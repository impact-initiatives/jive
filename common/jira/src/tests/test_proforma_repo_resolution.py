import sys
from pathlib import Path

import pytest

from jira.jira_client import JiraClient
from jira.proforma_parser import ProformaParser

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def jira_client():
    return JiraClient()


def test_get_proforma_answers(httpx2_mock, jira_client: JiraClient):
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
    client = ProformaParser(jira_client.session)

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
