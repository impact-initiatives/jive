import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..worker.main import process_message
from ..worker.models import JiraSubmissionPayload
from .helpers import set_default_env_vars

set_default_env_vars()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(str(project_root.parent / "argus"))


@patch("src.worker.main.JiraClient")
@patch("src.worker.main.ProformaParser")
@patch("src.worker.main.ImpactRepoClient")
@patch("src.worker.main.download_dataset")
@patch("src.worker.worker_utils.ValidationPipeline")
@patch("src.worker.main.export_response_to_excel")
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
    mock_pipeline.run_all.return_value = {
        "success": True,
        "metadata": {
            "dataset_type": "jmmi_dataset",
            "validation_date": "2023-01-01T00:00:00Z",
            "version": "1.0.0",
            "file_name": "report.xlsx",
        },
        "summary": {
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "admin_errors": 0,
            "admin_info": 0,
            "passed": True,
        },
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

    payload = JiraSubmissionPayload(**payload_data)

    with patch("src.worker.main.Path") as mock_path_cls:
        mock_tmp_path = MagicMock()
        mock_tmp_path.__truediv__ = lambda self, other: mock_excel_path
        mock_path_cls.return_value = mock_tmp_path

        process_message(mock_msg, payload)

    mock_jira.get_attachments.assert_called_once()
    mock_download_dataset.assert_called_once()
    mock_pipeline.run_all.assert_called_once()
    mock_export.assert_called_once()
    mock_jira.post_comment.assert_called_once()
