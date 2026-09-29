import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx2 import Client

from src.worker.config import get_settings, reload_settings

from .helpers import set_default_env_vars

reload_settings()
set_default_env_vars()


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "argus"))

# Set mock env vars
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
)
os.environ["JIRA_API_EMAIL"] = "mock-jira-email@example.com"
os.environ["JIRA_API_TOKEN"] = "mock-jira-token"
os.environ["REPO_USERNAME"] = "mock-wp-username@example.com"
os.environ["REPO_PASSWORD"] = "mock-wp-password"
get_settings()


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure env vars are set for JiraClient initialization."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIVE_MAX_ATTACHMENT_MB", "250")
    monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
    monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
    monkeypatch.setenv("ALLOWED_DOMAINS", "repository.impact-initiatives.org,test.atlassian.net")


from ..worker.impact_repo_client import ImpactRepoClient  # noqa: E402
from ..worker.jira.jira_client import JiraClient  # noqa: E402
from ..worker.jira.proforma_parser import ProformaParser  # noqa: E402
from ..worker.worker_utils import resolve_dataset  # noqa: E402


def test_get_cloud_id(httpx2_mock):
    """Test retrieving and caching Atlassian Cloud ID."""
    url = "https://mock/_edge/tenant_info"
    httpx2_mock.add_response(
        method="GET",
        url=url,
        json={"cloudId": "mock-cloud-id-12345"},
        status_code=200,
    )

    client = ProformaParser(Client(), auth=("mock", "mock"), base_url="https://mock")
    cloud_id = client._get_cloud_id()

    assert cloud_id == "mock-cloud-id-12345"
    assert client.cloud_id == "mock-cloud-id-12345"
    requests = httpx2_mock.get_requests(url=url)
    assert len(requests) == 1

    cloud_id_cached = client._get_cloud_id()
    assert cloud_id_cached == "mock-cloud-id-12345"
    requests = httpx2_mock.get_requests(url=url)
    assert len(requests) == 1


def test_get_proforma_answers(httpx2_mock):
    """Test parsing of complex ProForma answers JSON."""

    httpx2_mock.add_response(
        method="GET",
        url="https://api.atlassian.com/jira/forms/cloud/mock-cloud-id-12345/issue/issue-id-999/form",
        json=[
            {
                "id": "form-uuid-abc-123",
                "submitted": True,
                "internal": True,
                "lock": True,
                "name": "name",
                "updated": "20260101",
                "formTemplate": {"id": "123"},
            }
        ],
        status_code=200,
    )

    httpx2_mock.add_response(
        method="GET",
        url="https://api.atlassian.com/jira/forms/cloud/mock-cloud-id-12345/issue/issue-id-999/form/form-uuid-abc-123",
        json={
            "design": {
                "questions": {
                    "1": {"label": "IMPACT Repository", "questionKey": "repo_url"},
                    "2": {
                        "label": "Dataset type",
                        "questionKey": "ds_type",
                        "choices": [
                            {"id": "choice-1", "label": "JMMI Factsheet"},
                            {"id": "choice-2", "label": "MSNA Dataset"},
                        ],
                    },
                },
                "settings": {
                    "language": "en",
                    "name": "New employee onboarding",
                    "primaryLocale": "en-US",
                    "submit": {"lock": True, "pdf": True},
                    "translatedLocale": "en-GB",
                },
            },
            "state": {
                "answers": {
                    "1": {
                        "text": "https://repository.impact-initiatives.org/resources/test-dataset"
                    },
                    "2": {"choices": ["choice-1"]},
                },
                "status": "some_status",
                "visibility": "some_visibility",
            },
            "id": "form_id",
            "updated": "20260110",
        },
        status_code=200,
    )

    client = ProformaParser(Client(), auth=("mock", "mock"), base_url="https://mock")
    client.cloud_id = "mock-cloud-id-12345"

    answers = client.get_answers("issue-id-999")

    assert (
        answers["IMPACT Repository"]
        == "https://repository.impact-initiatives.org/resources/test-dataset"
    )
    assert answers["repo_url"] == "https://repository.impact-initiatives.org/resources/test-dataset"
    assert answers["Dataset type"] == "JMMI Factsheet"
    assert answers["ds_type"] == "JMMI Factsheet"
    requests = httpx2_mock.get_requests()
    assert len(requests) == 2


def test_get_repo_session(httpx2_mock):
    """Test authenticated WordPress session creation for IMPACT Repository."""

    httpx2_mock.add_response(
        method="GET",
        url="https://repository.impact-initiatives.org/wp-login.php",
        status_code=200,
    )

    httpx2_mock.add_response(
        method="POST",
        url="https://repository.impact-initiatives.org/wp-login.php",
        status_code=200,
        headers={"Set-Cookie": "wordpress_logged_in_abc123=user%7C123; Path=/"},
    )

    client = ImpactRepoClient()
    session = client.get_authenticated_session()

    assert session is not None
    assert client.session is not None
    requests = httpx2_mock.get_requests()
    assert len(requests) == 2
    assert "log=mock-wp-username%40example.com" in str(requests[1].content.decode("utf-8"))


def test_scrape_excel_url(httpx2_mock):
    """Test HTML scraping regex for extracting direct .xlsx links."""
    client = ImpactRepoClient()

    mock_html = """
    <html>
        <body>
            <div class="download-section">
                <a href="https://repository.impact-initiatives.org/resources/download/Ukraine_JMMI_R40.xlsx">Download Dataset</a>
            </div>
        </body>
    </html>
    """  # noqa: E501

    httpx2_mock.add_response(
        method="GET",
        url="https://repository.impact-initiatives.org/Ukraine_JMMI_R40_page",
        status_code=200,
        content=mock_html,
    )

    client.get_authenticated_session = MagicMock(return_value=Client())

    excel_url = client.scrape_excel_url(
        "https://repository.impact-initiatives.org/Ukraine_JMMI_R40_page"
    )

    assert (
        excel_url
        == "https://repository.impact-initiatives.org/resources/download/Ukraine_JMMI_R40.xlsx"
    )
    requests = httpx2_mock.get_requests()
    assert len(requests) == 1


@patch("src.worker.worker_utils.JiraClient.download_proforma_attachment")
@patch("src.worker.worker_utils.ImpactRepoClient.scrape_excel_url")
@patch("src.worker.worker_utils.ImpactRepoClient.download_excel")
def test_resolve_dataset_workflow(mock_download_excel, mock_scrape_url, mock_download_att):
    """Test unified fallback priority resolver strategy."""
    jira = JiraClient()
    proforma = ProformaParser(jira.session, jira.auth, jira.base_url)
    impact_repo = ImpactRepoClient()
    tmp_path = Path("/tmp/mock-dir")

    # ──── Case A: Direct Attachment  ────
    mock_download_att.return_value = Path("/tmp/mock-dir/attachment.xlsx")

    resolved_path = resolve_dataset(
        jira, proforma, impact_repo, "RQA-123", tmp_path, issue_id="10400", proforma_answers={}
    )
    assert resolved_path == Path("/tmp/mock-dir/attachment.xlsx")

    # ──── Case B: ProForma & Repository Scraping ────
    mock_download_att.return_value = None
    proforma_answers = {
        "IMPACT Repository": "https://repository.impact-initiatives.org/Ukraine_JMMI_R40"
    }
    mock_scrape_url.return_value = "https://repository.impact-initiatives.org/Ukraine_JMMI_R40.xlsx"
    mock_download_excel.return_value = True

    resolved_path = resolve_dataset(
        jira,
        proforma,
        impact_repo,
        "RQA-123",
        tmp_path,
        issue_id="10400",
        proforma_answers=proforma_answers,
    )
    assert resolved_path == tmp_path / "Ukraine_JMMI_R40.xlsx"

    mock_scrape_url.assert_called_once_with(
        "https://repository.impact-initiatives.org/Ukraine_JMMI_R40"
    )
    mock_download_excel.assert_called_once()
