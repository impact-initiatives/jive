from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # model_config: SettingsConfigDict = SettingsConfigDict(
    #     env_file=".env",
    #     env_ignore_empty=True,
    #     extra="ignore",
    # )

    queue_connection_string: str = Field(alias="AZURE_STORAGE_CONNECTION_STRING")
    queue_name: str = "jive-validation-queue"
    max_attachment_size: int = Field(alias="JIVE_MAX_ATTACHMENT_MB", default=250)
    max_retries: int = Field(alias="JIVE_MAX_RETRIES", default=3)
    force_validation: bool = Field(alias="JIVE_FORCE_VALIDATION", default=False)

    max_excel_errors: int = Field(alias="MAX_EXCEL_ERRORS", default=50000)

    jive_documentation: dict[str, dict[str, str]] = Field(
        default_factory=dict, alias="JIVE_DOCUMENTATION"
    )

    jive_version_file: str = Field(alias="JIVE_VERSION_FILE", default="/app/jive_version.txt")

    @computed_field
    @property
    def jive_version(self) -> str:
        try:
            with open(self.jive_version_file) as f:
                return f.read().strip()
        except Exception:
            return "unknown"

    @property
    def parsed_allowed_domains(self) -> frozenset[str]:
        """Return domains as frozenset."""
        return frozenset(filter(None, self.allowed_domains.split(",")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process; subsequent calls return the same object."""
    return Settings()


def reload_settings() -> None:
    """Reset cached settings (for testing)."""
    get_settings.cache_clear()
