from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings


def _clean_url(v: str) -> str:
    return v.rstrip("/")


BaseUrl = Annotated[str, AfterValidator(_clean_url)]


class Settings(BaseSettings):
    jira_auth_type: Literal["basic", "token"] = Field(alias="JIRA_AUTH_TYPE", default="basic")
    jira_cloud_id: str = Field(alias="JIRA_CLOUD_ID")
    jira_api_email: str = Field(alias="JIRA_API_EMAIL", default="")
    jira_api_token: str = Field(alias="JIRA_API_TOKEN")
    jira_api_base_url: BaseUrl = Field(alias="JIRA_API_BASE_URL")
    retry_status_codes: set[int] = {429, 500, 502, 503, 504}
    secure_link_username: str = Field(alias="SECURE_LINK_USERNAME", default="")
    secure_link_password: str = Field(alias="SECURE_LINK_PASSWORD", default="")
    max_attachment_size: int = Field(alias="JIVE_MAX_ATTACHMENT_MB", default=250)
    max_retries: int = Field(alias="JIVE_MAX_RETRIES", default=3)
    allowed_domains: str | frozenset[str] = Field(alias="ALLOWED_DOMAINS", default="")
    proforma_repository_label: str = Field(alias="PROFORMA_REPO_LABEL", default="IMPACT Repository")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process; subsequent calls return the same object."""
    return Settings()


def reload_settings() -> None:
    """Reset cached settings (for testing)."""
    get_settings.cache_clear()
