import os

import pytest

from jira.config import reload_settings

# to prevent module errors about to values not being set leading to test import errors
os.environ.setdefault("JIRA_API_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "test-token")
os.environ.setdefault("JIRA_CLOUD_ID", "mock-cloud-id-12345")
os.environ.setdefault("JIRA_API_BASE_URL", "https://test.atlassian.net")
os.environ.setdefault("JIRA_AUTH_TYPE", "basic")
os.environ.setdefault("SECURE_LINK_USERNAME", "secure-user")
os.environ.setdefault("SECURE_LINK_PASSWORD", "secure-pass")
os.environ.setdefault(
    "ALLOWED_DOMAINS", "repository.impact-initiatives.org,test.atlassian.net"
)


os.environ.setdefault("REPO_USERNAME", "mock-wp-username@example.com")
os.environ.setdefault("REPO_PASSWORD", "mock-wp-password")


@pytest.fixture(autouse=True)
def set_default_env_vars(monkeypatch):

    reload_settings()

    monkeypatch.setenv("JIRA_API_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_CLOUD_ID", "mock-cloud-id-12345")
    monkeypatch.setenv("JIRA_API_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "basic")
    monkeypatch.setenv("SECURE_LINK_USERNAME", "secure-user")
    monkeypatch.setenv("SECURE_LINK_PASSWORD", "secure-pass")
    monkeypatch.setenv(
        "ALLOWED_DOMAINS", "repository.impact-initiatives.org,test.atlassian.net"
    )

    monkeypatch.setenv("REPO_USERNAME", "mock-wp-username@example.com")
    monkeypatch.setenv("REPO_PASSWORD", "mock-wp-password")
