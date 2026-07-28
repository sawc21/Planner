from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from semester_ops.cli.google_setup import run_cli
from semester_ops.config import Settings
from semester_ops.db.base import Base
from semester_ops.db.models import AppSettings
from semester_ops.db.session import create_sqlite_engine
from semester_ops.integrations.google_calendar.gateway import (
    DEV_CALENDAR_NAME,
    GoogleCalendarConfigurationError,
    GoogleCalendarGateway,
)


class FakeCalendarCreator:
    def __init__(self, calendar_id: str = "opaque-dev-calendar-id") -> None:
        self.calendar_id = calendar_id
        self.timezones: list[str] = []

    def create_dev_calendar(self, *, timezone_name: str) -> str:
        self.timezones.append(timezone_name)
        return self.calendar_id


class FakeGatewayFactory:
    def __init__(self, creator: FakeCalendarCreator) -> None:
        self.creator = creator
        self.calls: list[tuple[Path, Path]] = []

    def __call__(
        self,
        *,
        client_secret_file: Path,
        token_file: Path,
    ) -> FakeCalendarCreator:
        self.calls.append((client_secret_file, token_file))
        return self.creator


class FakeRequest:
    def __init__(self, response: dict[str, str]) -> None:
        self.response = response

    def execute(self, *, num_retries: int) -> dict[str, str]:
        assert num_retries == 2
        return self.response


class FakeCalendarsResource:
    def __init__(self, response: dict[str, str]) -> None:
        self.response = response
        self.bodies: list[dict[str, str]] = []

    def insert(self, *, body: dict[str, str]) -> FakeRequest:
        self.bodies.append(body)
        return FakeRequest(self.response)


class FakeGoogleService:
    def __init__(self, response: dict[str, str]) -> None:
        self.resource = FakeCalendarsResource(response)

    def calendars(self) -> FakeCalendarsResource:
        return self.resource


@pytest.fixture
def database(tmp_path: Path) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_sqlite_engine(tmp_path / "setup.db")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def make_session_scope(
    factory: sessionmaker[Session],
):
    @contextmanager
    def sessions() -> Iterator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    return sessions


def make_settings(tmp_path: Path, client_secret_file: Path | None) -> Settings:
    return Settings(
        _env_file=None,
        database_path=tmp_path / "unused.db",
        timezone="America/Chicago",
        google_client_secret_file=client_secret_file,
        google_token_file=tmp_path / "token-with-secret-value.json",
    )


def test_setup_persists_opaque_id_without_printing_sensitive_values(
    tmp_path: Path,
    database: tuple[Engine, sessionmaker[Session]],
) -> None:
    _engine, session_maker = database
    client_file = tmp_path / "client-with-secret-value.json"
    client_file.write_text("client-secret-material", encoding="utf-8")
    creator = FakeCalendarCreator()
    gateway_factory = FakeGatewayFactory(creator)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        settings=make_settings(tmp_path, client_file),
        gateway_factory=gateway_factory,
        session_factory=make_session_scope(session_maker),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert creator.timezones == ["America/Chicago"]
    assert gateway_factory.calls == [(client_file, tmp_path / "token-with-secret-value.json")]
    with session_maker() as session:
        assert session.get(AppSettings, 1).google_calendar_id == "opaque-dev-calendar-id"
    combined_output = stdout.getvalue() + stderr.getvalue()
    assert "opaque-dev-calendar-id" not in combined_output
    assert "client-secret-material" not in combined_output
    assert "token-with-secret-value" not in combined_output


def test_setup_refuses_a_missing_client_file_before_gateway_or_database_use(
    tmp_path: Path,
    database: tuple[Engine, sessionmaker[Session]],
) -> None:
    _engine, session_maker = database
    creator = FakeCalendarCreator()
    gateway_factory = FakeGatewayFactory(creator)
    stderr = StringIO()

    exit_code = run_cli(
        settings=make_settings(tmp_path, tmp_path / "missing.json"),
        gateway_factory=gateway_factory,
        session_factory=make_session_scope(session_maker),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert gateway_factory.calls == []
    assert "client-secret file" in stderr.getvalue()
    with session_maker() as session:
        assert session.get(AppSettings, 1) is None


def test_setup_is_idempotent_after_calendar_id_is_persisted(
    tmp_path: Path,
    database: tuple[Engine, sessionmaker[Session]],
) -> None:
    _engine, session_maker = database
    client_file = tmp_path / "client.json"
    client_file.write_text("{}", encoding="utf-8")
    with session_maker.begin() as session:
        session.add(AppSettings(id=1, google_calendar_id="already-configured"))
    gateway_factory = FakeGatewayFactory(FakeCalendarCreator())
    stdout = StringIO()

    exit_code = run_cli(
        settings=make_settings(tmp_path, client_file),
        gateway_factory=gateway_factory,
        session_factory=make_session_scope(session_maker),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert gateway_factory.calls == []
    assert "already complete" in stdout.getvalue()
    assert "already-configured" not in stdout.getvalue()


def test_setup_rejects_primary_without_persisting_it(
    tmp_path: Path,
    database: tuple[Engine, sessionmaker[Session]],
) -> None:
    _engine, session_maker = database
    client_file = tmp_path / "client.json"
    client_file.write_text("{}", encoding="utf-8")
    stderr = StringIO()

    exit_code = run_cli(
        settings=make_settings(tmp_path, client_file),
        gateway_factory=FakeGatewayFactory(FakeCalendarCreator("primary")),
        session_factory=make_session_scope(session_maker),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 2
    with session_maker() as session:
        assert session.get(AppSettings, 1) is None
    assert "primary calendar ID" in stderr.getvalue()


def test_gateway_creates_exact_development_calendar() -> None:
    service = FakeGoogleService({"id": "opaque-dev-calendar-id"})

    calendar_id = GoogleCalendarGateway(service).create_dev_calendar(
        timezone_name="America/Chicago"
    )

    assert calendar_id == "opaque-dev-calendar-id"
    assert service.resource.bodies == [
        {
            "summary": DEV_CALENDAR_NAME,
            "description": "Development projection owned by the local Semester Ops app.",
            "timeZone": "America/Chicago",
        }
    ]


def test_gateway_rejects_primary_calendar_response() -> None:
    service = FakeGoogleService({"id": "primary"})

    with pytest.raises(GoogleCalendarConfigurationError):
        GoogleCalendarGateway(service).create_dev_calendar(timezone_name="America/Chicago")
