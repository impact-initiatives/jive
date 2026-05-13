import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def api_key():
    return os.getenv("JIVE_API_KEY", "dev-secret-key")


@pytest.mark.asyncio
async def test_healthz():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_valid_payload(api_key):
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
                headers={"x-functions-key": api_key},
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
            headers={"x-functions-key": os.getenv("JIVE_API_KEY", "dev-secret-key")},
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
