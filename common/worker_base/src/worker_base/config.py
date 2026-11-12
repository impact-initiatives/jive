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

    max_attachment_size: int = Field(alias="JIVE_MAX_ATTACHMENT_MB", default=250)
    max_retries: int = Field(alias="JIVE_MAX_RETRIES", default=3)

    repository_username: str = Field(alias="REPO_USERNAME", default="")
    repository_password: str = Field(alias="REPO_PASSWORD", default="")
    repository_session_ttl: int = Field(alias="REPO_SESSION_TTL_SECONDS", default=43200)
    allowed_domains: str | frozenset[str] = Field(alias="ALLOWED_DOMAINS", default="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process; subsequent calls return the same object."""
    return Settings()
