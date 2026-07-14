import pytest

from ..worker.models import JiraSubmissionPayload


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure env vars are set for JiraClient initialization."""
    monkeypatch.setenv("JIRA_API_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIVE_MAX_ATTACHMENT_MB", "250")
    monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
    monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
    monkeypatch.setenv("ALLOWED_DOMAINS", "repository.impact-initiatives.org,test.atlassian.net")


class TestJiraSubmissionPayload:
    """Tests for the JiraSubmissionPayload Pydantic model."""

    def test_valid_payload(self):
        payload = JiraSubmissionPayload(
            issue_key="RQA-123",
            project_key="RQA",
            rcid="RCID-456",
            dataset_type="jmmi",
        )
        assert payload.issue_key == "RQA-123"
        assert payload.project_key == "RQA"
        assert payload.rcid == "RCID-456"
        assert payload.dataset_type == "jmmi"

    def test_minimal_payload_only_issue_key(self):
        payload = JiraSubmissionPayload(issue_key="RQA-001")
        assert payload.issue_key == "RQA-001"
        assert payload.project_key == ""
        assert payload.rcid == ""
        assert payload.dataset_type == ""

    def test_missing_issue_key_raises(self):
        with pytest.raises(ValueError):
            JiraSubmissionPayload()

    def test_dataset_type_dropdown_dict(self):
        """Jira Automation sends dropdowns as {"value": "JMMI"} objects."""
        payload = JiraSubmissionPayload(
            issue_key="RQA-200",
            dataset_type={"value": "JMMI"},
        )
        assert payload.dataset_type == "jmmi"

    def test_dataset_type_string_uppercased(self):
        payload = JiraSubmissionPayload(
            issue_key="RQA-201",
            dataset_type="JMMI",
        )
        assert payload.dataset_type == "jmmi"

    def test_extra_fields_ignored(self):
        """Extra fields from Jira should not cause validation errors."""
        payload = JiraSubmissionPayload(
            issue_key="RQA-300",
            unknown_field="some_value",
            another_field=42,
        )
        assert payload.issue_key == "RQA-300"
        assert not hasattr(payload, "unknown_field")

    def test_serialization_roundtrip(self):
        payload = JiraSubmissionPayload(
            issue_key="RQA-400",
            project_key="RQA",
            rcid="RCID-789",
            dataset_type="jmmi",
        )
        json_str = payload.model_dump_json()
        restored = JiraSubmissionPayload.model_validate_json(json_str)
        assert restored.issue_key == payload.issue_key
        assert restored.dataset_type == payload.dataset_type
