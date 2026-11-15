import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker_base.models import JiraSubmissionPayload

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
)
os.environ["JIRA_API_EMAIL"] = "test@test.com"
os.environ["JIRA_API_TOKEN"] = "fake-token"
os.environ["JIVE_MAX_RETRIES"] = "3"

MAX_RETRIES = 3

from worker_base.base import BaseWorker  # dead_letter_message, main  # noqa: E402


@pytest.fixture
def get_base_worker() -> BaseWorker:
    return BaseWorker(
        logger_name="test_logger",
        description="worker description",
        queue_name="jive-validation-queue",
    )


class TestDeadLetterMessage:
    """Tests for the dead-letter queue pathway."""

    @patch("worker_base.base.JiraClient")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_dead_letter_sends_to_poison_queue(
        self, mock_get_queue, mock_jira_cls, get_base_worker: BaseWorker
    ):
        """A failed message should be forwarded to the poison queue with full metadata."""
        mock_poison_client = MagicMock()
        mock_get_queue.return_value = mock_poison_client
        mock_jira = MagicMock()
        get_base_worker.jira_client = mock_jira
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-001"
        msg.dequeue_count = 4

        payload = JiraSubmissionPayload(
            issue_key="RQA-999",
            programme_type="jmmi",
            output_type="dataset",
        )
        error = RuntimeError("Something broke")

        get_base_worker.dead_letter_message(msg, payload, error)

        # Verify it was sent to the poison queue
        mock_poison_client.send_message.assert_called_once()
        poison_body = json.loads(mock_poison_client.send_message.call_args[0][0])

        assert poison_body["original_message_id"] == "msg-001"
        assert poison_body["dequeue_count"] == 4
        assert poison_body["error_message"] == "Something broke"
        assert poison_body["error_type"] == "RuntimeError"
        assert poison_body["payload"]["issue_key"] == "RQA-999"
        assert "failed_at" in poison_body

    @patch("worker_base.base.JiraClient")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_dead_letter_posts_error_comment_to_jira(
        self, mock_get_queue, mock_jira_cls, get_base_worker: BaseWorker
    ):
        """The dead-letter handler should notify the user on the Jira ticket."""
        mock_get_queue.return_value = MagicMock()
        mock_jira = MagicMock()
        get_base_worker.jira_client = mock_jira
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-002"
        msg.dequeue_count = 3

        payload = JiraSubmissionPayload(
            issue_key="RQA-500",
            programme_type="jmmi",
            output_type="dataset",
        )
        get_base_worker.dead_letter_message(msg, payload, ValueError("Bad data"))

        mock_jira.post_comment.assert_called_once()
        posted_adf = mock_jira.post_comment.call_args[0][1]
        comment_text = posted_adf["content"][0]["content"][0]["text"]
        assert "failed" in comment_text.lower()
        assert "3" in comment_text

    @patch("worker_base.base.JiraClient")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_dead_letter_survives_jira_notification_failure(
        self, mock_get_queue, mock_jira_cls, get_base_worker: BaseWorker
    ):
        """If the Jira comment fails, the message should still be dead-lettered."""
        mock_poison_client = MagicMock()
        mock_get_queue.return_value = mock_poison_client
        mock_jira = MagicMock()
        get_base_worker.jira_client = mock_jira
        mock_jira.post_comment.side_effect = Exception("Jira is down")
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-003"
        msg.dequeue_count = 5

        payload = JiraSubmissionPayload(
            issue_key="RQA-600",
            programme_type="jmmi",
            output_type="dataset",
        )
        get_base_worker.dead_letter_message(msg, payload, RuntimeError("Exceeded retries"))
        mock_poison_client.send_message.assert_called_once()


class TestWorkerMainLoop:
    """Tests for the worker's main() polling loop."""

    # now handled by pydantic
    # @patch("worker_base.base.get_queue_client")
    # def test_main_exits_without_connection_string(self, mock_get_queue):
    #     """Worker should log and exit if the connection string is missing."""
    #     with patch("worker_base.base.QUEUE_CONNECTION_STRING", None):
    #         main()
    #         mock_get_queue.assert_not_called()

    @patch("worker_base.base.BaseWorker.process_message")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_main_processes_and_deletes_message(
        self, mock_get_queue, mock_process, get_base_worker: BaseWorker
    ):
        """A valid message should be processed and then deleted from the queue."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = 1
        msg.content = json.dumps(
            {"issue_key": "RQA-100", "programme_type": "jmmi", "output_type": "dataset"}
        )

        # First call returns a message, second call raises SystemExit to break the loop
        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            get_base_worker.work()

        mock_process.assert_called_once()
        assert mock_process.call_args[0][0] == msg

    @patch("worker_base.base.BaseWorker.dead_letter_message")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_main_dead_letters_after_max_retries(
        self, mock_get_queue, mock_dlq, get_base_worker: BaseWorker
    ):
        """A message exceeding MAX_RETRIES should be dead-lettered and deleted."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = MAX_RETRIES + 1
        msg.content = json.dumps(
            {"issue_key": "RQA-200", "programme_type": "jmmi", "output_type": "dataset"}
        )

        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            get_base_worker.work()

        mock_dlq.assert_called_once()
        mock_queue.delete_message.assert_called_once_with(msg)

    @patch("worker_base.base.BaseWorker.process_message")
    @patch("worker_base.base.BaseWorker.get_queue_client")
    def test_main_does_not_delete_on_processing_failure(
        self, mock_get_queue, mock_process, get_base_worker: BaseWorker
    ):
        """If processing fails, the message should NOT be deleted (so it retries
        via visibility timeout)."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = 1
        msg.content = json.dumps(
            {"issue_key": "RQA-300", "programme_type": "jmmi", "output_type": "dataset"}
        )

        mock_process.side_effect = RuntimeError("Pipeline crashed")
        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            get_base_worker.work()

        mock_process.assert_called_once()
        assert mock_process.call_args[0][0] == msg
        mock_queue.delete_message.assert_not_called()
