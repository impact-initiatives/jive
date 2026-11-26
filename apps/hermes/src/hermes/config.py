from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jive_version: str = Field(alias="JIVE_VERSION", default="Not Specified")
    jive_documentation: dict[str, dict[str, str]] = Field(
        default_factory=dict, alias="JIVE_DOCUMENTATION"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process; subsequent calls return the same object."""
    return Settings()
