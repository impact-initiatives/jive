import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "argus"))
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
)
os.environ["JIRA_API_EMAIL"] = "test@test.com"
os.environ["JIRA_API_TOKEN"] = "fake-token"

from models import JiraSubmissionPayload  # noqa: E402
from worker import MAX_RETRIES, dead_letter_message, main  # noqa: E402


class TestDeadLetterMessage:
    """Tests for the dead-letter queue pathway."""

    @patch("worker.JiraClient")
    @patch("worker.get_queue_client")
    def test_dead_letter_sends_to_poison_queue(self, mock_get_queue, mock_jira_cls):
        """A failed message should be forwarded to the poison queue with full metadata."""
        mock_poison_client = MagicMock()
        mock_get_queue.return_value = mock_poison_client
        mock_jira = MagicMock()
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-001"
        msg.dequeue_count = 4

        payload = JiraSubmissionPayload(issue_key="RQA-999", dataset_type="jmmi")
        error = RuntimeError("Something broke")

        dead_letter_message(msg, payload, error)

        # Verify it was sent to the poison queue
        mock_poison_client.send_message.assert_called_once()
        poison_body = json.loads(mock_poison_client.send_message.call_args[0][0])

        assert poison_body["original_message_id"] == "msg-001"
        assert poison_body["dequeue_count"] == 4
        assert poison_body["error_message"] == "Something broke"
        assert poison_body["error_type"] == "RuntimeError"
        assert poison_body["payload"]["issue_key"] == "RQA-999"
        assert "failed_at" in poison_body

    @patch("worker.JiraClient")
    @patch("worker.get_queue_client")
    def test_dead_letter_posts_error_comment_to_jira(self, mock_get_queue, mock_jira_cls):
        """The dead-letter handler should notify the user on the Jira ticket."""
        mock_get_queue.return_value = MagicMock()
        mock_jira = MagicMock()
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-002"
        msg.dequeue_count = 3

        payload = JiraSubmissionPayload(issue_key="RQA-500")
        dead_letter_message(msg, payload, ValueError("Bad data"))

        mock_jira.post_comment.assert_called_once()
        posted_adf = mock_jira.post_comment.call_args[0][1]
        comment_text = posted_adf["content"][0]["content"][0]["text"]
        assert "failed" in comment_text.lower()
        assert "3" in comment_text

    @patch("worker.JiraClient")
    @patch("worker.get_queue_client")
    def test_dead_letter_survives_jira_notification_failure(self, mock_get_queue, mock_jira_cls):
        """If the Jira comment fails, the message should still be dead-lettered."""
        mock_poison_client = MagicMock()
        mock_get_queue.return_value = mock_poison_client
        mock_jira = MagicMock()
        mock_jira.post_comment.side_effect = Exception("Jira is down")
        mock_jira_cls.return_value = mock_jira

        msg = MagicMock()
        msg.id = "msg-003"
        msg.dequeue_count = 5

        payload = JiraSubmissionPayload(issue_key="RQA-600")
        dead_letter_message(msg, payload, RuntimeError("Exceeded retries"))
        mock_poison_client.send_message.assert_called_once()


class TestWorkerMainLoop:
    """Tests for the worker's main() polling loop."""

    @patch("worker.get_queue_client")
    def test_main_exits_without_connection_string(self, mock_get_queue):
        """Worker should log and exit if the connection string is missing."""
        with patch("worker.QUEUE_CONNECTION_STRING", None):
            main()
            mock_get_queue.assert_not_called()

    @patch("worker.time.sleep")
    @patch("worker.process_message")
    @patch("worker.get_queue_client")
    def test_main_processes_and_deletes_message(self, mock_get_queue, mock_process, mock_sleep):
        """A valid message should be processed and then deleted from the queue."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = 1
        msg.content = json.dumps({"issue_key": "RQA-100", "dataset_type": "jmmi"})

        # First call returns a message, second call raises SystemExit to break the loop
        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            main()

        mock_process.assert_called_once()
        assert mock_process.call_args[0][0] == msg

    @patch("worker.time.sleep")
    @patch("worker.dead_letter_message")
    @patch("worker.get_queue_client")
    def test_main_dead_letters_after_max_retries(self, mock_get_queue, mock_dlq, mock_sleep):
        """A message exceeding MAX_RETRIES should be dead-lettered and deleted."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = MAX_RETRIES + 1
        msg.content = json.dumps({"issue_key": "RQA-200", "dataset_type": "jmmi"})

        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            main()

        mock_dlq.assert_called_once()
        mock_queue.delete_message.assert_called_once_with(msg)

    @patch("worker.time.sleep")
    @patch("worker.process_message")
    @patch("worker.get_queue_client")
    def test_main_does_not_delete_on_processing_failure(
        self, mock_get_queue, mock_process, mock_sleep
    ):
        """If processing fails, the message should NOT be deleted (so it retries
        via visibility timeout)."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        msg = MagicMock()
        msg.dequeue_count = 1
        msg.content = json.dumps({"issue_key": "RQA-300"})

        mock_process.side_effect = RuntimeError("Pipeline crashed")
        mock_queue.receive_messages.side_effect = [[msg], SystemExit]

        with pytest.raises(SystemExit):
            main()

        mock_process.assert_called_once()
        assert mock_process.call_args[0][0] == msg
        mock_queue.delete_message.assert_not_called()

    @patch("worker.time.sleep")
    @patch("worker.get_queue_client")
    def test_main_sleeps_when_queue_is_empty(self, mock_get_queue, mock_sleep):
        """When no messages are available, the worker should sleep before polling again."""
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        # First call returns empty, sleep is called, second call breaks the loop
        mock_queue.receive_messages.side_effect = [iter([]), SystemExit]

        with pytest.raises(SystemExit):
            main()

        mock_sleep.assert_called_with(5)
