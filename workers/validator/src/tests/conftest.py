import pytest

from validator.config import reload_settings


@pytest.fixture(autouse=True)
def set_default_env_vars(monkeypatch):

    reload_settings()

    # print(f"BEFORE FIXTURE: JIRA_CLOUD_ID={os.environ.get('JIRA_CLOUD_ID')}")

    monkeypatch.setenv("JIRA_API_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_CLOUD_ID", "mock-cloud-id-12345")
    monkeypatch.setenv("JIRA_API_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "basic")
    monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
    monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
    monkeypatch.setenv("ALLOWED_DOMAINS", "repository.impact-initiatives.org,test.atlassian.net")
    monkeypatch.setenv("JIVE_API_KEY", "secure-pass")
    monkeypatch.setenv("JIVE_DOCUMENTATION", '{"jive":{"doco":"url"}}')

    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=mock;AccountKey=mock;EndpointSuffix=core.windows.net",
    )
    monkeypatch.setenv("REPO_USERNAME", "mock-wp-username@example.com")
    monkeypatch.setenv("REPO_PASSWORD", "mock-wp-password")

    # print(f"AFTER PATCH: JIRA_CLOUD_ID={os.environ.get('JIRA_CLOUD_ID')}")

    # reload_settings()
    # get_settings()

    # print(f"AFTER RELOAD: JIRA_CLOUD_ID={os.environ.get('JIRA_CLOUD_ID')}")

    # yield

    # reload_settings()
