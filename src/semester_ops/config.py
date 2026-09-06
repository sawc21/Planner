from functools import lru_cache
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SEMOPS_",
        extra="ignore",
    )

    database_path: Path = Path("var/semester-ops.db")
    timezone: str = "America/Chicago"
    base_url: str = "http://127.0.0.1:8000"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    secret_key: str = "semester-ops-local-development"
    google_client_secret_file: Path | None = None
    google_token_file: Path = Path("var/google-token.json")
    google_calendar_id: str | None = None
    google_sync_write_limit: int = Field(default=50, ge=1, le=250)
    google_initial_sync_write_limit: int = Field(default=1, ge=1, le=250)
    blackboard_ics_url: str | None = None

    @model_validator(mode="after")
    def validate_google_sync_limits(self) -> Self:
        if self.google_initial_sync_write_limit > self.google_sync_write_limit:
            raise ValueError(
                "google_initial_sync_write_limit cannot exceed google_sync_write_limit"
            )
        return self

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("base_url must be an http(s) origin without credentials or a path")
        return normalized

    @field_validator("host")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Semester Ops v1 may bind only to a loopback host")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
