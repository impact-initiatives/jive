import json
from datetime import UTC, datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.core.paging import ItemPaged
from azure.storage.queue import QueueClient, QueueMessage
from jira.jira_client import JiraClient
from jive_logging.logger import get_logger

from .config import get_settings
from .models import JiraSubmissionPayload

settings = get_settings()


class BaseWorker:
    def __init__(self, logger_name: str, description: str, queue_name: str) -> None:
        self.logger = get_logger(f"jive.{logger_name}")
        self.description = description
        self.queue_name: str = queue_name
        self.POISON_QUEUE_NAME = f"{queue_name}-poison"
        self.jira_client = JiraClient()

    def get_queue_client(self, queue_name: str) -> QueueClient:
        return QueueClient.from_connection_string(
            conn_str=settings.queue_connection_string, queue_name=queue_name
        )

    def dead_letter_message(
        self,
        msg: QueueMessage,
        payload: JiraSubmissionPayload,
        error: Exception,
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

        self.logger.critical(
            "Message dead-lettered after %d attempts",
            msg.dequeue_count,
            extra={
                "issue_key": payload.issue_key,
                "dequeue_count": msg.dequeue_count,
                "queue": self.POISON_QUEUE_NAME,
            },
        )

        poison_client = self.get_queue_client(self.POISON_QUEUE_NAME)
        try:
            _ = poison_client.send_message(json.dumps(poison_message))
        except ResourceNotFoundError:
            self.logger.info(
                "Poison queue not found, creating it...",
                extra={"queue": self.POISON_QUEUE_NAME},
            )
            poison_client.create_queue()
            _ = poison_client.send_message(json.dumps(poison_message))

        # Notify on the Jira ticket
        try:
            error_adf = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{self.description} failed after {msg.dequeue_count}"
                                + " attempts. Please contact RQA.",
                                "marks": [{"type": "strong"}],
                            }
                        ],
                    }
                ],
            }
            _ = self.jira_client.post_comment(payload.issue_key, error_adf)
        except Exception as notify_err:
            self.logger.error(
                "Failed to post dead-letter notification to Jira",
                exc_info=notify_err,
                extra={"issue_key": payload.issue_key},
            )

    def process_message(self, msg: QueueMessage, payload: JiraSubmissionPayload):
        pass

    def failure_message(self, issue_key: str):
        try:
            error_adf = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Jive {self.description} failed to process Jira issue."
                                + " Please contact RQA.",
                                "marks": [{"type": "strong"}],
                            }
                        ],
                    }
                ],
            }
            _ = self.jira_client.post_comment(issue_key, error_adf)
        except Exception as notify_err:
            self.logger.error(
                "Failed to post failure notification to Jira",
                exc_info=notify_err,
                extra={"issue_key": issue_key},
            )

    def work(
        self,
    ):
        self.logger.info("Getting queue client...")
        queue_client = self.get_queue_client(self.queue_name)
        try:
            self.logger.info("Getting queue properties...")
            _ = queue_client.get_queue_properties()
        except ResourceNotFoundError:
            self.logger.info("Queue not found, creating it...", extra={"queue": self.queue_name})
            queue_client.create_queue()

        self.logger.info("Worker started", extra={"queue": self.queue_name})

        has_message = True
        while has_message:
            try:
                self.logger.info("Checking for new messages...")
                messages: ItemPaged[QueueMessage] = queue_client.receive_messages(
                    max_messages=1, visibility_timeout=300
                )

                # if there are no messages the process will end after the for loop does nothing
                has_message = False

                for msg in messages:
                    has_message = True
                    # Parse payload once — used by both dead-letter and processing
                    try:
                        payload_data = json.loads(msg.content)
                        payload = JiraSubmissionPayload(**payload_data)
                    except Exception:
                        self.logger.error(
                            "Malformed message — dead-lettering immediately",
                            extra={"msg_id": msg.id, "content": str(msg.content)[:200]},
                        )
                        self.dead_letter_message(
                            msg,
                            JiraSubmissionPayload(
                                issue_key="UNKNOWN",
                                programme_type="UNKNOWN",
                                output_type="UNKNOWN",
                            ),
                            ValueError("Malformed JSON payload"),
                        )
                        queue_client.delete_message(msg)
                        continue

                    # Dead-letter check
                    if msg.dequeue_count is not None and msg.dequeue_count > settings.max_retries:
                        self.dead_letter_message(
                            msg,
                            payload,
                            RuntimeError(f"Exceeded {settings.max_retries} retries"),
                        )
                        queue_client.delete_message(msg)
                        continue

                    try:
                        self.process_message(msg, payload)
                        queue_client.delete_message(msg)
                    except Exception as e:
                        self.logger.error(
                            "Error processing message",
                            exc_info=e,
                            extra={"issue_key": payload.issue_key},
                        )
                        self.failure_message(payload.issue_key)

            except Exception as e:
                self.logger.error("Queue polling error", exc_info=e)
