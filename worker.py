import os
import json
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from azure.storage.queue import QueueClient
from models import JiraSubmissionPayload
from jira_client import JiraClient
from report_formatter import format_comment_adf
from logger import get_logger

from rqa_validator.orchestrator.validation_pipeline import ValidationPipeline
from excel_exporter import export_response_to_excel
from rqa_validator.models.api_models import PipelineResponse

logger = get_logger("jive.worker")

QUEUE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
QUEUE_NAME = os.getenv("JIVE_QUEUE_NAME", "jive-validation-queue")
POISON_QUEUE_NAME = f"{QUEUE_NAME}-poison"
MAX_RETRIES = int(os.getenv("JIVE_MAX_RETRIES", "3"))
MAX_JIRA_ATTACHMENT_MB = int(os.getenv("JIVE_MAX_ATTACHMENT_MB", "250"))


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

    # Idempotency guard: skip if a JIVE report already exists on this ticket
    expected_report_name = f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
    if any(a.get("filename") == expected_report_name for a in attachments):
        logger.warning(
            "Idempotency: JIVE report already attached — skipping re-validation",
            extra={"issue_key": payload.issue_key, "report": expected_report_name},
        )
        return

    start_time = time.monotonic()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        if payload.secure_link:
            logger.info("Downloading dataset from secure link", extra={"issue_key": payload.issue_key})
            dataset_path = jira.download_from_secure_link(payload.secure_link, tmp_path)
        else:
            logger.info("Downloading dataset from Jira attachments", extra={"issue_key": payload.issue_key})
            dataset_path = jira.download_proforma_attachment(payload.issue_key, tmp_path, attachments=attachments)

        if not dataset_path:
            error_adf = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "Failed to download dataset. No valid Excel attachment found.",
                            }
                        ],
                    }
                ],
            }
            jira.post_comment(payload.issue_key, error_adf)
            logger.warning("No Excel attachment found", extra={"issue_key": payload.issue_key})
            return

        logger.info("Running validation pipeline", extra={"issue_key": payload.issue_key})
        pipeline = ValidationPipeline(dataset_type=payload.dataset_type)
        response_dict = pipeline.run(dataset_path)
        response = PipelineResponse(**response_dict)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "Pipeline completed",
            extra={"issue_key": payload.issue_key, "duration_ms": duration_ms},
        )

        adf_summary = format_comment_adf(response)

        excel_report_path = tmp_path / f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
        export_response_to_excel(response, excel_report_path)

        #TODO: BLOB STORAGE INTEGRATION PLACEHOLDER
        #Future architecture: Upload `excel_report_path` to Azure Blob Storage here 
        #and retrieve a secure SAS download link. For now, attach it directly to Jira.
        #blob_url = upload_to_blob(excel_report_path)
        #adf_summary = format_comment_adf(response, blob_url)


        file_size_mb = excel_report_path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_JIRA_ATTACHMENT_MB:
            logger.warning(
                "Excel report too large for Jira attachment — skipping upload",
                extra={"issue_key": payload.issue_key, "size_mb": round(file_size_mb, 2), "limit_mb": MAX_JIRA_ATTACHMENT_MB},
            )

            adf_summary["content"].append({
                "type": "paragraph",
                "content": [{
                    "type": "text",
                    "text": f"⚠️ The validation report ({file_size_mb:.1f}MB) exceeds the Jira attachment limit ({MAX_JIRA_ATTACHMENT_MB}MB). Please contact the JIVE team to retrieve the full report.",
                    "marks": [{"type": "strong"}],
                }],
            })
        else:
            logger.info("Uploading attachment", extra={"issue_key": payload.issue_key, "size_mb": round(file_size_mb, 2)})
            jira.upload_attachment(payload.issue_key, excel_report_path)

        logger.info("Posting summary comment", extra={"issue_key": payload.issue_key})
        jira.post_comment(payload.issue_key, adf_summary)

        total_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("Job completed", extra={"issue_key": payload.issue_key, "duration_ms": total_ms})


def main():
    if not QUEUE_CONNECTION_STRING:
        logger.error("AZURE_STORAGE_CONNECTION_STRING not set. Exiting.")
        return

    queue_client = get_queue_client()
    try:
        queue_client.get_queue_properties()
    except Exception:
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
                    logger.error(
                        "Error processing message",
                        exc_info=e,
                        extra={"issue_key": getattr(msg, "id", "unknown")},
                    )

            if not has_message:
                time.sleep(5)

        except Exception as e:
            logger.error("Queue polling error", exc_info=e)
            time.sleep(10)


if __name__ == "__main__":
    main()
