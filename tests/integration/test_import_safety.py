from collections.abc import Callable
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from semester_ops.application.common import get_or_create_settings
from semester_ops.application.errors import StaleRevisionError
from semester_ops.application.imports import ImportService
from semester_ops.application.recurrence import RecurrenceService
from semester_ops.application.tracking import TrackingService
from semester_ops.db.base import Base
from semester_ops.db.models import (
    Assignment,
    AssignmentBlockLink,
    BlockOccurrence,
    BlockTemplate,
    ChecklistItem,
    MealItem,
    Semester,
    WorkoutExercise,
    WorkoutSet,
)
from semester_ops.domain.enums import (
    ChangeOperation,
    DraftStatus,
    DuePrecision,
    Flexibility,
    ImportEntityType,
    TrackingStatus,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value


@pytest.fixture
def semester(session: Session) -> Semester:
    value = Semester(
        name="Fall 2026",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 12, 18),
        timezone="America/Chicago",
        is_active=True,
    )
    session.add(value)
    session.flush()
    settings = get_or_create_settings(session)
    settings.active_semester_id = value.id
    session.flush()
    return value


def patch_payload(
    semester: Semester,
    *,
    managed_dataset: str,
    operations: list[dict[str, object]],
    base_revision: int | None = None,
    scope_start: date = date(2026, 8, 24),
    scope_end: date = date(2026, 9, 6),
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "mode": "patch",
        "managed_dataset": managed_dataset,
        "idempotency_key": f"safety-{uuid4()}",
        "base_revision": base_revision if base_revision is not None else 0,
        "scope": {
            "semester_id": semester.id,
            "start_date": scope_start.isoformat(),
            "end_date": scope_end.isoformat(),
        },
        "source": {"filename": "planning.json"},
        "operations": operations,
    }


def occurrence_value(
    *,
    source_key: str,
    occurrence_date: date = date(2026, 8, 24),
    start_time: str = "07:00:00",
    duration_minutes: int = 60,
    title: str = "Study block",
    flexibility: str = "flexible",
    assignment_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_key": source_key,
        "title": title,
        "category": "study",
        "flexibility": flexibility,
        "occurrence_date": occurrence_date.isoformat(),
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "assignment_ids": assignment_ids or [],
    }


def template_value(
    *,
    source_key: str = "study-routine",
    weekdays: list[int] | None = None,
    start_time: str = "07:00:00",
) -> dict[str, object]:
    return {
        "source_key": source_key,
        "title": "Study routine",
        "category": "study",
        "flexibility": "flexible",
        "weekdays": weekdays or [0, 2],
        "start_time": start_time,
        "duration_minutes": 60,
        "effective_start_date": "2026-08-24",
        "effective_end_date": "2026-09-06",
    }


def stored_occurrence(
    semester: Semester,
    *,
    managed_dataset: str | None,
    source_key: str,
    occurrence_date: date = date(2026, 8, 24),
    start: datetime = datetime(2026, 8, 24, 12, tzinfo=UTC),
    end: datetime = datetime(2026, 8, 24, 13, tzinfo=UTC),
    template: BlockTemplate | None = None,
    flexibility: Flexibility = Flexibility.FLEXIBLE,
) -> BlockOccurrence:
    return BlockOccurrence(
        semester=semester,
        template=template,
        occurrence_date=occurrence_date,
        title="Stored block",
        flexibility=flexibility,
        planned_start_utc=start,
        planned_end_utc=end,
        managed_dataset=managed_dataset,
        source_key=source_key,
    )


def test_moving_an_existing_fixed_occurrence_blocks_the_draft(
    session: Session, semester: Semester
) -> None:
    occurrence = stored_occurrence(
        semester,
        managed_dataset="planning.schedule",
        source_key="fixed-class",
        flexibility=Flexibility.FIXED,
    )
    session.add(occurrence)
    session.flush()

    draft = ImportService(session).create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": "fixed-class",
                    "value": occurrence_value(
                        source_key="fixed-class",
                        start_time="08:00:00",
                        flexibility="fixed",
                    ),
                }
            ],
        )
    )

    assert draft.status is DraftStatus.BLOCKED
    assert any(issue.code == "fixed_occurrence_move" and issue.blocking for issue in draft.issues)


def test_direct_occurrence_update_becomes_a_durable_template_override(
    session: Session, semester: Semester
) -> None:
    template = BlockTemplate(
        semester=semester,
        title="Study routine",
        weekdays=[0],
        local_start_time=time(7),
        duration_minutes=60,
        effective_start_date=date(2026, 8, 24),
        effective_end_date=date(2026, 8, 24),
        managed_dataset="planning.schedule",
        source_key="study-routine",
    )
    occurrence = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-24",
    )
    session.add_all((template, occurrence))
    session.flush()

    service = ImportService(session)
    draft = service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": occurrence.source_key,
                    "value": occurrence_value(
                        source_key=occurrence.source_key or "missing",
                        start_time="08:00:00",
                    ),
                }
            ],
            scope_end=date(2026, 8, 24),
        )
    )

    assert draft.status is DraftStatus.READY
    change = next(
        change for change in draft.changes if change.entity_type is ImportEntityType.OCCURRENCE
    )
    assert change.after_json is not None
    assert change.after_json["template_id"] == template.id
    assert change.after_json["mark_as_override"] is True

    service.apply_draft(draft.id)

    assert occurrence.template_id == template.id
    assert occurrence.is_override is True
    assert occurrence.override_reason == "updated by reviewed occurrence patch"
    assert occurrence.planned_start_utc == datetime(2026, 8, 24, 13, tzinfo=UTC)

    regenerated = RecurrenceService(session).materialize_template(
        template.id,
        scope_start=date(2026, 8, 24),
        scope_end=date(2026, 8, 24),
        bump_revision=False,
    )
    assert regenerated.preserved == 1
    assert occurrence.planned_start_utc == datetime(2026, 8, 24, 13, tzinfo=UTC)


def test_direct_occurrence_cancel_becomes_a_durable_template_override(
    session: Session, semester: Semester
) -> None:
    template = BlockTemplate(
        semester=semester,
        title="Study routine",
        weekdays=[0],
        local_start_time=time(7),
        duration_minutes=60,
        effective_start_date=date(2026, 8, 24),
        effective_end_date=date(2026, 8, 24),
        managed_dataset="planning.schedule",
        source_key="study-routine",
    )
    occurrence = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-24",
    )
    session.add_all((template, occurrence))
    session.flush()

    service = ImportService(session)
    draft = service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "cancel",
                    "entity_type": "occurrence",
                    "target_source_key": occurrence.source_key,
                }
            ],
            scope_end=date(2026, 8, 24),
        )
    )
    service.apply_draft(draft.id)

    assert occurrence.cancelled_at is not None
    assert occurrence.template_id == template.id
    assert occurrence.is_override is True
    assert occurrence.override_reason == "cancelled by reviewed occurrence patch"

    regenerated = RecurrenceService(session).materialize_template(
        template.id,
        scope_start=date(2026, 8, 24),
        scope_end=date(2026, 8, 24),
        bump_revision=False,
    )
    assert regenerated.preserved == 1
    assert occurrence.cancelled_at is not None


def test_cross_date_occurrence_patch_preserves_the_template_recurrence_identity(
    session: Session, semester: Semester
) -> None:
    template = BlockTemplate(
        semester=semester,
        title="Study routine",
        weekdays=[0, 1],
        local_start_time=time(7),
        duration_minutes=60,
        effective_start_date=date(2026, 8, 24),
        effective_end_date=date(2026, 8, 25),
        managed_dataset="planning.schedule",
        source_key="study-routine",
    )
    monday = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-24",
    )
    tuesday = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-25",
        occurrence_date=date(2026, 8, 25),
        start=datetime(2026, 8, 25, 12, tzinfo=UTC),
        end=datetime(2026, 8, 25, 13, tzinfo=UTC),
    )
    session.add_all((template, monday, tuesday))
    session.flush()

    service = ImportService(session)
    draft = service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": monday.source_key,
                    "value": occurrence_value(
                        source_key=monday.source_key or "missing",
                        occurrence_date=date(2026, 8, 25),
                        start_time="08:00:00",
                    ),
                }
            ],
            scope_end=date(2026, 8, 25),
        )
    )

    assert draft.status is DraftStatus.READY
    service.apply_draft(draft.id)

    assert monday.occurrence_date == date(2026, 8, 24)
    assert monday.planned_start_utc == datetime(2026, 8, 25, 13, tzinfo=UTC)
    assert monday.is_override is True
    assert tuesday.occurrence_date == date(2026, 8, 25)


@pytest.mark.parametrize(
    ("precision", "due_date", "due_at_utc", "start_time"),
    [
        (DuePrecision.DATE, date(2026, 8, 24), None, "23:30:00"),
        (
            DuePrecision.DATETIME,
            None,
            datetime(2026, 8, 24, 14, tzinfo=UTC),
            "08:30:00",
        ),
    ],
)
def test_occurrence_cannot_end_after_a_linked_assignment_planning_deadline(
    session: Session,
    semester: Semester,
    precision: DuePrecision,
    due_date: date | None,
    due_at_utc: datetime | None,
    start_time: str,
) -> None:
    assignment = Assignment(
        external_uid=f"assignment-{precision.value}",
        title="Lab report",
        due_precision=precision,
        due_date=due_date,
        due_at_utc=due_at_utc,
    )
    occurrence = stored_occurrence(
        semester,
        managed_dataset="planning.schedule",
        source_key=f"late-{precision.value}",
    )
    occurrence.assignment_links = [AssignmentBlockLink(assignment=assignment)]
    session.add(occurrence)
    session.flush()

    value = occurrence_value(
        source_key=occurrence.source_key or "missing",
        start_time=start_time,
    )
    value.pop("assignment_ids")

    draft = ImportService(session).create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": occurrence.source_key,
                    "value": value,
                }
            ],
        )
    )

    assert draft.status is DraftStatus.BLOCKED
    assert any(
        issue.code == "assignment_deadline_exceeded" and issue.blocking for issue in draft.issues
    )


def test_template_cancel_only_soft_cancels_safe_occurrences_in_scope(
    session: Session, semester: Semester
) -> None:
    template = BlockTemplate(
        semester=semester,
        title="Study routine",
        weekdays=[0, 1, 2, 3],
        local_start_time=time(7),
        duration_minutes=60,
        effective_start_date=date(2026, 8, 24),
        effective_end_date=date(2026, 9, 6),
        managed_dataset="planning.schedule",
        source_key="study-routine",
    )
    safe = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-24",
    )
    tracked = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-25",
        occurrence_date=date(2026, 8, 25),
        start=datetime(2026, 8, 25, 12, tzinfo=UTC),
        end=datetime(2026, 8, 25, 13, tzinfo=UTC),
    )
    tracked.status = TrackingStatus.COMPLETED
    overridden = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-26",
        occurrence_date=date(2026, 8, 26),
        start=datetime(2026, 8, 26, 12, tzinfo=UTC),
        end=datetime(2026, 8, 26, 13, tzinfo=UTC),
    )
    overridden.is_override = True
    partial = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-27",
        occurrence_date=date(2026, 8, 27),
        start=datetime(2026, 8, 27, 12, tzinfo=UTC),
        end=datetime(2026, 8, 27, 13, tzinfo=UTC),
    )
    partial.checklist_items = [
        ChecklistItem(title="Read notes", completed_at=datetime(2026, 8, 27, 12, 15, tzinfo=UTC))
    ]
    session.add_all([template, safe, tracked, overridden, partial])
    session.flush()

    service = ImportService(session)
    draft = service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "cancel",
                    "entity_type": "template",
                    "target_source_key": "study-routine",
                }
            ],
        )
    )

    canceled_targets = {
        change.target_id for change in draft.changes if change.operation is ChangeOperation.CANCEL
    }
    assert canceled_targets == {template.id, safe.id}
    assert sum(issue.code == "tracked_occurrence_preserved" for issue in draft.issues) == 3

    service.apply_draft(draft.id, allow_warnings=True)

    assert template.cancelled_at is not None
    assert safe.cancelled_at is not None
    assert tracked.cancelled_at is None
    assert overridden.cancelled_at is None
    assert partial.cancelled_at is None


def test_template_update_reconciles_safe_dates_and_preserves_history(
    session: Session, semester: Semester
) -> None:
    template = BlockTemplate(
        semester=semester,
        title="Study routine",
        weekdays=[0, 2],
        local_start_time=time(7),
        duration_minutes=60,
        effective_start_date=date(2026, 8, 24),
        effective_end_date=date(2026, 9, 6),
        managed_dataset="planning.schedule",
        source_key="study-routine",
    )
    monday_safe = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-24",
    )
    wednesday_safe = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-26",
        occurrence_date=date(2026, 8, 26),
        start=datetime(2026, 8, 26, 12, tzinfo=UTC),
        end=datetime(2026, 8, 26, 13, tzinfo=UTC),
    )
    monday_tracked = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-08-31",
        occurrence_date=date(2026, 8, 31),
        start=datetime(2026, 8, 31, 12, tzinfo=UTC),
        end=datetime(2026, 8, 31, 13, tzinfo=UTC),
    )
    monday_tracked.status = TrackingStatus.COMPLETED
    wednesday_override = stored_occurrence(
        semester,
        template=template,
        managed_dataset="planning.schedule",
        source_key="template:study-routine:2026-09-02",
        occurrence_date=date(2026, 9, 2),
        start=datetime(2026, 9, 2, 12, tzinfo=UTC),
        end=datetime(2026, 9, 2, 13, tzinfo=UTC),
    )
    wednesday_override.is_override = True
    session.add_all([template, monday_safe, wednesday_safe, monday_tracked, wednesday_override])
    session.flush()

    service = ImportService(session)
    draft = service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "template",
                    "target_source_key": "study-routine",
                    "value": template_value(weekdays=[0, 4], start_time="08:00:00"),
                }
            ],
        )
    )

    occurrence_changes = [
        change for change in draft.changes if change.entity_type is ImportEntityType.OCCURRENCE
    ]
    assert any(
        change.operation is ChangeOperation.UPDATE and change.target_id == monday_safe.id
        for change in occurrence_changes
    )
    assert any(
        change.operation is ChangeOperation.CANCEL and change.target_id == wednesday_safe.id
        for change in occurrence_changes
    )
    assert sum(change.operation is ChangeOperation.ADD for change in occurrence_changes) == 2
    assert sum(issue.code == "tracked_occurrence_preserved" for issue in draft.issues) == 2

    service.apply_draft(draft.id, allow_warnings=True)

    assert template.weekdays == [0, 4]
    assert template.local_start_time == time(8)
    assert monday_safe.planned_start_utc == datetime(2026, 8, 24, 13, tzinfo=UTC)
    assert wednesday_safe.cancelled_at is not None
    assert monday_tracked.cancelled_at is None
    assert monday_tracked.planned_start_utc == datetime(2026, 8, 31, 12, tzinfo=UTC)
    assert wednesday_override.cancelled_at is None
    friday_dates = set(
        session.scalars(
            select(BlockOccurrence.occurrence_date).where(
                BlockOccurrence.template_id == template.id,
                BlockOccurrence.cancelled_at.is_(None),
                BlockOccurrence.occurrence_date.in_([date(2026, 8, 28), date(2026, 9, 4)]),
            )
        )
    )
    assert friday_dates == {date(2026, 8, 28), date(2026, 9, 4)}


ChildMutation = Callable[[TrackingService, BlockOccurrence], None]


def _checklist_mutation(service: TrackingService, occurrence: BlockOccurrence) -> None:
    service.set_checklist_item_completed(occurrence.checklist_items[0].id, True)


def _meal_mutation(service: TrackingService, occurrence: BlockOccurrence) -> None:
    service.set_meal_item_completed(
        occurrence.meal_items[0].id,
        True,
        consumed_quantity=Decimal("0.5"),
    )


def _workout_mutation(service: TrackingService, occurrence: BlockOccurrence) -> None:
    service.complete_workout_set(
        occurrence.workout_exercises[0].sets[0].id,
        True,
        actual_reps=5,
        actual_weight=Decimal("100"),
    )


@pytest.mark.parametrize(
    ("kind", "mutate"),
    [
        ("checklist", _checklist_mutation),
        ("meal", _meal_mutation),
        ("workout", _workout_mutation),
    ],
)
def test_partial_execution_preserves_occurrence_and_invalidates_existing_draft(
    session: Session,
    semester: Semester,
    kind: str,
    mutate: ChildMutation,
) -> None:
    occurrence = stored_occurrence(
        semester,
        managed_dataset="planning.schedule",
        source_key=f"partial-{kind}",
    )
    if kind == "checklist":
        occurrence.checklist_items = [
            ChecklistItem(title="First", required=True),
            ChecklistItem(title="Second", required=True),
        ]
    elif kind == "meal":
        occurrence.meal_items = [
            MealItem(food_name="First", required=True),
            MealItem(food_name="Second", required=True),
        ]
    else:
        occurrence.workout_exercises = [
            WorkoutExercise(
                name="Squat",
                planned_sets=2,
                required=True,
                sets=[WorkoutSet(set_number=1), WorkoutSet(set_number=2)],
            )
        ]
    session.add(occurrence)
    session.flush()

    import_service = ImportService(session)
    racing_draft = import_service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "add",
                    "entity_type": "occurrence",
                    "value": occurrence_value(
                        source_key=f"unrelated-{kind}",
                        occurrence_date=date(2026, 8, 25),
                    ),
                }
            ],
        )
    )
    assert racing_draft.status is DraftStatus.READY

    mutate(
        TrackingService(
            session,
            now=lambda: datetime(2026, 8, 24, 12, 30, tzinfo=UTC),
        ),
        occurrence,
    )

    assert occurrence.status is TrackingStatus.PLANNED
    assert occurrence.revision == 2
    assert get_or_create_settings(session).schedule_revision == 1
    with pytest.raises(StaleRevisionError):
        import_service.apply_draft(racing_draft.id)

    replacement = import_service.create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            base_revision=1,
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": occurrence.source_key,
                    "value": occurrence_value(
                        source_key=occurrence.source_key or "missing",
                        start_time="08:00:00",
                    ),
                }
            ],
        )
    )
    assert replacement.status is DraftStatus.READY
    assert not any(
        change.entity_type is ImportEntityType.OCCURRENCE for change in replacement.changes
    )
    assert any(issue.code == "tracked_occurrence_preserved" for issue in replacement.issues)


def test_proposed_schedule_warns_when_it_overlaps_an_active_other_dataset_block(
    session: Session, semester: Semester
) -> None:
    session.add(
        stored_occurrence(
            semester,
            managed_dataset="manual.schedule",
            source_key="manual-class",
        )
    )
    session.flush()
    payload = {
        "schema_version": "1.0",
        "mode": "replace_scope",
        "managed_dataset": "planning.schedule",
        "idempotency_key": f"safety-{uuid4()}",
        "base_revision": 0,
        "scope": {
            "semester_id": semester.id,
            "start_date": "2026-08-24",
            "end_date": "2026-08-24",
        },
        "source": {"filename": "planning.json"},
        "occurrences": [
            occurrence_value(
                source_key="planned-study",
                start_time="07:30:00",
                duration_minutes=30,
            )
        ],
    }

    draft = ImportService(session).create_draft(payload)

    assert any(
        issue.code == "schedule_overlap" and "existing block" in issue.message
        for issue in draft.issues
    )


def test_updating_an_occurrence_does_not_report_an_overlap_with_itself(
    session: Session, semester: Semester
) -> None:
    occurrence = stored_occurrence(
        semester,
        managed_dataset="planning.schedule",
        source_key="same-block",
    )
    session.add(occurrence)
    session.flush()

    draft = ImportService(session).create_draft(
        patch_payload(
            semester,
            managed_dataset="planning.schedule",
            operations=[
                {
                    "operation": "update",
                    "entity_type": "occurrence",
                    "target_source_key": "same-block",
                    "value": occurrence_value(
                        source_key="same-block",
                        title="Renamed block",
                    ),
                }
            ],
        )
    )

    assert not any(issue.code == "schedule_overlap" for issue in draft.issues)
