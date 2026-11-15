from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker_base.dataset_utils import DatasetResolutionError, download_dataset
from worker_base.models import JiraSubmissionPayload


@pytest.fixture
def mock_jira_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_proforma() -> MagicMock:
    proforma = MagicMock()
    proforma.dataset_type_label = "Dataset type"
    proforma.repo_label = "IMPACT Repository"
    return proforma


@pytest.fixture
def mock_impact_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def payload():
    return JiraSubmissionPayload(
        issue_key="TEST-123",
        programme_type="jmmi",
        output_type="dataset",
    )


def test_download_dataset_success(
    mock_jira_client: MagicMock,
    mock_proforma: MagicMock,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
):
    with patch("worker_base.dataset_utils.resolve_dataset") as mock_resolve:
        mock_resolve.return_value = tmp_path / "test.xlsx"
        result = download_dataset(
            mock_jira_client,
            mock_proforma,
            payload,
            tmp_path,
            "1000",
            [],
            {},
        )
        assert result == tmp_path / "test.xlsx"
        mock_jira_client.post_comment.assert_not_called()


def test_download_dataset_failure(
    mock_jira_client: MagicMock,
    mock_proforma: MagicMock,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
):

    with patch("worker_base.dataset_utils.resolve_dataset") as mock_resolve:
        mock_resolve.return_value = None
        with pytest.raises(DatasetResolutionError):
            _ = download_dataset(
                mock_jira_client,
                mock_proforma,
                payload,
                tmp_path,
                "1000",
                [],
                {},
            )
        mock_jira_client.post_comment.assert_called_once()
