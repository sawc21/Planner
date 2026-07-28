from __future__ import annotations

import re
from collections import deque
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from semester_ops.application.facade import SemesterOpsService
from semester_ops.application.sync import GoogleCalendarProjectionSync, SyncService
from semester_ops.config import Settings
from semester_ops.db import session as session_module
from semester_ops.db.base import Base
from semester_ops.db.models import AppSettings, BlockOccurrence
from semester_ops.db.session import create_sqlite_engine
from semester_ops.integrations.google_calendar import (
    CalendarPage,
    LocalCalendarProjection,
    RemoteCalendarEvent,
    TimeRange,
    deterministic_event_id,
    ownership_tags,
)
from semester_ops.mcp_server import McpTools, _default_service_factory
from semester_ops.web.main import create_app


class FakeCalendarGateway:
    def __init__(self) -> None:
        self.pages: deque[CalendarPage] = deque([CalendarPage((), None, "sync-1")])
        self.upserts: list[LocalCalendarProjection] = []

    def create_dev_calendar(self, *, timezone_name: str) -> str:
        del timezone_name
        return "dev-calendar"

    def list_event_page(
        self,
        calendar_id: str,
        *,
        sync_token: str | None,
        page_token: str | None,
    ) -> CalendarPage:
        assert calendar_id == "dev-calendar"
        assert page_token is None
        del sync_token
        return self.pages.popleft()

    def upsert_projection(
        self,
        calendar_id: str,
        *,
        event_id: str,
        projection: LocalCalendarProjection,
    ) -> RemoteCalendarEvent:
        assert calendar_id == "dev-calendar"
        self.upserts.append(projection)
        return RemoteCalendarEvent(
            event_id=event_id,
            occurrence_id=projection.occurrence_id,
            time_range=projection.time_range,
            summary=projection.summary,
            description=projection.description,
            tags=ownership_tags(projection.occurrence_id, projection.revision),
            etag='"created"',
        )

    def delete_owned_event(
        self,
        calendar_id: str,
        *,
        event_id: str,
        occurrence_id: str,
    ) -> bool:
        del calendar_id, event_id, occurrence_id
        return True


def test_mcp_review_web_apply_today_and_google_pullback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = Path("var/vertical-slice-acceptance.db")
    for suffix in ("", "-shm", "-wal"):
        database_path.with_name(database_path.name + suffix).unlink(missing_ok=True)
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)

    payload = {
        "schema_version": "1.0",
        "mode": "replace_scope",
        "managed_dataset": "acceptance.vertical_slice",
        "idempotency_key": "vertical-slice-import-001",
        "base_revision": 0,
        "scope": {"start_date": "2026-08-24", "end_date": "2026-08-24"},
        "semester": {
            "name": "Vertical slice semester",
            "start_date": "2026-08-24",
            "end_date": "2026-08-24",
            "timezone": "America/Chicago",
        },
        "source": {"filename": "vertical-slice.txt"},
        "occurrences": [
            {
                "source_key": "morning-training",
                "title": "Morning training and breakfast",
                "category": "workout",
                "flexibility": "flexible",
                "description": "Private workout and nutrition notes stay local.",
                "occurrence_date": "2026-08-24",
                "start_time": "08:00:00",
                "duration_minutes": 60,
                "checklist_items": [{"title": "Fill water bottle"}],
                "meal_items": [
                    {
                        "food_name": "Protein breakfast",
                        "calories_per_unit": "520",
                        "protein_grams_per_unit": "42",
                    }
                ],
                "workout_exercises": [
                    {"name": "Squat", "planned_sets": 2, "rep_min": 5, "rep_max": 5}
                ],
            }
        ],
    }

    tools = McpTools(_default_service_factory)
    draft = tools.create_import_draft(payload, "vertical-slice-import-001", 0)
    retry = tools.create_import_draft(payload, "vertical-slice-import-001", 0)
    assert draft["id"] == retry["id"]
    assert draft["status"] == "ready"

    @contextmanager
    def web_services():
        with factory() as session:
            try:
                yield SemesterOpsService(session)
                session.commit()
            except Exception:
                session.rollback()
                raise

    app = create_app(
        settings=Settings(
            database_path=database_path,
            secret_key="vertical-slice-test-secret",
        ),
        service_factory=web_services,
    )
    client = TestClient(app)
    detail = client.get(f"/imports/{draft['id']}")
    token = _csrf(detail.text)
    approval = client.post(
        f"/imports/{draft['id']}/approve",
        data={"_csrf": token},
        follow_redirects=False,
    )
    assert approval.status_code == 303

    today = client.get("/?day=2026-08-24")
    assert today.status_code == 200
    assert "Morning training and breakfast" in today.text
    assert "Protein breakfast" in today.text

    with factory() as session:
        occurrence = session.scalar(select(BlockOccurrence))
        assert occurrence is not None
        occurrence_id = occurrence.id
        original = TimeRange(occurrence.planned_start_utc, occurrence.planned_end_utc)
        settings = session.get(AppSettings, 1)
        assert settings is not None
        settings.google_calendar_id = "dev-calendar"
        session.commit()

    gateway = FakeCalendarGateway()
    sync = SyncService(factory, (GoogleCalendarProjectionSync(lambda: gateway),))
    first = sync.sync_now()
    assert first.succeeded
    assert gateway.upserts[0].description == "Managed by the local Semester Ops tracker."
    assert "Private workout" not in gateway.upserts[0].description

    moved = TimeRange(original.start + timedelta(hours=2), original.end + timedelta(hours=2))
    projection = gateway.upserts[0]
    gateway.pages.append(
        CalendarPage(
            (
                RemoteCalendarEvent(
                    event_id=deterministic_event_id(occurrence_id),
                    occurrence_id=occurrence_id,
                    time_range=moved,
                    summary=projection.summary,
                    description=projection.description,
                    tags=ownership_tags(occurrence_id, projection.revision),
                    etag='"moved"',
                ),
            ),
            None,
            "sync-2",
        )
    )
    second = sync.sync_now()
    assert second.succeeded

    with factory() as session:
        occurrence = session.get(BlockOccurrence, occurrence_id)
        assert occurrence is not None
        assert occurrence.planned_start_utc == moved.start
        assert occurrence.override_reason == "Moved in Google Calendar"

    moved_today = client.get("/?day=2026-08-24")
    assert "10:00 AM" in moved_today.text


def _csrf(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
    assert match is not None
    return match.group(1)
