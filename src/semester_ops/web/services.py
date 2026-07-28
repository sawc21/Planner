from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from semester_ops.db.session import get_session_factory

type ViewData = dict[str, Any]


@dataclass(frozen=True, slots=True)
class BlockEditCommand:
    title: str
    planned_start_local: datetime
    planned_end_local: datetime
    category: str
    flexibility: str
    notes: str | None
    project_to_calendar: bool


@dataclass(frozen=True, slots=True)
class MealItemCommand:
    completed: bool
    consumed_quantity: Decimal | None


@dataclass(frozen=True, slots=True)
class WorkoutSetCommand:
    completed: bool
    actual_reps: int | None
    actual_weight: Decimal | None


@dataclass(frozen=True, slots=True)
class SettingsCommand:
    timezone: str
    operational_day_start: str
    missed_grace_minutes: int
    calorie_target: int | None
    protein_target_grams: int | None
    weight_unit: str
    blackboard_ics_url: str | None
    clear_blackboard_ics: bool = False


@runtime_checkable
class WebServices(Protocol):
    """Application facade consumed by the HTTP adapter.

    View methods return plain dictionaries so templates are insulated from ORM
    objects. Mutation methods retain domain validation in the application layer.
    """

    def get_today(self, day: date | None = None) -> ViewData: ...

    def get_week(self, anchor: date | None = None) -> ViewData: ...

    def list_assignments(self, state: str | None = None) -> ViewData: ...

    def list_imports(self) -> ViewData: ...

    def get_import(self, draft_id: str) -> ViewData: ...

    def get_settings_view(self) -> ViewData: ...

    def get_block(self, block_id: str) -> ViewData: ...

    def set_block_status(self, block_id: str, action: str) -> Mapping[str, Any] | None: ...

    def update_block(self, block_id: str, command: BlockEditCommand) -> None: ...

    def move_block(self, block_id: str, minutes: int) -> None: ...

    def set_checklist_item(self, item_id: str, *, completed: bool) -> None: ...

    def set_meal_item(self, item_id: str, command: MealItemCommand) -> None: ...

    def set_workout_set(self, set_id: str, command: WorkoutSetCommand) -> None: ...

    def set_assignment_state(
        self,
        assignment_id: str,
        *,
        state: str,
        estimated_minutes: int | None,
    ) -> None: ...

    def approve_import(self, draft_id: str, *, allow_warnings: bool) -> Mapping[str, Any]: ...

    def reject_import(self, draft_id: str) -> None: ...

    def update_settings(self, command: SettingsCommand) -> None: ...

    def sync_now(self) -> Mapping[str, Any]: ...

    def resolve_sync_conflict(
        self,
        conflict_id: str,
        resolution: str,
    ) -> Mapping[str, Any]: ...


class WebServiceUnavailable(RuntimeError):
    """Raised when the application facade has not been installed or wired."""


@contextmanager
def default_service_factory() -> Iterator[WebServices]:
    """Create one application facade and transaction per HTTP request."""

    try:
        facade_module = importlib.import_module("semester_ops.application.facade")
        facade_type = facade_module.SemesterOpsService
    except (ImportError, AttributeError) as exc:
        raise WebServiceUnavailable(
            "The Semester Ops application facade is unavailable. "
            "Run the complete installation and database migration before starting the web app."
        ) from exc

    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            service = facade_type(session)
            if not isinstance(service, WebServices):
                raise WebServiceUnavailable(
                    "SemesterOpsService does not implement the required web service contract."
                )
            yield service
            session.commit()
        except Exception:
            session.rollback()
            raise


type ServiceFactory = Callable[[], AbstractContextManager[WebServices]]
