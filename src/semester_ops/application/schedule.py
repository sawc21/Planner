from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from semester_ops.application.common import (
    add_audit_event,
    get_or_create_settings,
    increment_schedule_revision,
)
from semester_ops.application.errors import NotFoundError, ValidationError
from semester_ops.db.models import (
    AppSettings,
    BlockOccurrence,
    Semester,
    WorkoutExercise,
    utc_now,
)
from semester_ops.domain.time import as_utc, operational_day_bounds
from semester_ops.domain.tracking import effective_status


@dataclass(frozen=True, slots=True)
class NutritionTotals:
    planned_calories: Decimal = Decimal("0")
    planned_protein_grams: Decimal = Decimal("0")
    consumed_calories: Decimal = Decimal("0")
    consumed_protein_grams: Decimal = Decimal("0")

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(frozen=True, slots=True)
class ScheduleConflict:
    first_occurrence_id: str
    second_occurrence_id: str
    overlap_start_utc: datetime
    overlap_end_utc: datetime


class ScheduleService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_settings(self) -> AppSettings:
        return get_or_create_settings(self.session)

    def create_semester(
        self,
        *,
        name: str,
        start_date: date,
        end_date: date,
        timezone: str = "America/Chicago",
        activate: bool = True,
    ) -> Semester:
        if end_date < start_date:
            raise ValidationError("semester end date must be on or after start date")
        if timezone != "America/Chicago":
            raise ValidationError("v1 supports America/Chicago only")
        if activate:
            for semester in self.session.scalars(select(Semester).where(Semester.is_active)):
                semester.is_active = False
        semester = Semester(
            name=name.strip(),
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            is_active=activate,
        )
        if not semester.name:
            raise ValidationError("semester name is required")
        self.session.add(semester)
        self.session.flush()
        settings = get_or_create_settings(self.session)
        if activate:
            settings.active_semester_id = semester.id
        increment_schedule_revision(self.session)
        add_audit_event(
            self.session,
            event_type="semester.created",
            entity_type="semester",
            entity_id=semester.id,
        )
        self.session.flush()
        return semester

    def list_occurrences(
        self,
        start_utc: datetime,
        end_utc: datetime,
        *,
        semester_id: str | None = None,
        include_cancelled: bool = False,
    ) -> list[BlockOccurrence]:
        start = as_utc(start_utc, field="start_utc")
        end = as_utc(end_utc, field="end_utc")
        if end <= start:
            raise ValidationError("end_utc must be after start_utc")
        settings = get_or_create_settings(self.session)
        resolved_semester_id = semester_id or settings.active_semester_id
        statement = (
            select(BlockOccurrence)
            .options(
                selectinload(BlockOccurrence.checklist_items),
                selectinload(BlockOccurrence.meal_items),
                selectinload(BlockOccurrence.workout_exercises).selectinload(WorkoutExercise.sets),
            )
            .where(
                BlockOccurrence.planned_start_utc < end,
                BlockOccurrence.planned_end_utc > start,
            )
            .order_by(BlockOccurrence.planned_start_utc, BlockOccurrence.id)
        )
        if resolved_semester_id:
            statement = statement.where(BlockOccurrence.semester_id == resolved_semester_id)
        if not include_cancelled:
            statement = statement.where(BlockOccurrence.cancelled_at.is_(None))
        return list(self.session.scalars(statement))

    def get_today(self, day: date, *, now_utc: datetime | None = None) -> list[BlockOccurrence]:
        settings = get_or_create_settings(self.session)
        start, end = operational_day_bounds(
            day,
            settings.timezone,
            settings.operational_day_boundary,
        )
        occurrences = self.list_occurrences(start, end)
        now = as_utc(now_utc or datetime.now(UTC))
        for occurrence in occurrences:
            # Accessing this once keeps the derived rule close to query behavior for adapters.
            effective_status(
                occurrence.status,
                planned_end_utc=occurrence.planned_end_utc,
                now_utc=now,
                requires_completion=occurrence.requires_completion,
                grace_minutes=settings.missed_grace_minutes,
            )
        return occurrences

    def get_week(self, start_date: date) -> list[BlockOccurrence]:
        settings = get_or_create_settings(self.session)
        start, _ = operational_day_bounds(
            start_date,
            settings.timezone,
            settings.operational_day_boundary,
        )
        end, _ = operational_day_bounds(
            start_date + timedelta(days=7),
            settings.timezone,
            settings.operational_day_boundary,
        )
        return self.list_occurrences(start, end)

    def move_occurrence(
        self,
        occurrence_id: str,
        start_utc: datetime,
        end_utc: datetime,
        *,
        actor: str = "user",
        automated: bool = False,
    ) -> BlockOccurrence:
        occurrence = self.session.get(BlockOccurrence, occurrence_id)
        if occurrence is None or occurrence.cancelled_at is not None:
            raise NotFoundError(f"block occurrence {occurrence_id} was not found")
        start = as_utc(start_utc, field="start_utc")
        end = as_utc(end_utc, field="end_utc")
        if end <= start:
            raise ValidationError("end_utc must be after start_utc")
        if automated and occurrence.flexibility.value == "fixed":
            raise ValidationError("automated planning cannot move a fixed block")
        before = {
            "start_utc": occurrence.planned_start_utc.isoformat(),
            "end_utc": occurrence.planned_end_utc.isoformat(),
        }
        occurrence.planned_start_utc = start
        occurrence.planned_end_utc = end
        if occurrence.template_id is None:
            settings = get_or_create_settings(self.session)
        # A generated occurrence's date is its recurrence identity. Moving it across
        # midnight changes its planned instant, not the template/date identity.
        if occurrence.template_id is None:
            occurrence.occurrence_date = start.astimezone(ZoneInfo(settings.timezone)).date()
        occurrence.is_override = occurrence.template_id is not None
        occurrence.override_reason = f"moved by {actor}"
        occurrence.revision += 1
        increment_schedule_revision(self.session)
        add_audit_event(
            self.session,
            event_type="block.moved",
            entity_type="block_occurrence",
            entity_id=occurrence.id,
            actor=actor,
            data={
                "before": before,
                "after": {"start_utc": start.isoformat(), "end_utc": end.isoformat()},
            },
        )
        self.session.flush()
        return occurrence

    def cancel_occurrence(self, occurrence_id: str, *, actor: str = "user") -> BlockOccurrence:
        occurrence = self.session.get(BlockOccurrence, occurrence_id)
        if occurrence is None:
            raise NotFoundError(f"block occurrence {occurrence_id} was not found")
        if occurrence.cancelled_at is None:
            occurrence.cancelled_at = utc_now()
            occurrence.revision += 1
            increment_schedule_revision(self.session)
            add_audit_event(
                self.session,
                event_type="block.cancelled",
                entity_type="block_occurrence",
                entity_id=occurrence.id,
                actor=actor,
            )
            self.session.flush()
        return occurrence

    @staticmethod
    def nutrition_totals(occurrences: list[BlockOccurrence]) -> NutritionTotals:
        planned_calories = planned_protein = Decimal("0")
        consumed_calories = consumed_protein = Decimal("0")
        for occurrence in occurrences:
            block_planned_calories, block_planned_protein = occurrence.planned_nutrition()
            block_consumed_calories, block_consumed_protein = occurrence.consumed_nutrition()
            planned_calories += block_planned_calories
            planned_protein += block_planned_protein
            consumed_calories += block_consumed_calories
            consumed_protein += block_consumed_protein
        return NutritionTotals(
            planned_calories=planned_calories,
            planned_protein_grams=planned_protein,
            consumed_calories=consumed_calories,
            consumed_protein_grams=consumed_protein,
        )

    @staticmethod
    def conflicts(occurrences: list[BlockOccurrence]) -> list[ScheduleConflict]:
        active = sorted(
            (item for item in occurrences if item.cancelled_at is None),
            key=lambda item: item.planned_start_utc,
        )
        conflicts: list[ScheduleConflict] = []
        for index, first in enumerate(active):
            for second in active[index + 1 :]:
                if second.planned_start_utc >= first.planned_end_utc:
                    break
                overlap_start = max(first.planned_start_utc, second.planned_start_utc)
                overlap_end = min(first.planned_end_utc, second.planned_end_utc)
                if overlap_end > overlap_start:
                    conflicts.append(
                        ScheduleConflict(
                            first_occurrence_id=first.id,
                            second_occurrence_id=second.id,
                            overlap_start_utc=overlap_start,
                            overlap_end_utc=overlap_end,
                        )
                    )
        return conflicts
