from __future__ import annotations

import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from sqlalchemy.orm import Session

from semester_ops.config import Settings, get_settings
from semester_ops.db.models import AppSettings
from semester_ops.db.session import session_scope
from semester_ops.integrations.google_calendar.gateway import (
    GoogleCalendarError,
    GoogleCalendarGateway,
)


class GoogleSetupError(RuntimeError):
    """A safe, user-actionable setup error."""


class CalendarCreator(Protocol):
    def create_dev_calendar(self, *, timezone_name: str) -> str: ...


class GatewayFactory(Protocol):
    def __call__(
        self,
        *,
        client_secret_file: Path,
        token_file: Path,
    ) -> CalendarCreator: ...


class SessionScopeFactory(Protocol):
    def __call__(self) -> AbstractContextManager[Session]: ...


@dataclass(frozen=True, slots=True)
class GoogleSetupOutcome:
    created: bool


def setup_google_calendar(
    *,
    settings: Settings,
    gateway_factory: GatewayFactory = GoogleCalendarGateway.from_oauth_files,
    session_factory: SessionScopeFactory = session_scope,
) -> GoogleSetupOutcome:
    """Create and persist the one dedicated development calendar, at most once."""

    client_secret_file = settings.google_client_secret_file
    if client_secret_file is None or not client_secret_file.expanduser().is_file():
        raise GoogleSetupError(
            "Google OAuth client-secret file is not configured or does not exist."
        )

    client_secret_file = client_secret_file.expanduser()
    token_file = settings.google_token_file.expanduser()

    with session_factory() as session:
        app_settings = session.get(AppSettings, 1)
        if app_settings is not None and app_settings.google_calendar_id is not None:
            _require_safe_calendar_id(app_settings.google_calendar_id)
            return GoogleSetupOutcome(created=False)
        timezone_name = app_settings.timezone if app_settings is not None else settings.timezone

    # Do not hold a SQLite transaction open while the user completes browser OAuth.
    gateway = gateway_factory(
        client_secret_file=client_secret_file,
        token_file=token_file,
    )
    calendar_id = gateway.create_dev_calendar(timezone_name=timezone_name)
    _require_safe_calendar_id(calendar_id)

    with session_factory() as session:
        app_settings = session.get(AppSettings, 1)
        if app_settings is None:
            app_settings = AppSettings(
                id=1,
                timezone=settings.timezone,
                blackboard_ics_url=settings.blackboard_ics_url,
            )
            session.add(app_settings)
        if app_settings.google_calendar_id is not None:
            _require_safe_calendar_id(app_settings.google_calendar_id)
            return GoogleSetupOutcome(created=False)
        _require_safe_calendar_id(calendar_id)
        app_settings.google_calendar_id = calendar_id
        session.flush()

    return GoogleSetupOutcome(created=True)


def run_cli(
    *,
    settings: Settings | None = None,
    gateway_factory: GatewayFactory = GoogleCalendarGateway.from_oauth_files,
    session_factory: SessionScopeFactory = session_scope,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    try:
        outcome = setup_google_calendar(
            settings=settings or get_settings(),
            gateway_factory=gateway_factory,
            session_factory=session_factory,
        )
    except GoogleSetupError as exc:
        print(f"Google Calendar setup stopped: {exc}", file=error_output)
        return 2
    except GoogleCalendarError:
        print(
            "Google Calendar setup failed. No calendar ID was saved; review OAuth setup and retry.",
            file=error_output,
        )
        return 1
    except Exception:
        # A CLI boundary must not echo credential-bearing third-party exception details.
        print(
            "Google Calendar setup failed because of an unexpected local error. "
            "No secrets were shown.",
            file=error_output,
        )
        return 1

    if outcome.created:
        print("Google Calendar setup complete. Semester Ops - Dev is configured.", file=output)
    else:
        print(
            "Google Calendar setup already complete. Semester Ops - Dev remains configured.",
            file=output,
        )
    return 0


def main() -> int:
    return run_cli()


def _require_safe_calendar_id(calendar_id: str) -> None:
    if not calendar_id.strip() or calendar_id.strip().lower() == "primary":
        raise GoogleSetupError(
            "a blank or primary calendar ID cannot be used for the development projection."
        )


if __name__ == "__main__":
    raise SystemExit(main())
