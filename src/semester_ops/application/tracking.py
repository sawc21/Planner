from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from semester_ops.application.common import add_audit_event, increment_schedule_revision
from semester_ops.application.errors import NotFoundError, ValidationError
from semester_ops.db.models import (
    BlockOccurrence,
    ChecklistItem,
    MealItem,
    WorkoutSet,
)
from semester_ops.domain.enums import TrackingStatus
from semester_ops.domain.time import as_utc
from semester_ops.domain.tracking import require_transition


class TrackingService:
    def __init__(
        self,
        session: Session,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self._now = now or (lambda: datetime.now(UTC))

    def start_occurrence(self, occurrence_id: str) -> BlockOccurrence:
        occurrence = self._occurrence(occurrence_id)
        require_transition(occurrence.status, TrackingStatus.IN_PROGRESS)
        when = as_utc(self._now())
        occurrence.status = TrackingStatus.IN_PROGRESS
        occurrence.actual_start_utc = occurrence.actual_start_utc or when
        occurrence.actual_end_utc = None
        self._record_status(occurrence, "block.started")
        return occurrence

    def complete_occurrence(self, occurrence_id: str) -> BlockOccurrence:
        occurrence = self._occurrence(occurrence_id)
        require_transition(occurrence.status, TrackingStatus.COMPLETED)
        occurrence.status = TrackingStatus.COMPLETED
        occurrence.actual_end_utc = as_utc(self._now())
        self._record_status(occurrence, "block.completed")
        return occurrence

    def skip_occurrence(self, occurrence_id: str) -> BlockOccurrence:
        occurrence = self._occurrence(occurrence_id)
        require_transition(occurrence.status, TrackingStatus.SKIPPED)
        occurrence.status = TrackingStatus.SKIPPED
        occurrence.actual_end_utc = None
        self._record_status(occurrence, "block.skipped")
        return occurrence

    def reopen_occurrence(self, occurrence_id: str) -> BlockOccurrence:
        occurrence = self._occurrence(occurrence_id)
        target = (
            TrackingStatus.IN_PROGRESS
            if occurrence.actual_start_utc is not None
            and occurrence.status is TrackingStatus.COMPLETED
            else TrackingStatus.PLANNED
        )
        require_transition(occurrence.status, target)
        occurrence.status = target
        occurrence.actual_end_utc = None
        if target is TrackingStatus.PLANNED:
            occurrence.actual_start_utc = None
        self._record_status(occurrence, "block.reopened")
        return occurrence

    def set_status(self, occurrence_id: str, status: TrackingStatus | str) -> BlockOccurrence:
        target = TrackingStatus(status)
        if target is TrackingStatus.IN_PROGRESS:
            return self.start_occurrence(occurrence_id)
        if target is TrackingStatus.COMPLETED:
            return self.complete_occurrence(occurrence_id)
        if target is TrackingStatus.SKIPPED:
            return self.skip_occurrence(occurrence_id)
        if target is TrackingStatus.PLANNED:
            return self.reopen_occurrence(occurrence_id)
        raise ValidationError("missed is derived and cannot be stored")

    def set_checklist_item_completed(self, item_id: str, completed: bool) -> ChecklistItem:
        item = self.session.get(ChecklistItem, item_id)
        if item is None:
            raise NotFoundError(f"checklist item {item_id} was not found")
        item.completed_at = as_utc(self._now()) if completed else None
        if completed:
            item.skipped_at = None
        self._after_child_change(item.occurrence)
        add_audit_event(
            self.session,
            event_type="checklist.completed" if completed else "checklist.reopened",
            entity_type="checklist_item",
            entity_id=item.id,
        )
        self.session.flush()
        return item

    def set_meal_item_completed(
        self,
        item_id: str,
        completed: bool,
        *,
        consumed_quantity: Decimal | None = None,
    ) -> MealItem:
        item = self.session.get(MealItem, item_id)
        if item is None:
            raise NotFoundError(f"meal item {item_id} was not found")
        if consumed_quantity is not None and consumed_quantity < 0:
            raise ValidationError("consumed quantity cannot be negative")
        item.completed_at = as_utc(self._now()) if completed else None
        item.consumed_quantity = consumed_quantity if completed else None
        self._after_child_change(item.occurrence)
        add_audit_event(
            self.session,
            event_type="meal.consumed" if completed else "meal.reopened",
            entity_type="meal_item",
            entity_id=item.id,
            data={"consumed_quantity": str(consumed_quantity) if consumed_quantity else None},
        )
        self.session.flush()
        return item

    def complete_workout_set(
        self,
        set_id: str,
        completed: bool,
        *,
        actual_reps: int | None = None,
        actual_weight: Decimal | None = None,
    ) -> WorkoutSet:
        workout_set = self.session.get(WorkoutSet, set_id)
        if workout_set is None:
            raise NotFoundError(f"workout set {set_id} was not found")
        if actual_reps is not None and actual_reps < 0:
            raise ValidationError("actual reps cannot be negative")
        if actual_weight is not None and actual_weight < 0:
            raise ValidationError("actual weight cannot be negative")
        workout_set.completed_at = as_utc(self._now()) if completed else None
        workout_set.actual_reps = actual_reps if completed else None
        workout_set.actual_weight = actual_weight if completed else None
        self._after_child_change(workout_set.exercise.occurrence)
        add_audit_event(
            self.session,
            event_type="workout.set_completed" if completed else "workout.set_reopened",
            entity_type="workout_set",
            entity_id=workout_set.id,
        )
        self.session.flush()
        return workout_set

    def _after_child_change(self, occurrence: BlockOccurrence) -> None:
        auto_completed = False
        if occurrence.status not in {TrackingStatus.COMPLETED, TrackingStatus.SKIPPED}:
            required_states: list[bool] = [
                item.completed_at is not None or item.skipped_at is not None
                for item in occurrence.checklist_items
                if item.required
            ]
            required_states.extend(
                item.completed_at is not None for item in occurrence.meal_items if item.required
            )
            for exercise in occurrence.workout_exercises:
                if exercise.required:
                    required_states.extend(item.completed_at is not None for item in exercise.sets)
            if required_states and all(required_states):
                occurrence.status = TrackingStatus.COMPLETED
                occurrence.actual_end_utc = as_utc(self._now())
                auto_completed = True

        occurrence.revision += 1
        increment_schedule_revision(self.session)
        if auto_completed:
            add_audit_event(
                self.session,
                event_type="block.auto_completed",
                entity_type="block_occurrence",
                entity_id=occurrence.id,
                data={"status": occurrence.status.value},
            )

    def _record_status(self, occurrence: BlockOccurrence, event_type: str) -> None:
        occurrence.revision += 1
        increment_schedule_revision(self.session)
        add_audit_event(
            self.session,
            event_type=event_type,
            entity_type="block_occurrence",
            entity_id=occurrence.id,
            data={"status": occurrence.status.value},
        )
        self.session.flush()

    def _occurrence(self, occurrence_id: str) -> BlockOccurrence:
        occurrence = self.session.get(BlockOccurrence, occurrence_id)
        if occurrence is None or occurrence.cancelled_at is not None:
            raise NotFoundError(f"block occurrence {occurrence_id} was not found")
        return occurrence
