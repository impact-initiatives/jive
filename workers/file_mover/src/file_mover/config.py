from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # model_config: SettingsConfigDict = SettingsConfigDict(
    #     env_file=".env",
    #     env_ignore_empty=True,
    #     extra="ignore",
    # )

    queue_connection_string: str = Field(alias="AZURE_STORAGE_CONNECTION_STRING")
    queue_name: str = "jive-file-mover-queue"
    storage_container_name: str = Field(
        default="validated-files",
        alias="JIVE_STORAGE_CONTAINER_NAME",
    )

    max_attachment_size: int = Field(alias="JIVE_MAX_ATTACHMENT_MB", default=250)
    max_retries: int = Field(alias="JIVE_MAX_RETRIES", default=3)

    allowed_domains: str | frozenset[str] = Field(alias="ALLOWED_DOMAINS", default="")

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
