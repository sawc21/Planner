from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from semester_ops.application.common import get_or_create_settings
from semester_ops.application.errors import DraftBlockedError, IdempotencyConflictError
from semester_ops.application.imports import ImportService
from semester_ops.application.tracking import TrackingService
from semester_ops.db.base import Base
from semester_ops.db.models import BlockOccurrence, Semester
from semester_ops.domain.enums import DraftStatus, TrackingStatus


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


def import_payload(semester_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "mode": "replace_scope",
        "managed_dataset": "acceptance.schedule",
        "idempotency_key": "acceptance-import-001",
        "base_revision": 0,
        "scope": {
            "semester_id": semester_id,
            "start_date": "2026-08-24",
            "end_date": "2026-08-30",
        },
        "source": {"filename": "schedule.txt"},
        "templates": [
            {
                "source_key": "morning-training",
                "title": "Morning training",
                "category": "workout",
                "flexibility": "flexible",
                "weekdays": [0, 2],
                "start_time": "07:00:00",
                "duration_minutes": 60,
                "effective_start_date": "2026-08-24",
                "effective_end_date": "2026-08-30",
                "checklist_items": [{"title": "Fill water bottle"}],
                "meal_items": [
                    {
                        "food_name": "Protein shake",
                        "planned_quantity": "1",
                        "calories_per_unit": "220",
                        "protein_grams_per_unit": "35",
                    }
                ],
                "workout_exercises": [
                    {"name": "Squat", "planned_sets": 2, "rep_min": 5, "rep_max": 5}
                ],
            }
        ],
    }


def test_reviewed_import_is_idempotent_and_materializes_typed_tracking(
    session: Session,
) -> None:
    semester = Semester(
        name="Fall 2026",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 12, 18),
        is_active=True,
    )
    session.add(semester)
    session.flush()
    settings = get_or_create_settings(session)
    settings.active_semester_id = semester.id
    service = ImportService(session)

    draft = service.create_draft(import_payload(semester.id))
    retried = service.create_draft(import_payload(semester.id))

    assert draft.id == retried.id
    assert draft.status is DraftStatus.READY
    assert len(draft.changes) == 3  # one template and two materialized occurrences

    applied = service.apply_draft(draft.id)
    occurrences = list(
        session.scalars(select(BlockOccurrence).order_by(BlockOccurrence.occurrence_date))
    )

    assert applied.status is DraftStatus.APPLIED
    assert [item.occurrence_date for item in occurrences] == [
        date(2026, 8, 24),
        date(2026, 8, 26),
    ]
    assert occurrences[0].checklist_items[0].title == "Fill water bottle"
    assert occurrences[0].planned_nutrition() == (Decimal("220"), Decimal("35"))
    assert len(occurrences[0].workout_exercises[0].sets) == 2
    assert get_or_create_settings(session).schedule_revision == 1


def test_duplicate_key_with_different_payload_is_rejected(session: Session) -> None:
    semester = Semester(
        name="Fall 2026",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 12, 18),
    )
    session.add(semester)
    session.flush()
    service = ImportService(session)
    payload = import_payload(semester.id)
    service.create_draft(payload)
    changed = import_payload(semester.id)
    changed["assumptions"] = ["This is a different request"]

    with pytest.raises(IdempotencyConflictError):
        service.create_draft(changed)


def test_warning_requires_explicit_approval(session: Session) -> None:
    semester = Semester(
        name="Fall 2026",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 12, 18),
    )
    session.add(semester)
    session.flush()
    payload = import_payload(semester.id)
    payload["occurrences"] = [
        {
            "source_key": "overlap",
            "title": "Overlapping breakfast",
            "category": "meal",
            "occurrence_date": "2026-08-24",
            "start_time": "07:30:00",
            "duration_minutes": 30,
        }
    ]
    service = ImportService(session)
    draft = service.create_draft(payload)

    with pytest.raises(DraftBlockedError):
        service.apply_draft(draft.id)
    service.apply_draft(draft.id, allow_warnings=True)


def test_required_children_auto_complete_parent(session: Session) -> None:
    semester = Semester(
        name="Fall 2026",
        start_date=date(2026, 8, 24),
        end_date=date(2026, 12, 18),
    )
    occurrence = BlockOccurrence(
        semester=semester,
        occurrence_date=date(2026, 8, 24),
        title="Morning routine",
        planned_start_utc=datetime(2026, 8, 24, 12, tzinfo=UTC),
        planned_end_utc=datetime(2026, 8, 24, 13, tzinfo=UTC),
    )
    from semester_ops.db.models import ChecklistItem

    occurrence.checklist_items = [ChecklistItem(title="Make bed", required=True)]
    session.add(occurrence)
    session.flush()

    def clock() -> datetime:
        return datetime(2026, 8, 24, 12, 30, tzinfo=UTC)

    TrackingService(session, now=clock).set_checklist_item_completed(
        occurrence.checklist_items[0].id, True
    )

    assert occurrence.status is TrackingStatus.COMPLETED
    assert occurrence.actual_end_utc == clock()
