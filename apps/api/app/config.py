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

    # Auth / sessions
    session_cookie_name: str = Field(default="finclaw_session", alias="SESSION_COOKIE_NAME")
    session_ttl_hours: int = Field(default=24 * 14, alias="SESSION_TTL_HOURS")  # 14 days
    cors_allow_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ALLOW_ORIGINS")
    login_rate_limit_window_minutes: int = Field(default=15, alias="LOGIN_RATE_LIMIT_WINDOW_MINUTES")
    login_rate_limit_attempts: int = Field(default=5, alias="LOGIN_RATE_LIMIT_ATTEMPTS")

    @property
    def session_cookie_secure(self) -> bool:
        return self.environment == "production"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
