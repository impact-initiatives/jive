import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import responses
from requests.exceptions import ConnectionError
from tenacity import RetryError

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jira_client import JiraClient


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure env vars are set for JiraClient initialization."""
    monkeypatch.setenv("JIRA_API_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIVE_MAX_ATTACHMENT_MB", "250")
    monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
    monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
    monkeypatch.setenv(
        "ALLOWED_DOMAINS", "repository.impact-initiatives.org,reach-initiative.atlassian.net"
    )


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    """Bypass tenacity's sleep to make retry tests fast."""
    monkeypatch.setattr("time.sleep", lambda x: None)


@pytest.fixture
def client():
    return JiraClient()


def test_missing_env_vars_raises_value_error(monkeypatch):
    monkeypatch.delenv("JIRA_API_EMAIL", raising=False)
    with pytest.raises(ValueError, match="JIRA_API_EMAIL and JIRA_API_TOKEN"):
        JiraClient()


def test_client_initialization_headers_and_auth(client):
    assert client.auth == ("test@example.com", "test-token")
    assert client.session.auth == ("test@example.com", "test-token")
    assert client.session.headers["Accept"] == "application/json"
    assert client.secure_link_auth == ("secure-user", "secure-pass")


@responses.activate
def test_post_comment_success(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123/comment"
    responses.add(responses.POST, url, json={"id": "1000"}, status=201)

    success = client.post_comment("RQA-123", {"type": "doc", "version": 1})
    assert success is True


@responses.activate
def test_post_comment_failure(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123/comment"
    responses.add(responses.POST, url, json={"error": "Bad Request"}, status=400)

    success = client.post_comment("RQA-123", {"type": "doc"})
    assert success is False


@responses.activate
def test_get_attachments_success(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    mock_attachments = [{"id": "1", "filename": "test.xlsx"}]
    responses.add(responses.GET, url, json={"fields": {"attachment": mock_attachments}}, status=200)

    attachments = client.get_attachments("RQA-123")
    assert attachments == mock_attachments


@responses.activate
def test_get_attachments_failure(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    responses.add(responses.GET, url, status=404)

    attachments = client.get_attachments("RQA-123")
    assert attachments == []


def test_download_proforma_attachment_no_valid_attachments(client, tmp_path):
    attachments = [
        {"filename": "image.png", "created": "2026-05-01T10:00:00.000+0000"},
        {
            "filename": "JIVE_Validation_Report_RQA-123.xlsx",
            "created": "2026-05-01T10:00:00.000+0000",
        },
    ]
    result = client.download_proforma_attachment("RQA-123", tmp_path, attachments)
    assert result is None


@responses.activate
def test_download_proforma_attachment_success(client, tmp_path):
    attachments = [
        {
            "filename": "old.xlsx",
            "content": "https://test/old.xlsx",
            "created": "2026-05-01T10:00:00.000+0000",
        },
        {
            "filename": "new.xlsx",
            "content": "https://test/new.xlsx",
            "created": "2026-05-02T10:00:00.000+0000",
        },
        {
            "filename": "JIVE_Validation_Report_RQA-123.xlsx",
            "content": "https://test/report.xlsx",
            "created": "2026-05-03T10:00:00.000+0000",
        },
    ]

    responses.add(responses.GET, "https://test/new.xlsx", body=b"mock-data", status=200)

    result = client.download_proforma_attachment("RQA-123", tmp_path, attachments)
    assert result == tmp_path / "new.xlsx"
    assert result.read_bytes() == b"mock-data"


@responses.activate
def test_download_from_secure_link_success(client, tmp_path):
    url = "https://repository.impact-initiatives.org/dataset.xlsx"
    responses.add(responses.GET, url, body=b"secure-data", status=200)

    result = client.download_from_secure_link(url, tmp_path, "secure.xlsx")
    assert result == tmp_path / "secure.xlsx"
    assert result.read_bytes() == b"secure-data"

    # Verify auth was passed
    assert responses.calls[0].request.headers.get("Authorization") is not None


def test_download_from_secure_link_ssrf_blocked_domain(client, tmp_path):
    url = "https://malicious.com/dataset.xlsx"
    result = client.download_from_secure_link(url, tmp_path, "secure.xlsx")
    assert result is None


def test_download_from_secure_link_ssrf_empty_allowlist(client, tmp_path, monkeypatch):
    import jira_client

    monkeypatch.setattr(jira_client, "ALLOWED_DOMAINS", frozenset())
    url = "https://repository.impact-initiatives.org/dataset.xlsx"
    result = client.download_from_secure_link(url, tmp_path, "secure.xlsx")
    assert result is None


@responses.activate
def test_upload_attachment_success(client, tmp_path):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123/attachments"
    responses.add(responses.POST, url, json=[{"content": "https://test/attach.xlsx"}], status=200)

    file_path = tmp_path / "report.xlsx"
    file_path.write_text("dummy content")

    success = client.upload_attachment("RQA-123", file_path)
    assert success is True


@responses.activate
def test_upload_attachment_failure(client, tmp_path):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123/attachments"
    responses.add(responses.POST, url, status=403)

    file_path = tmp_path / "report.xlsx"
    file_path.write_text("dummy content")

    success = client.upload_attachment("RQA-123", file_path)
    assert success is False


@responses.activate
def test_upload_public_jsm_attachment_success(client, tmp_path):
    # 1. get_service_desk_id
    responses.add(
        responses.GET,
        f"{client.base_url}/rest/servicedeskapi/servicedesk/RQA",
        json={"id": "5"},
        status=200,
    )

    # 2. upload temporary
    responses.add(
        responses.POST,
        f"{client.base_url}/rest/servicedeskapi/servicedesk/5/attachTemporaryFile",
        json={"temporaryAttachments": [{"temporaryAttachmentId": "temp-123"}]},
        status=201,
    )

    # 3. attach publicly
    responses.add(
        responses.POST,
        f"{client.base_url}/rest/servicedeskapi/request/RQA-123/attachment",
        json={},
        status=201,
    )

    file_path = tmp_path / "report.xlsx"
    file_path.write_text("dummy content")

    success = client.upload_public_jsm_attachment("RQA-123", "RQA", file_path)
    assert success is True


@responses.activate
def test_upload_public_jsm_attachment_sd_id_failure(client, tmp_path):
    responses.add(
        responses.GET, f"{client.base_url}/rest/servicedeskapi/servicedesk/RQA", status=404
    )
    file_path = tmp_path / "report.xlsx"
    file_path.write_text("dummy content")

    success = client.upload_public_jsm_attachment("RQA-123", "RQA", file_path)
    assert success is False


@responses.activate
def test_retry_on_429(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    responses.add(responses.GET, url, status=429)
    responses.add(responses.GET, url, status=429)
    responses.add(responses.GET, url, json={"fields": {"attachment": []}}, status=200)

    # Should succeed on the 3rd try
    attachments = client.get_attachments("RQA-123")
    assert attachments == []
    assert len(responses.calls) == 3


@responses.activate
def test_retry_exhaustion_raises_retry_error(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    # Will fail 3 times and raise RetryError
    responses.add(responses.GET, url, status=503)

    with pytest.raises(RetryError):
        client.get_attachments("RQA-123")
    assert len(responses.calls) == 3


@responses.activate
def test_connection_error_triggers_retry(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    responses.add(responses.GET, url, body=ConnectionError("Network down"))

    with pytest.raises(RetryError):
        client.get_attachments("RQA-123")
    assert len(responses.calls) == 3


@responses.activate
def test_no_retry_on_400(client):
    url = f"{client.base_url}/rest/api/3/issue/RQA-123?fields=attachment"
    responses.add(responses.GET, url, status=400)

    attachments = client.get_attachments("RQA-123")
    assert attachments == []
    # Should only try once
    assert len(responses.calls) == 1


def test_jira_client_download_memory_limit(client, tmp_path, monkeypatch):
    """Test that download aborts if the file exceeds the maximum allowed size."""
    monkeypatch.setenv("JIVE_MAX_ATTACHMENT_MB", "0")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b"a" * 8192]

    output_file = tmp_path / "test_download.xlsx"

    with patch.object(client.session, "get", return_value=mock_response):
        success = client._download_file_with_retry("http://example.com/file.xlsx", output_file)
        assert success is False
        assert not output_file.exists()
        mock_response.close.assert_called_once()
