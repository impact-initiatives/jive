from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # model_config: SettingsConfigDict = SettingsConfigDict(
    #     env_file=".env",
    #     env_ignore_empty=True,
    #     extra="ignore",
    # )

    queue_connection_string: str = Field(alias="AZURE_STORAGE_CONNECTION_STRING")
    queue_name: str = Field(
        default="jive-validation-queue",
        alias="JIVE_QUEUE_NAME",
    )
    api_key: str = Field(
        alias="JIVE_API_KEY",
    )

    max_attachment_size: int = Field(alias="JIVE_MAX_ATTACHMENT_MB", default=250)
    max_retries: int = Field(alias="JIVE_MAX_RETRIES", default=3)
    force_validation: bool = Field(alias="JIVE_FORCE_VALIDATION", default=False)

    max_excel_errors: int = Field(alias="MAX_EXCEL_ERRORS", default=50000)

    allowed_domains: str | frozenset[str] = Field(alias="ALLOWED_DOMAINS", default="")

    repository_username: str = Field(alias="REPO_USERNAME", default="")
    repository_password: str = Field(alias="REPO_PASSWORD", default="")
    repository_session_ttl: int = Field(alias="REPO_SESSION_TTL_SECONDS", default=43200)

    proforma_repository_label: str = Field(alias="PROFORMA_REPO_LABEL", default="IMPACT Repository")
    proforma_dataset_type_label: str = Field(
        alias="PROFORMA_DATASET_TYPE_LABEL", default="Dataset type"
    )
    jive_documentation: Json[list[dict[str, str]]] = Field(default_factory=list, alias="JIVE_DOCUMENTATION")

    jira_api_email: str = Field(alias="JIRA_API_EMAIL")
    jira_api_token: str = Field(alias="JIRA_API_TOKEN")
    jira_base_url: str = Field(alias="JIRA_BASE_URL")

    secure_link_username: str = Field(alias="SECURE_LINK_USERNAME", default="")
    secure_link_password: str = Field(alias="SECURE_LINK_PASSWORD", default="")

    def parsed_allowed_domains(self) -> frozenset[str]:
        """Return domains as frozenset."""
        return frozenset(filter(None, self.allowed_domains.split(",")))


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Lazy load settings on first access."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        _settings_instance.allowed_domains = _settings_instance.parsed_allowed_domains()
    return _settings_instance


def reload_settings():
    """Reset cached settings (for testing)."""
    global _settings_instance
    _settings_instance = None
