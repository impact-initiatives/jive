import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.core.paging import ItemPaged
from azure.storage.queue import QueueClient, QueueMessage

from .excel_exporter import export_response_to_excel
from .impact_repo_client import ImpactRepoClient
from .jira.jira_client import JiraClient
from .jira.models import IssueAttachment
from .logger import get_logger
from .models import JiraSubmissionPayload
from .proforma_parser import ProformaParser
from .worker_utils import (
    check_idempotency,
    download_dataset,
    publish_results,
    resolve_context,
    run_validation,
)

logger = get_logger("jive.worker")

QUEUE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
QUEUE_NAME = os.getenv("JIVE_QUEUE_NAME", "jive-validation-queue")
POISON_QUEUE_NAME = f"{QUEUE_NAME}-poison"
MAX_RETRIES = int(os.getenv("JIVE_MAX_RETRIES", "3"))


def get_queue_client(queue_name: str = QUEUE_NAME) -> QueueClient:
    conn_str = QUEUE_CONNECTION_STRING
    if not conn_str:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set")
    return QueueClient.from_connection_string(conn_str=conn_str, queue_name=queue_name)


def dead_letter_message(
    msg: QueueMessage,
    payload: JiraSubmissionPayload,
    error: Exception,
    jira: JiraClient | None = None,
):
    """Moves a failed message to the poison queue with full metadata."""
    poison_message = {
        "original_message_id": msg.id,
        "dequeue_count": msg.dequeue_count,
        "failed_at": datetime.now(UTC).isoformat(),
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
        _ = poison_client.send_message(json.dumps(poison_message))
    except ResourceNotFoundError:
        logger.info("Poison queue not found, creating it...", extra={"queue": POISON_QUEUE_NAME})
        poison_client.create_queue()
        _ = poison_client.send_message(json.dumps(poison_message))

    # Notify on the Jira ticket
    try:
        if jira is None:
            jira = JiraClient()
        error_adf: dict[
            str, int | str | list[dict[str, str | list[dict[str, str | list[dict[str, str]]]]]]
        ] = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Validation failed after {msg.dequeue_count} attempts."
                            + " The JIVE team has been notified.",
                            "marks": [{"type": "strong"}],
                        }
                    ],
                }
            ],
        }
        _ = jira.post_comment(payload.issue_key, error_adf)
    except Exception as notify_err:
        logger.error(
            "Failed to post dead-letter notification to Jira",
            exc_info=notify_err,
            extra={"issue_key": payload.issue_key},
        )


def process_message(msg: QueueMessage, payload: JiraSubmissionPayload):
    """Processes a single Jira validation job."""
    logger.info(
        "Processing message",
        extra={"issue_key": payload.issue_key, "dequeue_count": msg.dequeue_count},
    )

    jira = JiraClient()
    proforma = ProformaParser(jira.session, jira.auth, jira.base_url)
    impact_repo = ImpactRepoClient()

    # Fetch attachments once — used for both idempotency and download
    attachments: list[IssueAttachment] | None = jira.get_attachments(payload.issue_key)

    if check_idempotency(payload, attachments):
        return

    start_time = time.monotonic()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Resolve issue ID once to reuse
        resolved_issue_id = jira.get_issue_id(payload.issue_key)
        proforma_answers = proforma.get_answers(resolved_issue_id) if resolved_issue_id else {}

        if resolved_issue_id is not None:
            dataset_path = download_dataset(
                jira,
                proforma,
                impact_repo,
                payload,
                tmp_path,
                resolved_issue_id,
                attachments,
                proforma_answers,
            )

            dataset_type, repo_url, repo_action = resolve_context(
                proforma, payload, resolved_issue_id, proforma_answers
            )
            if dataset_path is not None:
                response = run_validation(dataset_path, dataset_type, payload)

                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "Pipeline completed",
                    extra={"issue_key": payload.issue_key, "duration_ms": duration_ms},
                )

                excel_report_path = tmp_path / f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
                export_response_to_excel(response, excel_report_path)

                publish_results(
                    jira, payload, response, excel_report_path, repo_url, repo_action, dataset_type
                )

                total_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "Job completed", extra={"issue_key": payload.issue_key, "duration_ms": total_ms}
                )
        else:
            raise ValueError("Failed to resolve issue ID from key.")


def main():
    if not QUEUE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING not set. Exiting.")
        return
    logger.info("Getting queue client...")
    queue_client = get_queue_client()
    try:
        logger.info("Getting queue properties...")
        _ = queue_client.get_queue_properties()
    except ResourceNotFoundError:
        logger.info("Queue not found, creating it...", extra={"queue": QUEUE_NAME})
        queue_client.create_queue()

    logger.info("Worker started", extra={"queue": QUEUE_NAME})

    while True:
        try:
            logger.info("Checking for new messages...")
            messages: ItemPaged[QueueMessage] = queue_client.receive_messages(
                max_messages=1, visibility_timeout=300
            )

            has_message = False
            for msg in messages:
                has_message = True

                # Parse payload once — used by both dead-letter and processing
                try:
                    payload_data = json.loads(msg.content)
                    payload = JiraSubmissionPayload(**payload_data)
                except Exception:
                    logger.error(
                        "Malformed message — dead-lettering immediately",
                        extra={"msg_id": msg.id, "content": str(msg.content)[:200]},
                    )
                    dead_letter_message(
                        msg,
                        JiraSubmissionPayload(issue_key="UNKNOWN"),
                        ValueError("Malformed JSON payload"),
                    )
                    queue_client.delete_message(msg)
                    continue

                # Dead-letter check
                if msg.dequeue_count is not None and msg.dequeue_count > MAX_RETRIES:
                    dead_letter_message(
                        msg, payload, RuntimeError(f"Exceeded {MAX_RETRIES} retries")
                    )
                    queue_client.delete_message(msg)
                    continue

                try:
                    process_message(msg, payload)
                    queue_client.delete_message(msg)
                except Exception as e:
                    logger.error(
                        "Error processing message",
                        exc_info=e,
                        extra={"issue_key": payload.issue_key},
                    )

            if not has_message:
                time.sleep(5)

        except Exception as e:
            logger.error("Queue polling error", exc_info=e)
            time.sleep(10)


if __name__ == "__main__":
    main()
