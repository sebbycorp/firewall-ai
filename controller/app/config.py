from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    store_backend: str = Field(default="memory")
    gcp_project: str = Field(default="firewall-ai")
    enrollment_key: str = Field(default="")
    admin_token: str = Field(default="")
    offline_after_sec: int = Field(default=120)
    port: int = Field(default=8080)


@lru_cache
def get_settings() -> Settings:
    return Settings()
