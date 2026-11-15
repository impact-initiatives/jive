from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # model_config: SettingsConfigDict = SettingsConfigDict(
    #     env_file=".env",
    #     env_ignore_empty=True,
    #     extra="ignore",
    # )

    queue_connection_string: str = Field(alias="AZURE_STORAGE_CONNECTION_STRING")

    api_key: str = Field(
        alias="JIVE_API_KEY",
    )

    secure_link_username: str = Field(alias="SECURE_LINK_USERNAME", default="")
    secure_link_password: str = Field(alias="SECURE_LINK_PASSWORD", default="")


settings = Settings()
