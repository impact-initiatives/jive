import datetime
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.config import get_settings, reload_settings

from .helpers import set_default_env_vars

set_default_env_vars()

from ..worker.models import (  # noqa: E402
    JiraSubmissionPayload,
    MetadataModel,
    PipelineResponse,
    SummaryModel,
)
from ..worker.worker_utils import (  # noqa: E402
    check_idempotency,
    download_dataset,
    publish_results,
    resolve_context,
    run_validation,
)
from .helpers import make_attachment  # noqa: E402


@pytest.fixture
def mock_jira_client():
    return MagicMock()


@pytest.fixture
def mock_proforma():
    proforma = MagicMock()
    proforma.dataset_type_label = "Dataset type"
    proforma.repo_label = "IMPACT Repository"
    return proforma


@pytest.fixture
def mock_impact_repo():
    return MagicMock()


@pytest.fixture
def payload():
    return JiraSubmissionPayload(issue_key="TEST-123", dataset_type="jmmi_dataset")


@pytest.fixture
def payload_split_dataset():
    return JiraSubmissionPayload(
        issue_key="TEST-123", type_of_programme="jmmi", type_of_output="Quant Dataset"
    )


def test_check_idempotency_no_report(payload: JiraSubmissionPayload):
    attachments = make_attachment(filename="some_dataset.xlsx", created="2026-05-28T10:00:00Z")
    assert check_idempotency(payload, [attachments]) is False


def test_check_idempotency_report_older_than_dataset(payload: JiraSubmissionPayload):

    attachments = [
        make_attachment(filename="some_dataset.xlsx", created="2026-05-28T10:00:00Z"),
        make_attachment(
            filename="JIVE_Validation_Report_TEST-123.xlsx", created="2026-05-27T10:00:00Z"
        ),
    ]

    assert check_idempotency(payload, attachments) is False


def test_check_idempotency_report_newer_than_dataset(payload: JiraSubmissionPayload):

    attachments = [
        make_attachment(filename="some_dataset.xlsx", created="2026-05-27T10:00:00Z"),
        make_attachment(
            filename="JIVE_Validation_Report_TEST-123.xlsx", created="2026-05-28T10:00:00Z"
        ),
    ]
    assert check_idempotency(payload, attachments) is True


def test_check_idempotency_force_flag(payload: JiraSubmissionPayload):
    payload.force_revalidation = True

    attachments = [
        make_attachment(filename="some_dataset.xlsx", created="2026-05-27T10:00:00Z"),
        make_attachment(
            filename="JIVE_Validation_Report_TEST-123.xlsx", created="2026-05-28T10:00:00Z"
        ),
    ]
    # Even though report is newer, force flag bypasses
    assert check_idempotency(payload, attachments) is False


def test_check_idempotency_external_link_prevent_loop(payload: JiraSubmissionPayload):

    attachments = [
        make_attachment(
            filename="JIVE_Validation_Report_TEST-123.xlsx", created="2026-05-28T10:00:00Z"
        )
    ]
    # No datasets found but report exists => skip to prevent loop
    assert check_idempotency(payload, attachments) is True


def test_download_dataset_success(
    mock_jira_client: MagicMock,
    mock_proforma: MagicMock,
    mock_impact_repo: MagicMock,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
):
    with patch("src.worker.worker_utils.resolve_dataset") as mock_resolve:
        mock_resolve.return_value = tmp_path / "test.xlsx"
        result = download_dataset(
            mock_jira_client, mock_proforma, mock_impact_repo, payload, tmp_path, "1000", [], {}
        )
        assert result == tmp_path / "test.xlsx"
        mock_jira_client.post_comment.assert_not_called()


def test_download_dataset_failure(
    mock_jira_client: MagicMock,
    mock_proforma: MagicMock,
    mock_impact_repo: MagicMock,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
):
    from ..worker.worker_utils import DatasetResolutionError

    with patch("src.worker.worker_utils.resolve_dataset") as mock_resolve:
        mock_resolve.return_value = None
        with pytest.raises(DatasetResolutionError):
            _ = download_dataset(
                mock_jira_client, mock_proforma, mock_impact_repo, payload, tmp_path, "1000", [], {}
            )
        mock_jira_client.post_comment.assert_called_once()


def test_resolve_context_default(mock_proforma: MagicMock, payload: JiraSubmissionPayload):
    dt, repo, action = resolve_context(mock_proforma, payload, "1000", {})
    assert dt == "jmmi_dataset"
    assert repo is None
    assert action is None


def test_resolve_context_default_split_dataset(
    mock_proforma: MagicMock, payload_split_dataset: JiraSubmissionPayload
):
    dt, repo, action = resolve_context(mock_proforma, payload_split_dataset, "1000", {})
    assert dt == "jmmi_dataset"
    assert repo is None
    assert action is None


def test_resolve_context_with_proforma(mock_proforma: MagicMock, payload: JiraSubmissionPayload):
    answers = {
        "Dataset type": "MSNA",
        "Link to the resource": "https://repository.example.com/msna",
        "Published or archived": "Archived",
    }
    dt, repo, action = resolve_context(mock_proforma, payload, "1000", answers)
    assert dt == "msna"
    assert repo == "https://repository.example.com/msna"
    assert action == "Archived"


@patch("src.worker.worker_utils.ValidationPipeline")
def test_run_validation(
    mock_pipeline_class: MagicMock, payload: JiraSubmissionPayload, tmp_path: Path
):
    mock_pipeline_instance: MagicMock = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline_instance
    mock_pipeline_instance.run_all.return_value = {
        "success": True,
        "summary": {
            "passed": True,
            "admin_errors": 0,
            "admin_info": 0,
            "errors": 0,
            "warnings": 0,
            "info": 0,
        },
        "metadata": {"dataset_type": "msna"},
        "warnings": [],
        "errors": [],
        "info": [],
        "admin_errors": [],
        "admin_info": [],
    }

    result = run_validation(tmp_path / "data.xlsx", "msna", payload)

    mock_pipeline_instance.run_all.assert_called_with(
        filepath=tmp_path / "data.xlsx", dataset_type="msna"
    )
    mock_pipeline_instance.run_all.assert_called_once()
    assert isinstance(result, PipelineResponse)


def test_publish_results_small_file(
    mock_jira_client: MagicMock, payload: JiraSubmissionPayload, tmp_path: Path
):
    response = PipelineResponse.model_construct(
        success=True,
        summary=SummaryModel(
            passed=True, admin_errors=0, errors=0, warnings=0, info=0, admin_info=0
        ),
        metadata=MetadataModel(
            dataset_type="msna",
            file_name="report.xlsx",
            validation_date=datetime.datetime.now().isoformat(),
            version="2026010100",
        ),
        warnings=[],
        errors=[],
        info=[],
        admin_errors=[],
    )
    report_file = tmp_path / "report.xlsx"
    _ = report_file.write_text("dummy content")  # very small

    mock_jira_client.upload_public_jsm_attachment.return_value = True
    payload.project_key = "RQA"

    publish_results(mock_jira_client, payload, response, report_file, None, None, "jmmi")

    mock_jira_client.upload_public_jsm_attachment.assert_called_once_with(
        "TEST-123", "RQA", report_file
    )
    mock_jira_client.post_comment.assert_called_once()


def test_publish_results_large_file(
    mock_jira_client: MagicMock, payload: JiraSubmissionPayload, tmp_path: Path
):
    response = PipelineResponse.model_construct(
        success=True,
        summary={"total_errors": 0, "total_warnings": 0},
        metadata=MetadataModel(
            dataset_type="msna",
            file_name="report.xlsx",
            validation_date=datetime.datetime.now().isoformat(),
            version="2026010100",
        ),
        warnings=[],
        errors=[],
        info=[],
        admin_errors=[],
    )
    report_file = tmp_path / "report.xlsx"

    reload_settings()
    set_default_env_vars()
    os.environ["JIVE_MAX_ATTACHMENT_MB"] = "0"
    mock_jira_client.settings = get_settings()

    from src.worker import worker_utils

    worker_utils.settings = get_settings()

    _ = report_file.write_text("dummy content")
    publish_results(mock_jira_client, payload, response, report_file, None, None, "jmmi_dataset")

    mock_jira_client.upload_public_jsm_attachment.assert_not_called()
    mock_jira_client.upload_attachment.assert_not_called()

    # Check if the warning text is in the posted comment
    args, kwargs = mock_jira_client.post_comment.call_args
    comment_content = str(args[1])
    assert "exceeds the Jira attachment limit" in comment_content


@patch("src.worker.worker_utils.ValidationPipeline")
def test_run_validation_minor_schema_mismatch(
    mock_pipeline_class: MagicMock, payload: JiraSubmissionPayload, tmp_path: Path
):
    mock_pipeline_instance = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline_instance
    # Simulates an output containing unexpected extra keys and some missing fields that Pydantic
    #  would normally reject
    mock_pipeline_instance.run_all.return_value = {
        "success": True,
        "unexpected_new_field": "some_value",
        "errors": [{"severity": "error", "rule": "E2", "message": "Schema test"}],
        "summary": {
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "admin_errors": 0,
            "admin_info": 0,
            "passed": True,
        },
        "metadata": {
            "dataset_type": "jmmi_dataset",
            "validation_date": "2023-01-01T00:00:00Z",
            "version": "1.0.0",
            "file_name": "report.xlsx",
        },
        # warnings, info, admin_errors are missing
    }

    result = run_validation(tmp_path / "data.xlsx", "msna_dataset", payload)

    assert isinstance(result, PipelineResponse)
    assert result.success is True
    # Verify Pydantic fallback bypassed validation and constructed lists correctly
    assert len(result.errors) == 1
    assert result.errors[0].rule == "E2"
    assert result.warnings == []


@patch("src.worker.worker_utils.ValidationPipeline")
def test_run_validation_major_schema_mismatch(
    mock_pipeline_class: MagicMock, payload: JiraSubmissionPayload, tmp_path: Path
):
    mock_pipeline_instance = MagicMock()
    mock_pipeline_class.return_value = mock_pipeline_instance
    # Simulates a completely broken response format (string instead of dict)
    mock_pipeline_instance.run_all.return_value = "This is a string not a dict"

    result = run_validation(tmp_path / "data.xlsx", "msna", payload)

    assert isinstance(result, PipelineResponse)
    assert result.success is False
    assert len(result.admin_errors) == 1
    assert result.admin_errors[0]["rule"] == "JIVE_SCHEMA_MISMATCH"
    assert "schema format error" in result.admin_errors[0]["message"]
