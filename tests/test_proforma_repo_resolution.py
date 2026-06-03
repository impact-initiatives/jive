import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path
import responses
import requests

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "rqa-validator"))

# Set mock env vars
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net"
os.environ["JIRA_API_EMAIL"] = "mock-jira-email@example.com"
os.environ["JIRA_API_TOKEN"] = "mock-jira-token"
os.environ["REPO_USERNAME"] = "mock-wp-username@example.com"
os.environ["REPO_PASSWORD"] = "mock-wp-password"

from jira_client import JiraClient  # noqa: E402
from proforma_parser import ProformaParser  # noqa: E402
from impact_repo_client import ImpactRepoClient  # noqa: E402
from worker_utils import resolve_dataset  # noqa: E402

@responses.activate
def test_get_cloud_id():
    """Test retrieving and caching Atlassian Cloud ID."""
    responses.add(
        responses.GET,
        "https://mock/_edge/tenant_info",
        json={"cloudId": "mock-cloud-id-12345"},
        status=200
    )

    client = ProformaParser(requests.Session(), auth=("mock", "mock"), base_url="https://mock")
    cloud_id = client._get_cloud_id()

    assert cloud_id == "mock-cloud-id-12345"
    assert client.cloud_id == "mock-cloud-id-12345"
    assert len(responses.calls) == 1

    cloud_id_cached = client._get_cloud_id()
    assert cloud_id_cached == "mock-cloud-id-12345"
    assert len(responses.calls) == 1  # Should not make a second request


@responses.activate
def test_get_proforma_answers():
    """Test parsing of complex ProForma answers JSON."""
    responses.add(
        responses.GET,
        "https://api.atlassian.com/jira/forms/cloud/mock-cloud-id-12345/issue/issue-id-999/form",
        json=[{"id": "form-uuid-abc-123", "submitted": True}],
        status=200
    )
    responses.add(
        responses.GET,
        "https://api.atlassian.com/jira/forms/cloud/mock-cloud-id-12345/issue/issue-id-999/form/form-uuid-abc-123",
        json={
            "design": {
                "questions": {
                    "1": {"label": "IMPACT Repository", "questionKey": "repo_url"},
                    "2": {"label": "Dataset type", "questionKey": "ds_type", "choices": [
                        {"id": "choice-1", "label": "JMMI Factsheet"},
                        {"id": "choice-2", "label": "MSNA Dataset"}
                    ]}
                }
            },
            "state": {
                "answers": {
                    "1": {"text": "https://repository.impact-initiatives.org/resources/test-dataset"},
                    "2": {"choices": ["choice-1"]}
                }
            }
        },
        status=200
    )
    
    client = ProformaParser(requests.Session(), auth=("mock", "mock"), base_url="https://mock")
    client.cloud_id = "mock-cloud-id-12345"

    answers = client.get_answers("issue-id-999")

    assert answers["IMPACT Repository"] == "https://repository.impact-initiatives.org/resources/test-dataset"
    assert answers["repo_url"] == "https://repository.impact-initiatives.org/resources/test-dataset"
    assert answers["Dataset type"] == "JMMI Factsheet"
    assert answers["ds_type"] == "JMMI Factsheet"
    assert len(responses.calls) == 2


@responses.activate
def test_get_repo_session():
    """Test authenticated WordPress session creation for IMPACT Repository."""
    responses.add(
        responses.GET,
        "https://repository.impact-initiatives.org/wp-login.php",
        status=200
    )
    responses.add(
        responses.POST,
        "https://repository.impact-initiatives.org/wp-login.php",
        status=200,
        headers={"Set-Cookie": "wordpress_logged_in_abc123=user%7C123; Path=/"}
    )

    client = ImpactRepoClient()
    session = client.get_authenticated_session()

    assert session is not None
    assert client.session is not None
    assert len(responses.calls) == 2
    assert "log=mock-wp-username%40example.com" in responses.calls[1].request.body


@responses.activate
def test_scrape_excel_url():
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
    """
    
    responses.add(
        responses.GET,
        "https://repository.impact-initiatives.org/Ukraine_JMMI_R40_page",
        body=mock_html,
        status=200
    )
    
    client.get_authenticated_session = MagicMock(return_value=requests.Session())

    excel_url = client.scrape_excel_url("https://repository.impact-initiatives.org/Ukraine_JMMI_R40_page")

    assert excel_url == "https://repository.impact-initiatives.org/resources/download/Ukraine_JMMI_R40.xlsx"
    assert len(responses.calls) == 1


@patch("worker_utils.JiraClient.download_proforma_attachment")
@patch("worker_utils.ImpactRepoClient.scrape_excel_url")
@patch("worker_utils.ImpactRepoClient.download_excel")
def test_resolve_dataset_workflow(mock_download_excel, mock_scrape_url, mock_download_att):
    """Test unified fallback priority resolver strategy."""
    jira = JiraClient()
    proforma = ProformaParser(jira.session, jira.auth, jira.base_url)
    impact_repo = ImpactRepoClient()
    tmp_path = Path("/tmp/mock-dir")
    
    # ──── Case A: Direct Attachment  ────
    mock_download_att.return_value = Path("/tmp/mock-dir/attachment.xlsx")
    
    resolved_path = resolve_dataset(jira, proforma, impact_repo, "RQA-123", tmp_path,
                                     issue_id="10400", proforma_answers={})
    assert resolved_path == Path("/tmp/mock-dir/attachment.xlsx")
    
    # ──── Case B: ProForma & Repository Scraping ────
    mock_download_att.return_value = None  
    proforma_answers = {
        "IMPACT Repository": "https://repository.impact-initiatives.org/Ukraine_JMMI_R40"
    }
    mock_scrape_url.return_value = "https://repository.impact-initiatives.org/Ukraine_JMMI_R40.xlsx"
    mock_download_excel.return_value = True

    resolved_path = resolve_dataset(jira, proforma, impact_repo, "RQA-123", tmp_path,
                                     issue_id="10400", proforma_answers=proforma_answers)
    assert resolved_path == tmp_path / "Ukraine_JMMI_R40.xlsx"
    
    mock_scrape_url.assert_called_once_with("https://repository.impact-initiatives.org/Ukraine_JMMI_R40")
    mock_download_excel.assert_called_once()
