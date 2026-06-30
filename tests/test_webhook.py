import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Ensure test API key is set before importing main (which reads at module level)
os.environ.setdefault("JIVE_API_KEY", "test-secret-ZZZZZZZZZZZZZZ")

from httpx import ASGITransport, AsyncClient

from main import app

TEST_API_KEY = os.environ["JIVE_API_KEY"]


@pytest.mark.asyncio
async def test_healthz():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_valid_payload():
    """Valid payload with correct API key should return 202."""
    transport = ASGITransport(app=app)
    payload = {
        "issue_key": "RQA-100",
        "project_key": "RQA",
        "rcid": "RCID-001",
        "dataset_type": "jmmi",
    }

    with patch("main.get_queue_client") as mock_queue:
        mock_client = MagicMock()
        mock_queue.return_value = mock_client

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/webhook",
                json=payload,
                headers={"x-functions-key": TEST_API_KEY},
            )

    assert response.status_code == 202
    assert response.json()["status"] == "Accepted"
    mock_client.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_invalid_api_key():
    """Invalid API key should return 401."""
    transport = ASGITransport(app=app)
    payload = {"issue_key": "RQA-100"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhook",
            json=payload,
            headers={"x-functions-key": "wrong-key"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_issue_key():
    """Missing required field should return 422 (Pydantic validation)."""
    transport = ASGITransport(app=app)
    payload = {"project_key": "RQA"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhook",
            json=payload,
            headers={"x-functions-key": TEST_API_KEY},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_no_api_key_header():
    """No API key header should return 401."""
    transport = ASGITransport(app=app)
    payload = {"issue_key": "RQA-100"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/webhook", json=payload)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_404_not_found():
    """Invalid path should return 404 via our custom handler."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_webhook_405_method_not_allowed():
    """Wrong HTTP method should return 405 via our custom handler."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send GET to a POST endpoint
        response = await client.get("/api/webhook")

    assert response.status_code == 405
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_webhook_500_internal_error():
    """Unhandled Python exceptions should return 500 via the global exception handler."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    payload = {
        "issue_key": "RQA-100",
        "project_key": "RQA",
        "rcid": "RCID-001",
        "dataset_type": "jmmi",
    }

    # Mock something internal to raise a raw Exception
    with patch("main.secrets.compare_digest", side_effect=ValueError("Simulated crash")):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/webhook",
                json=payload,
                headers={"x-functions-key": TEST_API_KEY},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"


@pytest.mark.asyncio
async def test_webhook_azure_queue_not_found():
    """If the queue does not exist, it should be auto-created and message sent, returning 202."""
    from azure.core.exceptions import ResourceNotFoundError

    transport = ASGITransport(app=app)
    payload = {"issue_key": "RQA-100", "dataset_type": "jmmi"}

    with patch("main.get_queue_client") as mock_queue:
        mock_client = MagicMock()
        mock_queue.return_value = mock_client
        # First send_message fails, second succeeds
        mock_client.send_message.side_effect = [ResourceNotFoundError("Queue not found"), None]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/webhook",
                json=payload,
                headers={"x-functions-key": TEST_API_KEY},
            )

    assert response.status_code == 202
    assert response.json()["status"] == "Accepted"
    mock_client.create_queue.assert_called_once()
    assert mock_client.send_message.call_count == 2


@pytest.mark.asyncio
async def test_webhook_azure_queue_unhandled_exception():
    """If the queue throws an unhandled exception (e.g., connection error), it should return 500."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    payload = {"issue_key": "RQA-100", "dataset_type": "jmmi"}

    with patch("main.get_queue_client") as mock_queue:
        mock_client = MagicMock()
        mock_queue.return_value = mock_client
        mock_client.send_message.side_effect = Exception("Connection Refused")

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/webhook",
                json=payload,
                headers={"x-functions-key": TEST_API_KEY},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to enqueue validation job"
