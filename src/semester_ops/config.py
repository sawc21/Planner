from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
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
    blackboard_ics_url: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("host")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Semester Ops v1 may bind only to a loopback host")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
