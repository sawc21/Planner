from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from semester_ops.application.common import increment_schedule_revision
from semester_ops.application.errors import NotFoundError
from semester_ops.db.models import (
    BlockOccurrence,
    BlockTemplate,
    ChecklistItem,
    MealItem,
    WorkoutExercise,
    WorkoutSet,
)
from semester_ops.domain.enums import TrackingStatus
from semester_ops.domain.recurrence import WeeklyRecurrence, materialize_weekly
from semester_ops.domain.time import resolve_wall_time


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    created: int = 0
    updated: int = 0
    preserved: int = 0


def occurrence_id_for(template: BlockTemplate, occurrence_date: date) -> str:
    return str(uuid5(NAMESPACE_URL, f"semops:{template.id}:{occurrence_date.isoformat()}"))


class RecurrenceService:
    def __init__(self, session: Session, *, now: datetime | None = None) -> None:
        self.session = session
        self.now = now or datetime.now(UTC)

    def materialize_template(
        self,
        template_id: str,
        *,
        scope_start: date | None = None,
        scope_end: date | None = None,
        bump_revision: bool = True,
    ) -> MaterializationResult:
        template = self.session.get(BlockTemplate, template_id)
        if template is None:
            raise NotFoundError(f"block template {template_id} was not found")
        if template.cancelled_at is not None:
            return MaterializationResult()

        rule = WeeklyRecurrence(
            effective_start=template.effective_start_date,
            effective_end=template.effective_end_date,
            weekdays=frozenset(template.weekdays),
            start_time=template.local_start_time,
            duration_minutes=template.duration_minutes,
            timezone=template.timezone,
            excluded_dates=frozenset(
                date.fromisoformat(value) for value in template.excluded_dates
            ),
        )
        materialized = materialize_weekly(
            rule,
            scope_start=scope_start,
            scope_end=scope_end,
        )
        existing = {
            item.occurrence_date: item
            for item in self.session.scalars(
                select(BlockOccurrence).where(BlockOccurrence.template_id == template.id)
            )
        }
        created = updated = preserved = 0
        for value in materialized:
            occurrence = existing.get(value.occurrence_date)
            if occurrence is None:
                occurrence = self._new_occurrence(template, value.occurrence_date)
                occurrence.planned_start_utc = value.start_utc
                occurrence.planned_end_utc = value.end_utc
                self.session.add(occurrence)
                self._replace_children(occurrence, template.content_json)
                created += 1
                continue
            if not self._safe_to_regenerate(occurrence):
                preserved += 1
                continue
            changed = (
                occurrence.planned_start_utc != value.start_utc
                or occurrence.planned_end_utc != value.end_utc
                or occurrence.title != template.title
                or occurrence.cancelled_at is not None
            )
            self._copy_template_fields(occurrence, template)
            occurrence.planned_start_utc = value.start_utc
            occurrence.planned_end_utc = value.end_utc
            occurrence.cancelled_at = None
            if changed:
                occurrence.revision += 1
                self._replace_children(occurrence, template.content_json)
                updated += 1
            else:
                preserved += 1

        if (created or updated) and bump_revision:
            increment_schedule_revision(self.session)
        self.session.flush()
        return MaterializationResult(created=created, updated=updated, preserved=preserved)

    def _new_occurrence(self, template: BlockTemplate, occurrence_date: date) -> BlockOccurrence:
        occurrence = BlockOccurrence(
            id=occurrence_id_for(template, occurrence_date),
            semester_id=template.semester_id,
            template_id=template.id,
            occurrence_date=occurrence_date,
            title=template.title,
            category=template.category,
            flexibility=template.flexibility,
            description=template.description,
            location=template.location,
            planned_start_utc=self.now,
            planned_end_utc=self.now,
            priority=template.priority,
            preferred_duration_minutes=template.preferred_duration_minutes,
            minimum_duration_minutes=template.minimum_duration_minutes,
            may_split=template.may_split,
            requires_completion=template.requires_completion,
            calendar_projection=template.calendar_projection,
            managed_dataset=template.managed_dataset,
            source_key=(
                f"template:{template.source_key}:{occurrence_date.isoformat()}"
                if template.source_key
                else None
            ),
        )
        self._set_time_windows(occurrence, template)
        return occurrence

    def _copy_template_fields(self, occurrence: BlockOccurrence, template: BlockTemplate) -> None:
        occurrence.title = template.title
        occurrence.category = template.category
        occurrence.flexibility = template.flexibility
        occurrence.description = template.description
        occurrence.location = template.location
        occurrence.priority = template.priority
        occurrence.preferred_duration_minutes = template.preferred_duration_minutes
        occurrence.minimum_duration_minutes = template.minimum_duration_minutes
        occurrence.may_split = template.may_split
        occurrence.requires_completion = template.requires_completion
        occurrence.calendar_projection = template.calendar_projection
        occurrence.managed_dataset = template.managed_dataset
        self._set_time_windows(occurrence, template)

    def _set_time_windows(self, occurrence: BlockOccurrence, template: BlockTemplate) -> None:
        occurrence.earliest_start_utc = (
            resolve_wall_time(
                occurrence.occurrence_date,
                template.earliest_start_time,
                template.timezone,
            ).astimezone(UTC)
            if template.earliest_start_time
            else None
        )
        occurrence.latest_end_utc = (
            resolve_wall_time(
                occurrence.occurrence_date,
                template.latest_end_time,
                template.timezone,
            ).astimezone(UTC)
            if template.latest_end_time
            else None
        )

    @staticmethod
    def _safe_to_regenerate(occurrence: BlockOccurrence) -> bool:
        return (
            occurrence.status is TrackingStatus.PLANNED
            and occurrence.actual_start_utc is None
            and occurrence.actual_end_utc is None
            and not occurrence.is_override
        )

    @staticmethod
    def _replace_children(occurrence: BlockOccurrence, content: dict[str, Any]) -> None:
        if "checklist_items" in content:
            occurrence.checklist_items = [
                ChecklistItem(
                    title=item["title"],
                    required=item.get("required", True),
                    position=item.get("position", index),
                )
                for index, item in enumerate(content["checklist_items"])
            ]
        if "meal_items" in content:
            occurrence.meal_items = [
                MealItem(
                    food_name=item["food_name"],
                    unit=item.get("unit", "serving"),
                    planned_quantity=Decimal(str(item.get("planned_quantity", "1"))),
                    calories_per_unit=Decimal(str(item.get("calories_per_unit", "0"))),
                    protein_grams_per_unit=Decimal(str(item.get("protein_grams_per_unit", "0"))),
                    required=item.get("required", True),
                    position=item.get("position", index),
                )
                for index, item in enumerate(content["meal_items"])
            ]
        if "workout_exercises" not in content:
            return
        occurrence.workout_exercises = []
        for index, item in enumerate(content.get("workout_exercises", [])):
            exercise = WorkoutExercise(
                name=item["name"],
                planned_sets=item.get("planned_sets", 1),
                rep_min=item.get("rep_min"),
                rep_max=item.get("rep_max"),
                target_weight=(
                    Decimal(str(item["target_weight"]))
                    if item.get("target_weight") is not None
                    else None
                ),
                weight_unit=item.get("weight_unit", "lb"),
                required=item.get("required", True),
                position=item.get("position", index),
                notes=item.get("notes"),
            )
            supplied_sets = item.get("sets", [])
            target_reps = item.get("rep_max") or item.get("rep_min")
            exercise.sets = [
                WorkoutSet(
                    set_number=value.get("set_number", set_index),
                    target_reps=value.get("target_reps", target_reps),
                )
                for set_index, value in enumerate(supplied_sets, start=1)
            ] or [
                WorkoutSet(set_number=set_number, target_reps=target_reps)
                for set_number in range(1, exercise.planned_sets + 1)
            ]
            occurrence.workout_exercises.append(exercise)
