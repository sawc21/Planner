from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from semester_ops.application.errors import ValidationError
from semester_ops.application.facade import SemesterOpsService
from semester_ops.application.schedule import ScheduleService
from semester_ops.db.base import Base
from semester_ops.db.models import (
    AppSettings,
    Assignment,
    AssignmentBlockLink,
    AuditEvent,
    BlockOccurrence,
    BlockTemplate,
    CalendarEventLink,
    ChecklistItem,
    MealItem,
    Semester,
    SyncConflict,
    SyncRun,
    WorkoutExercise,
    WorkoutSet,
)
from semester_ops.db.session import create_sqlite_engine
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    DuePrecision,
    SyncConflictStatus,
    SyncConnector,
    SyncStatus,
    TrackingStatus,
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


def test_block_detail_surfaces_meal_recipe_and_workout_targets(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        meal = _occurrence(
            semester,
            "Cook lemon-Parmesan chicken dinner",
            date(2026, 8, 24),
            time(17),
        )
        meal.category = BlockCategory.MEAL
        meal.description = (
            "Ingredients: chicken breast; baby potatoes; green beans; lemon; Parmesan."
        )
        meal.meal_items = [
            MealItem(
                food_name="Lemon-Parmesan chicken, crispy potatoes, and green beans",
                planned_quantity=Decimal("1"),
                calories_per_unit=Decimal("720"),
                protein_grams_per_unit=Decimal("58"),
            )
        ]

        workout = _occurrence(
            semester,
            "Full-body Lift A",
            date(2026, 8, 24),
            time(18),
        )
        workout.category = BlockCategory.WORKOUT
        workout.description = (
            "Warm up 5-8 minutes; leave 2-3 good reps in reserve; rest 2-3 minutes "
            "for compounds and 60-90 seconds for smaller exercises."
        )
        workout.workout_exercises = [
            WorkoutExercise(
                name="Bench press",
                planned_sets=2,
                rep_min=6,
                rep_max=10,
                target_weight=Decimal("40"),
                weight_unit="lb",
                notes="Use a controlled lowering phase.",
                sets=[
                    WorkoutSet(set_number=1, target_reps=8),
                    WorkoutSet(set_number=2, target_reps=8),
                ],
            )
        ]
        session.add_all([meal, workout])
        session.commit()

        service = SemesterOpsService(session)
        meal_block = service.get_block(meal.id)["block"]
        workout_block = service.get_block(workout.id)["block"]

        assert meal_block["meal_guide"]["ingredients"] == [
            "chicken breast",
            "baby potatoes",
            "green beans",
            "lemon",
            "Parmesan",
        ]
        assert meal_block["meal_guide"]["source_label"] == "Stored details + source recipe"
        assert "chicken reaches 165 F" in " ".join(meal_block["meal_guide"]["steps"])
        exercise = workout_block["workout_exercises"][0]
        assert exercise["rep_target"] == "6-10 reps"
        assert exercise["target_weight"] == "40"
        assert exercise["notes"] == "Use a controlled lowering phase."
        assert exercise["sets"][0]["set_number"] == 1
        assert exercise["sets"][0]["target_reps"] == 8
        assert "Rest 2-3 minutes" in workout_block["workout_guidance"][1]["text"]


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


def test_manual_creation_uses_active_semester_and_audits_once(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        service = ScheduleService(session)
        start = _utc(date(2026, 8, 25), time(13, 15))

        occurrence = service.create_occurrence(
            title="  Office hours  ",
            start_utc=start,
            end_utc=start + timedelta(minutes=45),
            calendar_projection=False,
        )

        settings = session.get(AppSettings, 1)
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "block.created",
                AuditEvent.entity_id == occurrence.id,
            )
        )
        assert occurrence.semester_id == semester.id
        assert occurrence.occurrence_date == date(2026, 8, 25)
        assert occurrence.title == "Office hours"
        assert occurrence.revision == 1
        assert occurrence.calendar_projection is False
        assert settings is not None
        assert settings.schedule_revision == 1
        assert audit is not None


def test_timeline_and_manual_creation_span_adjacent_planning_periods(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        fall = _seed_semester(session)
        prep = Semester(
            name="Pre-semester 2026",
            start_date=date(2026, 7, 29),
            end_date=date(2026, 8, 23),
            is_active=False,
        )
        session.add(prep)
        session.flush()
        session.add_all(
            [
                _occurrence(prep, "Prep block", date(2026, 7, 29), time(9)),
                _occurrence(fall, "Fall block", date(2026, 8, 24), time(9)),
            ]
        )
        session.flush()
        service = ScheduleService(session)

        visible = service.list_occurrences(
            _utc(date(2026, 7, 29), time(0)),
            _utc(date(2026, 8, 25), time(0)),
        )
        fall_only = service.list_occurrences(
            _utc(date(2026, 7, 29), time(0)),
            _utc(date(2026, 8, 25), time(0)),
            semester_id=fall.id,
        )
        created = service.create_occurrence(
            title="Pre-semester appointment",
            start_utc=_utc(date(2026, 7, 30), time(14)),
            end_utc=_utc(date(2026, 7, 30), time(15)),
        )
        duplicate = service.duplicate_occurrence(created.id)

        assert [item.title for item in visible] == ["Prep block", "Fall block"]
        assert [item.title for item in fall_only] == ["Fall block"]
        assert created.semester_id == prep.id
        assert duplicate.semester_id == prep.id


def test_manual_creation_rejects_missing_semester_and_invalid_ranges(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        service = ScheduleService(session)
        start = _utc(date(2026, 8, 25), time(13))

        with pytest.raises(ValidationError, match="active semester"):
            service.create_occurrence(
                title="No semester",
                start_utc=start,
                end_utc=start + timedelta(hours=1),
            )

        semester = Semester(
            name="Fall 2026",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        session.add(semester)
        session.flush()
        settings = session.get(AppSettings, 1)
        assert settings is not None
        settings.active_semester_id = semester.id
        session.flush()
        with pytest.raises(ValidationError, match="after start"):
            service.create_occurrence(
                title="Backwards",
                start_utc=start,
                end_utc=start,
            )
        with pytest.raises(ValidationError, match="configured planning period"):
            service.create_occurrence(
                title="Outside semester",
                start_utc=_utc(date(2027, 1, 2), time(9)),
                end_utc=_utc(date(2027, 1, 2), time(10)),
            )


def test_duplicate_detaches_series_and_resets_tracking_children(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        template = BlockTemplate(
            semester=semester,
            title="Lift",
            weekdays=[0],
            local_start_time=time(17),
            duration_minutes=60,
            effective_start_date=semester.start_date,
            effective_end_date=semester.end_date,
        )
        source = _occurrence(
            semester,
            "Lift",
            date(2026, 8, 24),
            time(17),
            template=template,
        )
        source.managed_dataset = "semester"
        source.source_key = "lift:monday"
        source.status = TrackingStatus.COMPLETED
        source.actual_start_utc = source.planned_start_utc
        source.actual_end_utc = source.planned_end_utc
        source.is_override = True
        source.override_reason = "moved by user"
        source.checklist_items = [
            ChecklistItem(
                title="Warm up",
                completed_at=source.planned_start_utc,
            )
        ]
        source.meal_items = [
            MealItem(
                food_name="Shake",
                planned_quantity=Decimal("1"),
                consumed_quantity=Decimal("1.5"),
                calories_per_unit=Decimal("250"),
                protein_grams_per_unit=Decimal("30"),
                completed_at=source.planned_end_utc,
            )
        ]
        source.workout_exercises = [
            WorkoutExercise(
                name="Squat",
                planned_sets=1,
                sets=[
                    WorkoutSet(
                        set_number=1,
                        target_reps=5,
                        actual_reps=5,
                        actual_weight=Decimal("225"),
                        completed_at=source.planned_end_utc,
                    )
                ],
            )
        ]
        source.calendar_link = CalendarEventLink(
            calendar_id="dev-calendar",
            event_id="source-event",
            last_synced_local_revision=1,
        )
        session.add(source)
        session.commit()

        duplicate = ScheduleService(session).duplicate_occurrence(source.id)

        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "block.duplicated",
                AuditEvent.entity_id == duplicate.id,
            )
        )
        settings = session.get(AppSettings, 1)
        assert duplicate.id != source.id
        assert duplicate.template_id is None
        assert duplicate.managed_dataset is None
        assert duplicate.source_key is None
        assert duplicate.status is TrackingStatus.PLANNED
        assert duplicate.actual_start_utc is None
        assert duplicate.actual_end_utc is None
        assert duplicate.is_override is False
        assert duplicate.override_reason is None
        assert duplicate.calendar_link is None
        assert duplicate.revision == 1
        assert duplicate.checklist_items[0].id != source.checklist_items[0].id
        assert duplicate.checklist_items[0].completed_at is None
        assert duplicate.meal_items[0].consumed_quantity is None
        assert duplicate.meal_items[0].completed_at is None
        assert duplicate.workout_exercises[0].sets[0].actual_reps is None
        assert duplicate.workout_exercises[0].sets[0].actual_weight is None
        assert duplicate.workout_exercises[0].sets[0].completed_at is None
        assert settings is not None
        assert settings.schedule_revision == 1
        assert audit is not None
        assert audit.data_json["source_occurrence_id"] == source.id


def test_cancel_is_idempotent_preserves_projection_and_hides_block(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        semester = _seed_semester(session)
        occurrence = _occurrence(semester, "Remove me", date(2026, 8, 24), time(9))
        occurrence.calendar_link = CalendarEventLink(
            calendar_id="dev-calendar",
            event_id="remove-event",
            last_synced_local_revision=1,
        )
        session.add(occurrence)
        session.commit()
        service = ScheduleService(session)

        service.cancel_occurrence(occurrence.id)
        first_revision = occurrence.revision
        service.cancel_occurrence(occurrence.id)

        persisted = session.get(BlockOccurrence, occurrence.id)
        settings = session.get(AppSettings, 1)
        audits = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type == "block.cancelled",
                    AuditEvent.entity_id == occurrence.id,
                )
            )
        )
        assert persisted is occurrence
        assert persisted.cancelled_at is not None
        assert persisted.calendar_link is not None
        assert persisted.calendar_link.event_id == "remove-event"
        assert occurrence.revision == first_revision == 2
        assert service.get_today(date(2026, 8, 24)) == []
        assert settings is not None
        assert settings.schedule_revision == 1
        assert len(audits) == 1


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
