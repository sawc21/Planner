from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from semester_ops.application.facade import SemesterOpsService
from semester_ops.application.schedule import ScheduleService
from semester_ops.db.base import Base
from semester_ops.db.models import (
    AppSettings,
    Assignment,
    AssignmentBlockLink,
    BlockOccurrence,
    BlockTemplate,
    CalendarEventLink,
    Semester,
    SyncConflict,
    SyncRun,
)
from semester_ops.db.session import create_sqlite_engine
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    DuePrecision,
    SyncConflictStatus,
    SyncConnector,
    SyncStatus,
)
from semester_ops.domain.time import resolve_wall_time


def test_week_contains_exactly_seven_operational_days(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        session.add_all(
            [
                _occurrence(semester, "Monday start", date(2026, 8, 24), time(5)),
                _occurrence(
                    semester,
                    "Sunday after midnight",
                    date(2026, 8, 31),
                    time(2),
                ),
                _occurrence(semester, "Eighth day", date(2026, 8, 31), time(5)),
            ]
        )
        session.commit()

        week = SemesterOpsService(session).get_week(date(2026, 8, 24))

        titles = [block["title"] for day in week["days"] for block in day["blocks"]]
        assert titles == ["Monday start", "Sunday after midnight"]
        assert week["summary"]["block_count"] == 2
        assert [block["title"] for block in week["days"][6]["blocks"]] == ["Sunday after midnight"]


def test_today_marks_every_overlapping_block_as_conflicted(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        session.add_all(
            [
                _occurrence(semester, "First", date(2026, 8, 24), time(9), duration=60),
                _occurrence(
                    semester,
                    "Second",
                    date(2026, 8, 24),
                    time(9, 30),
                    duration=60,
                ),
                _occurrence(semester, "Clear", date(2026, 8, 24), time(11), duration=60),
            ]
        )
        session.commit()

        today = SemesterOpsService(session).get_today(date(2026, 8, 24))

        rows = {row["title"]: row for row in today["blocks"]}
        assert rows["First"]["conflict"] is True
        assert rows["Second"]["conflict"] is True
        assert rows["Clear"]["conflict"] is False
        assert len(today["conflicts"]) == 1


def test_sync_card_counts_only_dirty_projected_occurrences(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        missing_link = _occurrence(
            semester,
            "Missing link",
            date(2026, 8, 24),
            time(8),
            revision=1,
        )
        clean = _occurrence(
            semester,
            "Clean",
            date(2026, 8, 24),
            time(9),
            revision=2,
        )
        stale_link = _occurrence(
            semester,
            "Stale link",
            date(2026, 8, 24),
            time(10),
            revision=3,
        )
        disabled = _occurrence(
            semester,
            "Local only",
            date(2026, 8, 24),
            time(11),
            revision=1,
            calendar_projection=False,
        )
        session.add_all([missing_link, clean, stale_link, disabled])
        session.flush()
        clean.calendar_link = CalendarEventLink(
            calendar_id="dev-calendar",
            event_id="clean-event",
            last_synced_local_revision=2,
        )
        stale_link.calendar_link = CalendarEventLink(
            calendar_id="dev-calendar",
            event_id="stale-event",
            last_synced_local_revision=2,
        )
        session.commit()

        today = SemesterOpsService(session).get_today(date(2026, 8, 24))

        rows = {row["title"]: row for row in today["blocks"]}
        assert today["sync"]["dirty_count"] == 2
        assert rows["Missing link"]["unsynced"] is True
        assert rows["Stale link"]["unsynced"] is True
        assert rows["Clean"]["unsynced"] is False
        assert rows["Local only"]["unsynced"] is False


def test_move_updates_manual_date_but_preserves_template_identity(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        template = BlockTemplate(
            semester=semester,
            title="Recurring class",
            weekdays=[0, 1],
            local_start_time=time(9),
            duration_minutes=60,
            effective_start_date=date(2026, 8, 24),
            effective_end_date=date(2026, 12, 12),
        )
        session.add(template)
        session.flush()
        manual = _occurrence(semester, "Manual", date(2026, 8, 24), time(8))
        monday = _occurrence(
            semester,
            "Monday class",
            date(2026, 8, 24),
            time(9),
            template=template,
        )
        tuesday = _occurrence(
            semester,
            "Tuesday class",
            date(2026, 8, 25),
            time(9),
            template=template,
        )
        session.add_all([manual, monday, tuesday])
        session.commit()

        schedule = ScheduleService(session)
        schedule.move_occurrence(
            manual.id,
            _utc(date(2026, 8, 25), time(8)),
            _utc(date(2026, 8, 25), time(9)),
        )
        schedule.move_occurrence(
            monday.id,
            _utc(date(2026, 8, 25), time(10)),
            _utc(date(2026, 8, 25), time(11)),
        )

        assert manual.occurrence_date == date(2026, 8, 25)
        assert monday.occurrence_date == date(2026, 8, 24)
        assert tuesday.occurrence_date == date(2026, 8, 25)


def test_keep_planner_resolution_makes_next_sync_push_local_time(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        base_start = _utc(date(2026, 8, 24), time(9))
        planner_start = _utc(date(2026, 8, 24), time(10))
        remote_start = _utc(date(2026, 8, 24), time(11))
        occurrence = BlockOccurrence(
            semester=semester,
            occurrence_date=date(2026, 8, 24),
            title="Conflicted class",
            planned_start_utc=planner_start,
            planned_end_utc=planner_start + timedelta(hours=1),
            revision=2,
        )
        occurrence.calendar_link = CalendarEventLink(
            calendar_id="dev-calendar",
            event_id="conflicted-event",
            last_synced_local_revision=1,
            last_synced_start_utc=base_start,
            last_synced_end_utc=base_start + timedelta(hours=1),
        )
        run = SyncRun(connector=SyncConnector.GOOGLE, status=SyncStatus.PARTIAL)
        session.add_all([occurrence, run])
        session.flush()
        conflict = SyncConflict(
            sync_run_id=run.id,
            occurrence_id=occurrence.id,
            planner_start_utc=planner_start,
            planner_end_utc=planner_start + timedelta(hours=1),
            remote_start_utc=remote_start,
            remote_end_utc=remote_start + timedelta(hours=1),
            base_start_utc=base_start,
            base_end_utc=base_start + timedelta(hours=1),
        )
        session.add(conflict)
        session.commit()

        SemesterOpsService(session).resolve_sync_conflict(conflict.id, "keep_planner")

        assert conflict.status is SyncConflictStatus.KEEP_PLANNER
        assert occurrence.planned_start_utc == planner_start
        assert occurrence.calendar_link is not None
        assert occurrence.calendar_link.last_synced_start_utc == remote_start
        assert occurrence.calendar_link.last_synced_end_utc == remote_start + timedelta(hours=1)


@pytest.mark.parametrize(
    "acknowledged_state",
    [
        AssignmentInboxStatus.PLANNED,
        AssignmentInboxStatus.COMPLETED,
        AssignmentInboxStatus.IGNORED,
    ],
)
def test_assignment_acknowledgement_clears_replanning_flags(
    tmp_path: Path,
    acknowledged_state: AssignmentInboxStatus,
) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        occurrence = _occurrence(semester, "Study block", date(2026, 8, 24), time(9))
        assignment = Assignment(
            external_uid="assignment-1",
            title="Read chapter 1",
            due_precision=DuePrecision.DATE,
            due_date=date(2026, 8, 25),
            source_changed=True,
            block_links=[
                AssignmentBlockLink(
                    occurrence=occurrence,
                    needs_replanning=True,
                )
            ],
        )
        session.add(assignment)
        session.commit()
        service = SemesterOpsService(session)

        row = service.list_assignments()["assignments"][0]

        assert row["source_changed"] is True
        assert row["linked_blocks"][0]["needs_replanning"] is True

        service.set_assignment_state(
            assignment.id,
            state=acknowledged_state.value,
            estimated_minutes=45,
        )

        assert assignment.inbox_status is acknowledged_state
        assert assignment.source_changed is False
        assert assignment.block_links[0].needs_replanning is False


def _session(tmp_path: Path) -> Session:
    engine = create_sqlite_engine(tmp_path / "schedule-views.db")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _seed_semester(session: Session) -> Semester:
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
            operational_day_boundary=time(4),
        )
    )
    session.flush()
    return semester


def _occurrence(
    semester: Semester,
    title: str,
    local_date: date,
    local_time: time,
    *,
    duration: int = 60,
    revision: int = 1,
    calendar_projection: bool = True,
    template: BlockTemplate | None = None,
) -> BlockOccurrence:
    start = _utc(local_date, local_time)
    return BlockOccurrence(
        semester=semester,
        template=template,
        occurrence_date=local_date,
        title=title,
        planned_start_utc=start,
        planned_end_utc=start + timedelta(minutes=duration),
        revision=revision,
        calendar_projection=calendar_projection,
    )


def _utc(local_date: date, local_time: time) -> datetime:
    return resolve_wall_time(local_date, local_time, "America/Chicago").astimezone(UTC)
