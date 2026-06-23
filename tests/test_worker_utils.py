import pytest
from unittest.mock import MagicMock, patch
from worker_utils import (
    check_idempotency,
    download_dataset,
    resolve_context,
    run_validation,
    publish_results
)
from models import JiraSubmissionPayload
from rqa_validator.models.api_models import PipelineResponse


@pytest.fixture
def mock_jira_client():
    return MagicMock()


@pytest.fixture
def payload():
    return JiraSubmissionPayload(issue_key="TEST-123", dataset_type="jmmi")


def test_check_idempotency_no_report(payload):
    attachments = [{"filename": "some_dataset.xlsx", "created": "2026-05-28T10:00:00Z"}]
    assert check_idempotency(payload, attachments) is False


def test_check_idempotency_report_older_than_dataset(payload):
    attachments = [
        {"filename": "some_dataset.xlsx", "created": "2026-05-28T10:00:00Z"},
        {"filename": "JIVE_Validation_Report_TEST-123.xlsx", "created": "2026-05-27T10:00:00Z"}
    ]
    assert check_idempotency(payload, attachments) is False


def test_check_idempotency_report_newer_than_dataset(payload):
    attachments = [
        {"filename": "some_dataset.xlsx", "created": "2026-05-27T10:00:00Z"},
        {"filename": "JIVE_Validation_Report_TEST-123.xlsx", "created": "2026-05-28T10:00:00Z"}
    ]
    assert check_idempotency(payload, attachments) is True


def test_check_idempotency_force_flag(payload):
    payload.force_revalidation = True
    attachments = [
        {"filename": "some_dataset.xlsx", "created": "2026-05-27T10:00:00Z"},
        {"filename": "JIVE_Validation_Report_TEST-123.xlsx", "created": "2026-05-28T10:00:00Z"}
    ]
    # Even though report is newer, force flag bypasses
    assert check_idempotency(payload, attachments) is False


def test_check_idempotency_external_link_prevent_loop(payload):
    attachments = [
        {"filename": "JIVE_Validation_Report_TEST-123.xlsx", "created": "2026-05-28T10:00:00Z"}
    ]
    # No datasets found but report exists => skip to prevent loop
    assert check_idempotency(payload, attachments) is True


def test_download_dataset_success(mock_jira_client, payload, tmp_path):
    mock_jira_client.resolve_dataset.return_value = tmp_path / "test.xlsx"
    result = download_dataset(mock_jira_client, payload, tmp_path, "1000", [], {})
    assert result == tmp_path / "test.xlsx"
    mock_jira_client.post_comment.assert_not_called()


def test_download_dataset_failure(mock_jira_client, payload, tmp_path):
    mock_jira_client.resolve_dataset.return_value = None
    result = download_dataset(mock_jira_client, payload, tmp_path, "1000", [], {})
    assert result is None
    mock_jira_client.post_comment.assert_called_once()


def test_resolve_context_default(mock_jira_client, payload):
    dt, repo, action = resolve_context(mock_jira_client, payload, "1000", {})
    assert dt == "jmmi"
    assert repo is None
    assert action is None


def test_resolve_context_with_proforma(mock_jira_client, payload):
    mock_jira_client.proforma_dataset_type_label = "Dataset type"
    answers = {
        "Dataset type": "MSNA",
        "Link to the resource": "https://repository.example.com/msna",
        "Published or archived": "Archived"
    }
    dt, repo, action = resolve_context(mock_jira_client, payload, "1000", answers)
    assert dt == "msna"
    assert repo == "https://repository.example.com/msna"
    assert action == "Archived"


@patch("worker_utils.ValidationPipeline")
def test_run_validation(mock_pipeline_class, payload, tmp_path):
    mock_pipeline_instance = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline_instance
    mock_pipeline_instance.run.return_value = {
        "success": True,
        "summary": {"passed": True, "admin_errors": 0, "errors": 0, "warnings": 0, "info": 0},
        "metadata": {"dataset_type": "msna"},
        "warnings": [], 
        "errors": [], 
        "info": [], 
        "admin_errors": []
    }
    
    result = run_validation(tmp_path / "data.xlsx", "msna", payload)
    
    mock_pipeline_class.assert_called_with(dataset_type="msna")
    mock_pipeline_instance.run.assert_called_once()
    assert isinstance(result, PipelineResponse)


def test_publish_results_small_file(mock_jira_client, payload, tmp_path):
    response = PipelineResponse.model_construct(
        success=True,
        summary={"passed": True, "admin_errors": 0, "errors": 0, "warnings": 0, "info": 0},
        metadata={"dataset_type": "msna"},
        warnings=[], 
        errors=[], 
        info=[], 
        admin_errors=[]
    )
    report_file = tmp_path / "report.xlsx"
    report_file.write_text("dummy content")  # very small
    
    mock_jira_client.upload_public_jsm_attachment.return_value = True
    payload.project_key = "RQA"
    
    publish_results(mock_jira_client, payload, response, report_file, None, None, "jmmi")
    
    mock_jira_client.upload_public_jsm_attachment.assert_called_once_with("TEST-123", "RQA", report_file)
    mock_jira_client.post_comment.assert_called_once()


def test_publish_results_large_file(mock_jira_client, payload, tmp_path):
    response = PipelineResponse.model_construct(
        success=True,
        summary={"total_errors": 0, "total_warnings": 0},
        metadata={"dataset_type": "msna"},
        warnings=[], 
        errors=[], 
        info=[], 
        admin_errors=[]
    )
    report_file = tmp_path / "report.xlsx"
    
    with patch("worker_utils.MAX_JIRA_ATTACHMENT_MB", 0):  # Force large file logic
        report_file.write_text("dummy content")
        publish_results(mock_jira_client, payload, response, report_file, None, None, "jmmi")
        
        mock_jira_client.upload_public_jsm_attachment.assert_not_called()
        mock_jira_client.upload_attachment.assert_not_called()
        
        # Check if the warning text is in the posted comment
        args, kwargs = mock_jira_client.post_comment.call_args
        comment_content = str(args[1])
        assert "exceeds the Jira attachment limit" in comment_content
