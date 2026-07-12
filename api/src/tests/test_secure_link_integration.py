import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

os.environ["SECURE_LINK_USERNAME"] = "XXXXXXX"
os.environ["SECURE_LINK_PASSWORD"] = "YYYYYYY"
os.environ["JIVE_API_KEY"] = "test-secret-ZZZZZZZZZZZZZZ"
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
)
# @pytest.fixture
# def settings_with_defaults():
#     return Settings(
#         SECURE_LINK_USERNAME = "XXXXXXX",
#         SECURE_LINK_PASSWORD = "YYYYYYY",
#         JIVE_API_KEY = "test-secret-ZZZZZZZZZZZZZZ",
#         AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"


#     )


from api.main import app

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "argus"))


# @pytest.fixture(autouse=True)
# def mock_env_vars(monkeypatch):
#     """Ensure env vars are set for JiraClient initialization."""
#     monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
#     monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
#     monkeypatch.setenv("JIVE_API_KEY", "test-secret-ZZZZZZZZZZZZZZ")

client = TestClient(app)


@patch("api.main.get_queue_client")
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
