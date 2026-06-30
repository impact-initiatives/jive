import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from worker import process_message

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "argus"))
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
)
os.environ["JIVE_API_KEY"] = "test-secret-ZZZZZZZZZZZZZZ"
os.environ["SECURE_LINK_USERNAME"] = "XXXXXXX"
os.environ["SECURE_LINK_PASSWORD"] = "YYYYYYY"


client = TestClient(app)


@patch("main.get_queue_client")
def test_webhook_ingress_with_secure_link(mock_get_queue_client):
    """Test that a webhook with a secure link is accepted and enqueued."""
    mock_queue = MagicMock()
    mock_get_queue_client.return_value = mock_queue

    payload = {
        "issue_key": "RQA-123",
        "dataset_type": "jmmi",
        "secure_link": "https://example.com/dataset.xlsx",
    }

    response = client.post(
        "/api/webhook", json=payload, headers={"x-functions-key": "test-secret-ZZZZZZZZZZZZZZ"}
    )

    assert response.status_code == 202
    assert response.json()["status"] == "Accepted"

    # Verify queue message
    mock_queue.send_message.assert_called_once()
    enqueued_msg = mock_queue.send_message.call_args[0][0]
    enqueued_payload = json.loads(enqueued_msg)
    assert enqueued_payload["secure_link"] == "https://example.com/dataset.xlsx"


@patch("worker.JiraClient")
@patch("worker.ProformaParser")
@patch("worker.ImpactRepoClient")
@patch("worker.download_dataset")
@patch("worker_utils.ValidationPipeline")
@patch("worker.export_response_to_excel")
def test_worker_process_message_with_secure_link(
    mock_export,
    mock_pipeline_cls,
    mock_download_dataset,
    mock_impact_repo_cls,
    mock_proforma_cls,
    mock_jira_client_cls,
):
    """Test that the worker correctly delegates to download_from_secure_link."""
    # Setup mocks
    mock_jira = MagicMock()
    mock_jira_client_cls.return_value = mock_jira

    # Check guard: no existing report on the ticket
    mock_jira.get_attachments.return_value = []

    # Mock resolve_dataset to return a dummy path
    mock_dataset_path = MagicMock(spec=Path)
    mock_download_dataset.return_value = mock_dataset_path

    mock_pipeline = MagicMock()
    mock_pipeline_cls.return_value = mock_pipeline
    mock_pipeline.run.return_value = {
        "success": True,
        "metadata": {
            "dataset_type": "jmmi",
            "timestamp": "2023-01-01T00:00:00Z",
            "version": "1.0.0",
        },
        "summary": {"errors": 0, "warnings": 0, "info": 0, "admin_errors": 0, "passed": True},
        "details": {},
    }

    # Mock the Excel report path returned by export
    mock_excel_path = MagicMock(spec=Path)
    mock_excel_path.stat.return_value.st_size = 1024 * 1024  # 1MB — well within the limit
    mock_excel_path.__truediv__ = lambda self, other: mock_excel_path

    # queue message
    mock_msg = MagicMock()
    payload_data = {
        "issue_key": "RQA-123",
        "dataset_type": "jmmi",
        "secure_link": "https://example.com/dataset.xlsx",
    }
    mock_msg.content = json.dumps(payload_data)
    mock_msg.dequeue_count = 1

    from models import JiraSubmissionPayload

    payload = JiraSubmissionPayload(**payload_data)

    with patch("worker.Path") as mock_path_cls:
        mock_tmp_path = MagicMock()
        mock_tmp_path.__truediv__ = lambda self, other: mock_excel_path
        mock_path_cls.return_value = mock_tmp_path

        process_message(mock_msg, payload)

    mock_jira.get_attachments.assert_called_once()
    mock_download_dataset.assert_called_once()
    mock_pipeline.run.assert_called_once()
    mock_export.assert_called_once()
    mock_jira.post_comment.assert_called_once()
