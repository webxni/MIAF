from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    environment: Literal["development", "production", "test"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    secret_key: str = Field(alias="SECRET_KEY")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
