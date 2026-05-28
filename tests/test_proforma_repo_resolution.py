import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

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


@patch("jira_client.requests.Session")
def test_get_cloud_id(mock_session_cls):
    """Test retrieving and caching Atlassian Cloud ID."""
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"cloudId": "mock-cloud-id-12345"}
    mock_session.get.return_value = mock_resp

    client = JiraClient()
    cloud_id = client._get_cloud_id()

    assert cloud_id == "mock-cloud-id-12345"
    assert client.cloud_id == "mock-cloud-id-12345"
    mock_session.get.assert_called_once()

    cloud_id_cached = client._get_cloud_id()
    assert cloud_id_cached == "mock-cloud-id-12345"
    mock_session.get.assert_called_once() 


@patch("jira_client.requests.Session")
def test_get_proforma_answers(mock_session_cls):
    """Test parsing of complex ProForma answers JSON."""
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    
    client = JiraClient()
    client.cloud_id = "mock-cloud-id-12345"

    # Mock ProForma forms list response
    mock_forms_resp = MagicMock()
    mock_forms_resp.status_code = 200
    mock_forms_resp.json.return_value = [{"id": "form-uuid-abc-123", "submitted": True}]
    
    # Mock detailed answers response
    mock_details_resp = MagicMock()
    mock_details_resp.status_code = 200
    mock_details_resp.json.return_value = {
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
    }

    mock_session.get.side_effect = [mock_forms_resp, mock_details_resp]

    answers = client.get_proforma_answers("issue-id-999")

    assert answers["IMPACT Repository"] == "https://repository.impact-initiatives.org/resources/test-dataset"
    assert answers["repo_url"] == "https://repository.impact-initiatives.org/resources/test-dataset"
    assert answers["Dataset type"] == "JMMI Factsheet"
    assert answers["ds_type"] == "JMMI Factsheet"


@patch("jira_client.requests.Session")
def test_get_repo_session(mock_session_cls):
    """Test authenticated WordPress session creation for IMPACT Repository."""
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp
    mock_session.post.return_value = mock_resp

    client = JiraClient()
    session = client._get_repo_session()

    assert session == mock_session
    assert client.repo_session == mock_session
    mock_session.get.assert_called_with("https://repository.impact-initiatives.org/wp-login.php", timeout=15)
    mock_session.post.assert_called_once()
    assert mock_session.post.call_args[1]["data"]["log"] == "mock-wp-username@example.com"


def test_scrape_excel_url():
    """Test HTML scraping regex for extracting direct .xlsx links."""
    client = JiraClient()
    
    mock_html = """
    <html>
        <body>
            <div class="download-section">
                <a href="https://repository.impact-initiatives.org/resources/download/Ukraine_JMMI_R40.xlsx">Download Dataset</a>
            </div>
        </body>
    </html>
    """
    
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_session.get.return_value = mock_resp
    client.repo_session = mock_session

    excel_url = client._scrape_excel_url("https://repository.impact-initiatives.org/Ukraine_JMMI_R40_page")

    assert excel_url == "https://repository.impact-initiatives.org/resources/download/Ukraine_JMMI_R40.xlsx"


@patch("jira_client.JiraClient.download_proforma_attachment")
@patch("jira_client.JiraClient.get_issue_id")
@patch("jira_client.JiraClient.get_proforma_answers")
@patch("jira_client.JiraClient._scrape_excel_url")
@patch("jira_client.JiraClient._get_repo_session")
@patch("jira_client.JiraClient._download_file_with_retry")
def test_resolve_dataset_workflow(mock_download_file, mock_repo_session, mock_scrape_url, mock_proforma, mock_issue_id, mock_download_att):
    """Test unified fallback priority resolver strategy."""
    client = JiraClient()
    tmp_path = Path("/tmp/mock-dir")
    
    # ──── Case A: Direct Attachment  ────
    mock_download_att.return_value = Path("/tmp/mock-dir/attachment.xlsx")
    
    resolved_path = client.resolve_dataset("RQA-123", tmp_path)
    assert resolved_path == Path("/tmp/mock-dir/attachment.xlsx")
    
    mock_issue_id.assert_not_called()
    
    # ──── Case B: ProForma & Repository Scraping ────
    mock_download_att.return_value = None  
    mock_issue_id.return_value = "10400"
    mock_proforma.return_value = {
        "IMPACT Repository": "https://repository.impact-initiatives.org/Ukraine_JMMI_R40"
    }
    mock_scrape_url.return_value = "https://repository.impact-initiatives.org/Ukraine_JMMI_R40.xlsx"
    mock_download_file.return_value = True

    resolved_path = client.resolve_dataset("RQA-123", tmp_path)
    assert resolved_path == tmp_path / "Ukraine_JMMI_R40.xlsx"
    
    mock_issue_id.assert_called_once_with("RQA-123")
    mock_proforma.assert_called_once_with("10400")
    mock_scrape_url.assert_called_once_with("https://repository.impact-initiatives.org/Ukraine_JMMI_R40")
    mock_download_file.assert_called_once()
