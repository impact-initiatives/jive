import os
import json
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from azure.storage.queue import QueueClient
from azure.core.exceptions import ResourceNotFoundError
from models import JiraSubmissionPayload
from jira_client import JiraClient
from logger import get_logger
from excel_exporter import export_response_to_excel
from worker_utils import (
    check_idempotency,
    download_dataset,
    resolve_context,
    run_validation,
    publish_results,
)

logger = get_logger("jive.worker")

QUEUE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
QUEUE_NAME = os.getenv("JIVE_QUEUE_NAME", "jive-validation-queue")
POISON_QUEUE_NAME = f"{QUEUE_NAME}-poison"
MAX_RETRIES = int(os.getenv("JIVE_MAX_RETRIES", "3"))


def get_queue_client(queue_name: str = QUEUE_NAME) -> QueueClient:
    return QueueClient.from_connection_string(
        conn_str=QUEUE_CONNECTION_STRING,
        queue_name=queue_name
    )


def dead_letter_message(msg, payload: JiraSubmissionPayload, error: Exception):
    """Moves a failed message to the poison queue with full metadata."""
    poison_message = {
        "original_message_id": msg.id,
        "dequeue_count": msg.dequeue_count,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error_message": str(error),
        "error_type": type(error).__name__,
        "payload": payload.model_dump(),
    }

    logger.critical(
        "Message dead-lettered after %d attempts",
        msg.dequeue_count,
        extra={
            "issue_key": payload.issue_key,
            "dequeue_count": msg.dequeue_count,
            "queue": POISON_QUEUE_NAME,
        },
    )

    poison_client = get_queue_client(POISON_QUEUE_NAME)
    try:
        poison_client.send_message(json.dumps(poison_message))
    except ResourceNotFoundError:
        logger.info("Poison queue not found, creating it...", extra={"queue": POISON_QUEUE_NAME})
        poison_client.create_queue()
        poison_client.send_message(json.dumps(poison_message))

    #Notify on the Jira ticket
    try:
        jira = JiraClient()
        error_adf = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Validation failed after {msg.dequeue_count} attempts. The JIVE team has been notified.",
                            "marks": [{"type": "strong"}],
                        }
                    ],
                }
            ],
        }
        jira.post_comment(payload.issue_key, error_adf)
    except Exception as notify_err:
        logger.error(
            "Failed to post dead-letter notification to Jira",
            exc_info=notify_err,
            extra={"issue_key": payload.issue_key},
        )


def process_message(msg):
    """Processes a single Jira validation job."""
    payload_data = json.loads(msg.content)
    payload = JiraSubmissionPayload(**payload_data)

    logger.info("Processing message", extra={"issue_key": payload.issue_key, "dequeue_count": msg.dequeue_count})

    jira = JiraClient()
    
    # Fetch attachments once — used for both idempotency and download
    attachments = jira.get_attachments(payload.issue_key)

    if check_idempotency(payload, attachments):
        return

    start_time = time.monotonic()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Resolve issue ID once to reuse
        resolved_issue_id = jira.get_issue_id(payload.issue_key)
        proforma_answers = jira.get_proforma_answers(resolved_issue_id) if resolved_issue_id else {}

        dataset_path = download_dataset(jira, payload, tmp_path, resolved_issue_id, attachments, proforma_answers)
        if not dataset_path:
            return

        dataset_type, repo_url, repo_action = resolve_context(jira, payload, resolved_issue_id, proforma_answers)
        
        response = run_validation(dataset_path, dataset_type, payload)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "Pipeline completed",
            extra={"issue_key": payload.issue_key, "duration_ms": duration_ms},
        )

        excel_report_path = tmp_path / f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
        export_response_to_excel(response, excel_report_path)

        publish_results(jira, payload, response, excel_report_path, repo_url, repo_action, dataset_type)

        total_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("Job completed", extra={"issue_key": payload.issue_key, "duration_ms": total_ms})


def main():
    if not QUEUE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING not set. Exiting.")
        return

    queue_client = get_queue_client()
    try:
        queue_client.get_queue_properties()
    except ResourceNotFoundError:
        logger.info("Queue not found, creating it...", extra={"queue": QUEUE_NAME})
        queue_client.create_queue()
        
    logger.info("Worker started", extra={"queue": QUEUE_NAME})

    while True:
        try:
            messages = queue_client.receive_messages(max_messages=1, visibility_timeout=300)

            has_message = False
            for msg in messages:
                has_message = True

                # Dead-letter check
                if msg.dequeue_count > MAX_RETRIES:
                    try:
                        payload_data = json.loads(msg.content)
                        payload = JiraSubmissionPayload(**payload_data)
                    except Exception:
                        payload = JiraSubmissionPayload(issue_key="UNKNOWN")

                    dead_letter_message(msg, payload, RuntimeError(f"Exceeded {MAX_RETRIES} retries"))
                    queue_client.delete_message(msg)
                    continue

                try:
                    process_message(msg)
                    queue_client.delete_message(msg)
                except Exception as e:
                    issue_key = "UNKNOWN"
                    try:
                        issue_key = json.loads(msg.content).get("issue_key", "UNKNOWN")
                    except Exception:
                        pass
                    
                    logger.error(
                        "Error processing message",
                        exc_info=e,
                        extra={"issue_key": issue_key},
                    )

            if not has_message:
                time.sleep(5)

        except Exception as e:
            logger.error("Queue polling error", exc_info=e)
            time.sleep(10)


if __name__ == "__main__":
    main()
