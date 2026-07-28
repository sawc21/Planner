from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from semester_ops.application.facade import SemesterOpsService
from semester_ops.application.schedule import ScheduleService
from semester_ops.application.sync import (
    BlackboardAssignmentSync,
    ConnectorSyncOutcome,
    GoogleCalendarProjectionSync,
    SyncService,
)
from semester_ops.db.base import Base
from semester_ops.db.models import (
    AppSettings,
    Assignment,
    AssignmentBlockLink,
    AuditEvent,
    BlockOccurrence,
    BlockTemplate,
    CalendarEventLink,
    Course,
    ExternalSourceState,
    Semester,
    SyncConflict,
    SyncRun,
)
from semester_ops.db.session import create_sqlite_engine
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    ExternalRecordState,
    SyncConflictStatus,
    SyncConnector,
    SyncStatus,
)
from semester_ops.integrations.blackboard import BlackboardFeedClient
from semester_ops.integrations.google_calendar import (
    CalendarPage,
    LocalCalendarProjection,
    RemoteCalendarEvent,
    SyncTokenExpired,
    TimeRange,
    deterministic_event_id,
    ownership_tags,
)


def _session_factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_sqlite_engine(tmp_path / "sync-test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@dataclass
class _FailingSync:
    connector: SyncConnector = SyncConnector.GOOGLE

    def synchronize(self, session: Session, *, run_id: str) -> ConnectorSyncOutcome:
        session.add(
            AuditEvent(
                event_type="rolled_back",
                entity_type="sync",
                entity_id=run_id,
            )
        )
        raise RuntimeError("https://private.example/?secret-token")


@dataclass
class _SuccessfulSync:
    connector: SyncConnector = SyncConnector.BLACKBOARD

    def synchronize(self, session: Session, *, run_id: str) -> ConnectorSyncOutcome:
        session.add(
            AuditEvent(
                event_type="persisted",
                entity_type="sync",
                entity_id=run_id,
            )
        )
        return ConnectorSyncOutcome(created_count=1)


def test_connector_runs_commit_and_fail_independently(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    result = SyncService(factory, (_FailingSync(), _SuccessfulSync())).sync_now()

    assert [run.status for run in result.runs] == [SyncStatus.FAILED, SyncStatus.SUCCEEDED]
    assert "secret-token" not in str(result.as_dict())
    with factory() as session:
        runs = tuple(session.scalars(select(SyncRun).order_by(SyncRun.started_at)))
        events = tuple(session.scalars(select(AuditEvent)))
    assert [run.status for run in runs] == [SyncStatus.FAILED, SyncStatus.SUCCEEDED]
    assert runs[0].error_count == 1
    assert runs[1].created_count == 1
    assert [event.event_type for event in events] == ["persisted"]


def test_blackboard_runner_refreshes_assignment_and_source_state(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        session.add(semester)
        session.flush()
        session.add(
            AppSettings(
                id=1,
                active_semester_id=semester.id,
                blackboard_ics_url="https://school.example/private/calendar.ics",
            )
        )
        session.commit()

    feed = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Blackboard//Calendar//EN\r
BEGIN:VEVENT\r
UID:assignment-1\r
SUMMARY:Lab report\r
DTSTART;TZID=America/Chicago:20260825T170000\r
CATEGORIES:CS 101\r
SEQUENCE:1\r
END:VEVENT\r
END:VCALENDAR\r
"""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=feed,
            headers={"ETag": '"new"'},
            request=request,
        )
    )
    client = BlackboardFeedClient(client=httpx.Client(transport=transport))

    result = SyncService(factory, (BlackboardAssignmentSync(client),)).sync_now()
    second = SyncService(factory, (BlackboardAssignmentSync(client),)).sync_now()

    assert result.runs[0].status is SyncStatus.SUCCEEDED
    assert result.runs[0].created_count == 1
    assert second.runs[0].created_count == 0
    with factory() as session:
        assignment = session.scalar(select(Assignment))
        state = session.scalar(select(ExternalSourceState))
        courses = tuple(session.scalars(select(Course)))
    assert assignment is not None
    assert assignment.title == "Lab report"
    assert assignment.due_at_utc == datetime(2026, 8, 25, 22, tzinfo=UTC)
    assert state is not None
    assert state.etag == '"new"'
    assert state.last_success_at is not None
    assert len(courses) == 1
    assert courses[0].name == "CS 101"
    assert assignment.course_id == courses[0].id


def _blackboard_feed(
    *,
    sequence: int,
    due_day: int | None,
    status: str = "CONFIRMED",
) -> bytes:
    due = (
        f"DTSTART;TZID=America/Chicago:202608{due_day:02d}T170000\r\n"
        if due_day is not None
        else ""
    )
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Blackboard//Calendar//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:revisioned-assignment\r\n"
        "SUMMARY:Research paper\r\n"
        f"{due}"
        "CATEGORIES:HIST 210\r\n"
        f"STATUS:{status}\r\n"
        f"SEQUENCE:{sequence}\r\n"
        f"DTSTAMP:202607{sequence + 10:02d}T120000Z\r\n"
        f"LAST-MODIFIED:202607{sequence + 10:02d}T120000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    ).encode()


def _queued_blackboard_client(*feeds: bytes) -> BlackboardFeedClient:
    responses = deque(feeds)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=responses.popleft(), request=request)

    return BlackboardFeedClient(client=httpx.Client(transport=httpx.MockTransport(respond)))


def _configure_blackboard(factory: sessionmaker[Session]) -> str:
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        session.add(semester)
        session.flush()
        session.add(
            AppSettings(
                id=1,
                active_semester_id=semester.id,
                blackboard_ics_url="https://school.example/private/calendar.ics",
            )
        )
        session.commit()
        return semester.id


def test_blackboard_cancellation_revision_blocks_stale_reactivation(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    _configure_blackboard(factory)
    client = _queued_blackboard_client(
        _blackboard_feed(sequence=4, due_day=25),
        _blackboard_feed(sequence=5, due_day=None, status="CANCELLED"),
        _blackboard_feed(sequence=4, due_day=26),
    )
    service = SyncService(factory, (BlackboardAssignmentSync(client),))

    service.sync_now()
    canceled = service.sync_now()
    stale_active = service.sync_now()

    assert canceled.runs[0].deleted_count == 1
    assert stale_active.runs[0].status is SyncStatus.SUCCEEDED
    with factory() as session:
        assignment = session.scalar(select(Assignment))
    assert assignment is not None
    assert assignment.source_state is ExternalRecordState.CANCELED
    assert assignment.inbox_status is AssignmentInboxStatus.CANCELED
    assert assignment.sequence == 5
    assert assignment.source_last_modified == datetime(2026, 7, 15, 12, tzinfo=UTC)
    assert assignment.due_at_utc == datetime(2026, 8, 25, 22, tzinfo=UTC)


def test_blackboard_due_change_flags_linked_study_blocks_for_replanning(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    semester_id = _configure_blackboard(factory)
    client = _queued_blackboard_client(
        _blackboard_feed(sequence=1, due_day=25),
        _blackboard_feed(sequence=2, due_day=27),
    )
    service = SyncService(factory, (BlackboardAssignmentSync(client),))
    service.sync_now()

    start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    with factory() as session:
        assignment = session.scalar(select(Assignment))
        assert assignment is not None
        study = BlockOccurrence(
            semester_id=semester_id,
            occurrence_date=date(2026, 8, 24),
            title="Study paper",
            category=BlockCategory.STUDY,
            planned_start_utc=start,
            planned_end_utc=start + timedelta(hours=1),
        )
        meal = BlockOccurrence(
            semester_id=semester_id,
            occurrence_date=date(2026, 8, 24),
            title="Dinner",
            category=BlockCategory.MEAL,
            planned_start_utc=start + timedelta(hours=2),
            planned_end_utc=start + timedelta(hours=3),
        )
        study_link = AssignmentBlockLink(assignment=assignment, occurrence=study)
        meal_link = AssignmentBlockLink(assignment=assignment, occurrence=meal)
        session.add_all((study, meal, study_link, meal_link))
        session.commit()
        study_link_id = study_link.id
        meal_link_id = meal_link.id

    result = service.sync_now()

    assert result.runs[0].status is SyncStatus.SUCCEEDED
    with factory() as session:
        assignment = session.scalar(select(Assignment))
        study_link = session.get(AssignmentBlockLink, study_link_id)
        meal_link = session.get(AssignmentBlockLink, meal_link_id)
        audit = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "assignment.due_changed")
        )
    assert assignment is not None
    assert assignment.source_changed is True
    assert assignment.due_at_utc == datetime(2026, 8, 27, 22, tzinfo=UTC)
    assert study_link is not None and study_link.needs_replanning is True
    assert meal_link is not None and meal_link.needs_replanning is False
    assert audit is not None
    assert audit.actor == "blackboard-sync"


class _FakeCalendarGateway:
    def __init__(self) -> None:
        self.pages: deque[CalendarPage | Exception] = deque([CalendarPage((), None, "sync-1")])
        self.upserts: list[LocalCalendarProjection] = []
        self.upsert_attempts: list[str] = []
        self.fail_upsert_occurrence_ids: set[str] = set()
        self.sync_tokens: list[str | None] = []

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
        self.sync_tokens.append(sync_token)
        page = self.pages.popleft()
        if isinstance(page, Exception):
            raise page
        return page

    def upsert_projection(
        self,
        calendar_id: str,
        *,
        event_id: str,
        projection: LocalCalendarProjection,
    ) -> RemoteCalendarEvent:
        assert calendar_id == "dev-calendar"
        self.upsert_attempts.append(projection.occurrence_id)
        if projection.occurrence_id in self.fail_upsert_occurrence_ids:
            raise RuntimeError("https://private.example/?secret=calendar-token")
        self.upserts.append(projection)
        return RemoteCalendarEvent(
            event_id=event_id,
            occurrence_id=projection.occurrence_id,
            time_range=projection.time_range,
            summary=projection.summary,
            description=projection.description,
            tags=ownership_tags(projection.occurrence_id, projection.revision),
            etag='"etag"',
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


def test_google_runner_pushes_then_pulls_a_remote_move(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        occurrence = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Class",
            description="Private meal ingredients and checklist notes",
            location="Private home address",
            planned_start_utc=start,
            planned_end_utc=start + timedelta(hours=1),
        )
        session.add_all(
            [
                semester,
                occurrence,
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
            ]
        )
        session.commit()
        occurrence_id = occurrence.id

    gateway = _FakeCalendarGateway()
    service = SyncService(factory, (GoogleCalendarProjectionSync(lambda: gateway),))

    first = service.sync_now()

    assert first.runs[0].status is SyncStatus.SUCCEEDED
    assert first.runs[0].created_count == 1
    assert gateway.sync_tokens == [None]
    assert gateway.upserts[0].description == "Managed by the local Semester Ops tracker."
    assert "ingredients" not in gateway.upserts[0].description
    assert "address" not in gateway.upserts[0].description
    moved_range = TimeRange(
        start + timedelta(days=1, hours=2),
        start + timedelta(days=1, hours=3),
    )
    created = gateway.upserts[0]
    gateway.pages.append(
        CalendarPage(
            (
                RemoteCalendarEvent(
                    event_id=next(iter(_event_ids(factory))),
                    occurrence_id=occurrence_id,
                    time_range=moved_range,
                    summary=created.summary,
                    description=created.description,
                    tags=ownership_tags(occurrence_id, created.revision),
                    etag='"moved"',
                ),
            ),
            None,
            "sync-2",
        )
    )

    second = service.sync_now()

    assert second.runs[0].status is SyncStatus.SUCCEEDED
    assert second.runs[0].updated_count == 1
    assert gateway.sync_tokens == [None, "sync-1"]
    with factory() as session:
        occurrence = session.get(BlockOccurrence, occurrence_id)
        settings = session.get(AppSettings, 1)
        link = session.scalar(
            select(CalendarEventLink).where(CalendarEventLink.occurrence_id == occurrence_id)
        )
        audit = session.scalar(select(AuditEvent).where(AuditEvent.event_type == "block.moved"))
        state = session.scalar(
            select(ExternalSourceState).where(ExternalSourceState.connector == SyncConnector.GOOGLE)
        )
    assert occurrence is not None
    assert occurrence.planned_start_utc == moved_range.start
    assert occurrence.occurrence_date == date(2026, 8, 25)
    assert occurrence.revision == 2
    assert occurrence.override_reason == "Moved in Google Calendar"
    assert settings is not None
    assert settings.schedule_revision == 1
    assert link is not None
    assert link.last_synced_local_revision == 2
    assert audit is not None
    assert audit.actor == "google-calendar-sync"
    assert gateway.upserts[-1].revision == 2
    assert state is not None
    assert state.sync_token == "sync-2"


def _event_ids(factory: sessionmaker[Session]) -> tuple[str, ...]:
    with factory() as session:
        return tuple(session.scalars(select(CalendarEventLink.event_id)))


def test_google_410_full_scan_recreates_projection_missing_from_remote(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        occurrence = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Class",
            planned_start_utc=start,
            planned_end_utc=start + timedelta(hours=1),
        )
        session.add_all((semester, occurrence))
        session.flush()
        event_id = deterministic_event_id(occurrence.id)
        session.add_all(
            (
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
                CalendarEventLink(
                    occurrence_id=occurrence.id,
                    calendar_id="dev-calendar",
                    event_id=event_id,
                    last_synced_local_revision=1,
                    last_synced_start_utc=start,
                    last_synced_end_utc=start + timedelta(hours=1),
                ),
                ExternalSourceState(
                    connector=SyncConnector.GOOGLE,
                    source_key="dev-calendar",
                    sync_token="expired-token",
                ),
            )
        )
        session.commit()
        occurrence_id = occurrence.id

    gateway = _FakeCalendarGateway()
    gateway.pages = deque(
        (
            SyncTokenExpired("expired"),
            CalendarPage((), None, "fresh-token"),
        )
    )

    result = SyncService(
        factory,
        (GoogleCalendarProjectionSync(lambda: gateway),),
    ).sync_now()

    assert result.runs[0].status is SyncStatus.SUCCEEDED
    assert result.runs[0].updated_count == 1
    assert gateway.sync_tokens == ["expired-token", None]
    assert gateway.upsert_attempts == [occurrence_id]
    with factory() as session:
        state = session.scalar(
            select(ExternalSourceState).where(ExternalSourceState.connector == SyncConnector.GOOGLE)
        )
    assert state is not None
    assert state.sync_token == "fresh-token"


def test_google_remote_mutations_continue_after_item_failure_and_report_partial(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        first = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="First",
            planned_start_utc=start,
            planned_end_utc=start + timedelta(hours=1),
        )
        second = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Second",
            planned_start_utc=start + timedelta(hours=2),
            planned_end_utc=start + timedelta(hours=3),
        )
        session.add_all(
            (
                semester,
                first,
                second,
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
            )
        )
        session.commit()
        failed_id = first.id
        successful_id = second.id

    gateway = _FakeCalendarGateway()
    gateway.fail_upsert_occurrence_ids.add(failed_id)

    result = SyncService(
        factory,
        (GoogleCalendarProjectionSync(lambda: gateway),),
    ).sync_now()

    run = result.runs[0]
    assert run.status is SyncStatus.PARTIAL
    assert run.error_count == 1
    assert run.created_count == 1
    assert set(gateway.upsert_attempts) == {failed_id, successful_id}
    assert run.details["external_writes_succeeded"] == 1
    assert run.details["retry_required"] is True
    assert "calendar-token" not in str(run.details)
    assert run.details["failed_mutations"] == [
        {
            "operation": "upsert",
            "occurrence_id": failed_id,
            "event_id": deterministic_event_id(failed_id),
            "stage": "remote_write",
            "error_code": "RuntimeError",
            "external_write_succeeded": False,
        }
    ]
    with factory() as session:
        links = tuple(session.scalars(select(CalendarEventLink)))
        state = session.scalar(
            select(ExternalSourceState).where(ExternalSourceState.connector == SyncConnector.GOOGLE)
        )
    assert [link.occurrence_id for link in links] == [successful_id]
    assert state is not None
    assert state.sync_token is None


def test_google_pull_collision_isolated_and_later_pull_still_applies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _session_factory(tmp_path)
    start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        first = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="First",
            planned_start_utc=start,
            planned_end_utc=start + timedelta(hours=1),
        )
        second = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Second",
            planned_start_utc=start + timedelta(hours=2),
            planned_end_utc=start + timedelta(hours=3),
        )
        session.add_all(
            (
                semester,
                first,
                second,
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
            )
        )
        session.commit()
        failed_id = first.id
        successful_id = second.id

    gateway = _FakeCalendarGateway()
    sync = SyncService(factory, (GoogleCalendarProjectionSync(lambda: gateway),))
    sync.sync_now()
    moves = {
        failed_id: TimeRange(start + timedelta(hours=1), start + timedelta(hours=2)),
        successful_id: TimeRange(start + timedelta(hours=4), start + timedelta(hours=5)),
    }
    gateway.pages.append(
        CalendarPage(
            tuple(
                RemoteCalendarEvent(
                    event_id=deterministic_event_id(occurrence_id),
                    occurrence_id=occurrence_id,
                    time_range=moved_range,
                    summary="First" if occurrence_id == failed_id else "Second",
                    description="Managed by the local Semester Ops tracker.",
                    tags=ownership_tags(occurrence_id, 1),
                    etag='"moved"',
                )
                for occurrence_id, moved_range in moves.items()
            ),
            None,
            "sync-2",
        )
    )
    original_move = ScheduleService.move_occurrence

    def collide_once(
        service: ScheduleService,
        occurrence_id: str,
        start_utc: datetime,
        end_utc: datetime,
        *,
        actor: str = "user",
        automated: bool = False,
    ) -> BlockOccurrence:
        if occurrence_id == failed_id:
            raise IntegrityError("unique occurrence identity", {}, Exception("collision"))
        return original_move(
            service,
            occurrence_id,
            start_utc,
            end_utc,
            actor=actor,
            automated=automated,
        )

    monkeypatch.setattr(ScheduleService, "move_occurrence", collide_once)

    result = sync.sync_now()

    run = result.runs[0]
    assert run.status is SyncStatus.PARTIAL
    assert run.updated_count == 1
    assert run.error_count == 1
    assert run.details["failed_mutations"][0]["error_code"] == "integrity_collision"
    with factory() as session:
        failed = session.get(BlockOccurrence, failed_id)
        successful = session.get(BlockOccurrence, successful_id)
        state = session.scalar(
            select(ExternalSourceState).where(ExternalSourceState.connector == SyncConnector.GOOGLE)
        )
    assert failed is not None and successful is not None and state is not None
    assert failed.planned_start_utc == start
    assert successful.planned_start_utc == moves[successful_id].start
    assert state.sync_token == "sync-1"


def test_google_cross_date_template_move_preserves_recurrence_identity(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    first_start = datetime(2026, 8, 24, 15, tzinfo=UTC)
    second_start = datetime(2026, 8, 25, 15, tzinfo=UTC)
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        template = BlockTemplate(
            semester=semester,
            title="Class",
            weekdays=[0, 1],
            local_start_time=time(10),
            duration_minutes=60,
            effective_start_date=date(2026, 8, 24),
            effective_end_date=date(2026, 12, 12),
        )
        first = BlockOccurrence(
            semester=semester,
            template=template,
            occurrence_date=date(2026, 8, 24),
            title="Class",
            planned_start_utc=first_start,
            planned_end_utc=first_start + timedelta(hours=1),
        )
        second = BlockOccurrence(
            semester=semester,
            template=template,
            occurrence_date=date(2026, 8, 25),
            title="Class",
            planned_start_utc=second_start,
            planned_end_utc=second_start + timedelta(hours=1),
        )
        session.add_all((semester, template, first, second))
        session.flush()
        for occurrence, occurrence_start in ((first, first_start), (second, second_start)):
            session.add(
                CalendarEventLink(
                    occurrence_id=occurrence.id,
                    calendar_id="dev-calendar",
                    event_id=deterministic_event_id(occurrence.id),
                    last_synced_local_revision=1,
                    last_synced_start_utc=occurrence_start,
                    last_synced_end_utc=occurrence_start + timedelta(hours=1),
                )
            )
        session.add_all(
            (
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
                ExternalSourceState(
                    connector=SyncConnector.GOOGLE,
                    source_key="dev-calendar",
                    sync_token="sync-1",
                ),
            )
        )
        session.commit()
        first_id = first.id
        second_id = second.id

    moved_range = TimeRange(
        second_start + timedelta(hours=2),
        second_start + timedelta(hours=3),
    )
    gateway = _FakeCalendarGateway()
    gateway.pages = deque(
        (
            CalendarPage(
                (
                    RemoteCalendarEvent(
                        event_id=deterministic_event_id(first_id),
                        occurrence_id=first_id,
                        time_range=moved_range,
                        summary="Class",
                        description="Managed by the local Semester Ops tracker.",
                        tags=ownership_tags(first_id, 1),
                        etag='"moved"',
                    ),
                ),
                None,
                "sync-2",
            ),
        )
    )

    result = SyncService(
        factory,
        (GoogleCalendarProjectionSync(lambda: gateway),),
    ).sync_now()

    assert result.runs[0].status is SyncStatus.SUCCEEDED
    with factory() as session:
        first = session.get(BlockOccurrence, first_id)
        second = session.get(BlockOccurrence, second_id)
    assert first is not None and second is not None
    assert first.planned_start_utc == moved_range.start
    assert first.occurrence_date == date(2026, 8, 24)
    assert second.occurrence_date == date(2026, 8, 25)


def test_google_conflict_survives_no_change_then_reconciles_after_resolution(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    base = TimeRange(
        datetime(2026, 8, 24, 15, tzinfo=UTC),
        datetime(2026, 8, 24, 16, tzinfo=UTC),
    )
    with factory() as session:
        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        occurrence = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Class",
            planned_start_utc=base.start,
            planned_end_utc=base.end,
        )
        session.add_all(
            (
                semester,
                occurrence,
                AppSettings(
                    id=1,
                    active_semester_id=semester.id,
                    google_calendar_id="dev-calendar",
                ),
            )
        )
        session.commit()
        occurrence_id = occurrence.id

    gateway = _FakeCalendarGateway()
    sync = SyncService(factory, (GoogleCalendarProjectionSync(lambda: gateway),))
    sync.sync_now()
    local = TimeRange(base.start + timedelta(hours=1), base.end + timedelta(hours=1))
    remote = TimeRange(base.start + timedelta(hours=2), base.end + timedelta(hours=2))
    with factory() as session:
        ScheduleService(session).move_occurrence(occurrence_id, local.start, local.end)
        session.commit()
    gateway.pages.append(
        CalendarPage(
            (
                RemoteCalendarEvent(
                    event_id=deterministic_event_id(occurrence_id),
                    occurrence_id=occurrence_id,
                    time_range=remote,
                    summary="Class",
                    description="Managed by the local Semester Ops tracker.",
                    tags=ownership_tags(occurrence_id, 1),
                    etag='"remote-move"',
                ),
            ),
            None,
            "sync-2",
        )
    )

    conflicted = sync.sync_now()

    assert conflicted.runs[0].status is SyncStatus.PARTIAL
    assert conflicted.runs[0].conflict_count == 1
    with factory() as session:
        conflict = session.scalar(select(SyncConflict))
        assert conflict is not None
        conflict_id = conflict.id

    gateway.pages.append(CalendarPage((), None, "sync-3"))
    quarantined = sync.sync_now()

    assert quarantined.runs[0].status is SyncStatus.PARTIAL
    assert quarantined.runs[0].conflict_count == 1
    with factory() as session:
        conflicts = tuple(session.scalars(select(SyncConflict)))
    assert len(conflicts) == 1
    assert conflicts[0].status is SyncConflictStatus.OPEN

    with factory() as session:
        response = SemesterOpsService(session).resolve_sync_conflict(
            conflict_id,
            SyncConflictStatus.KEEP_PLANNER.value,
        )
    assert "Keep" not in response["message"]
    gateway.pages.append(CalendarPage((), None, "sync-4"))

    reconciled = sync.sync_now()

    assert reconciled.runs[0].status is SyncStatus.SUCCEEDED
    assert gateway.upserts[-1].time_range == local
    with factory() as session:
        conflict = session.get(SyncConflict, conflict_id)
    assert conflict is not None
    assert conflict.status is SyncConflictStatus.KEEP_PLANNER
