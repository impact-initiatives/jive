from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import json
from pathlib import Path
import os
import sys

# Add project rqa-validator path to sys.path and MOCK env vars
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "rqa-validator"))
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
os.environ["JIVE_API_KEY"] = "test-secret-ZZZZZZZZZZZZZZ"
os.environ["SECURE_LINK_USERNAME"] = "XXXXXXX"
os.environ["SECURE_LINK_PASSWORD"] = "YYYYYYY"

from main import app  # noqa: E402
from worker import process_message  # noqa: E402

client = TestClient(app)

@patch("main.get_queue_client")
def test_webhook_ingress_with_secure_link(mock_get_queue_client):
    """Test that a webhook with a secure link is accepted and enqueued."""
    mock_queue = MagicMock()
    mock_get_queue_client.return_value = mock_queue

    payload = {
        "issue_key": "RQA-123",
        "dataset_type": "jmmi",
        "secure_link": "https://example.com/dataset.xlsx"
    }

    response = client.post(
        "/api/webhook",
        json=payload,
        headers={"x-functions-key": "test-secret-ZZZZZZZZZZZZZZ"}
    )

    assert response.status_code == 202
    assert response.json()["status"] == "Accepted"
    
    # Verify queue message
    mock_queue.send_message.assert_called_once()
    enqueued_msg = mock_queue.send_message.call_args[0][0]
    enqueued_payload = json.loads(enqueued_msg)
    assert enqueued_payload["secure_link"] == "https://example.com/dataset.xlsx"

@patch("worker.JiraClient")
@patch("worker.ValidationPipeline")
@patch("worker.export_response_to_excel")

def test_worker_process_message_with_secure_link(mock_export, mock_pipeline_cls, mock_jira_client_cls):
    """Test that the worker correctly delegates to download_from_secure_link."""
    # Setup mocks
    mock_jira = MagicMock()
    mock_jira_client_cls.return_value = mock_jira
    
    # Mock download_from_secure_link to return a dummy path
    mock_jira.download_from_secure_link.return_value = Path("/tmp/mock_dataset.xlsx")
    
    mock_pipeline = MagicMock()
    mock_pipeline_cls.return_value = mock_pipeline
    mock_pipeline.run.return_value = {
        "success": True,
        "metadata": {"dataset_type": "jmmi", "timestamp": "2023-01-01T00:00:00Z", "version": "1.0.0"},
        "summary": {"errors": 0, "warnings": 0, "info": 0, "admin_errors": 0, "passed": True},
        "details": {}
    }

    #queue message
    mock_msg = MagicMock()
    mock_msg.content = json.dumps({
        "issue_key": "RQA-123",
        "dataset_type": "jmmi",
        "secure_link": "https://example.com/dataset.xlsx"
    })
    mock_msg.dequeue_count = 1

    process_message(mock_msg)

    mock_jira.download_from_secure_link.assert_called_once()
    mock_jira.download_proforma_attachment.assert_not_called()
    
    mock_pipeline.run.assert_called_once_with(Path("/tmp/mock_dataset.xlsx"))
    mock_export.assert_called_once()
    mock_jira.upload_attachment.assert_called_once()
    mock_jira.post_comment.assert_called_once()
