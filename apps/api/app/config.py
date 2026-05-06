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
    session_cookie_name: str = Field(default="miaf_session", alias="SESSION_COOKIE_NAME")
    session_ttl_hours: int = Field(default=24 * 14, alias="SESSION_TTL_HOURS")  # 14 days
    cors_allow_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ALLOW_ORIGINS")
    login_rate_limit_window_minutes: int = Field(default=15, alias="LOGIN_RATE_LIMIT_WINDOW_MINUTES")
    login_rate_limit_attempts: int = Field(default=5, alias="LOGIN_RATE_LIMIT_ATTEMPTS")
    agent_rate_limit_window_seconds: int = Field(default=60, alias="AGENT_RATE_LIMIT_WINDOW_SECONDS")
    agent_rate_limit_attempts: int = Field(default=30, alias="AGENT_RATE_LIMIT_ATTEMPTS")

    # Per-IP rate limiting (applied via middleware to auth + agent hot paths)
    ip_rate_limit_window_seconds: int = Field(default=60, alias="IP_RATE_LIMIT_WINDOW_SECONDS")
    ip_rate_limit_requests: int = Field(default=120, alias="IP_RATE_LIMIT_REQUESTS")

    # Telegram
    telegram_webhook_secret: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")

    # Internal automation
    automation_token: str | None = Field(default=None, alias="AUTOMATION_TOKEN")

    # Tailscale
    tailscale_binary_path: str = Field(default="/usr/bin/tailscale", alias="TAILSCALE_BINARY_PATH")
    tailscale_command_timeout: int = Field(default=10, alias="TAILSCALE_COMMAND_TIMEOUT")
    # Comma-separated list of ports allowed as Tailscale Serve targets (localhost only).
    tailscale_allowed_ports: str = Field(default="80", alias="TAILSCALE_ALLOWED_PORTS")

    @property
    def tailscale_allowed_ports_set(self) -> set[int]:
        ports: set[int] = set()
        for part in self.tailscale_allowed_ports.split(","):
            try:
                ports.add(int(part.strip()))
            except ValueError:
                pass
        return ports

    @property
    def session_cookie_secure(self) -> bool:
        return self.environment == "production"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
