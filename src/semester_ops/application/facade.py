import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from semester_ops.application.common import add_audit_event, get_or_create_settings
from semester_ops.application.errors import NotFoundError, ValidationError
from semester_ops.application.imports import ImportService
from semester_ops.application.schedule import ScheduleService
from semester_ops.application.sync import (
    BlackboardAssignmentSync,
    ConnectorSynchronizer,
    GoogleCalendarProjectionSync,
    SyncService,
)
from semester_ops.application.tracking import TrackingService
from semester_ops.config import get_settings as get_runtime_settings
from semester_ops.db.models import (
    Assignment,
    AssignmentBlockLink,
    BlockOccurrence,
    CalendarEventLink,
    ChecklistItem,
    ExternalSourceState,
    ImportDraft,
    SyncConflict,
    SyncRun,
    utc_now,
)
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    Flexibility,
    SyncConflictStatus,
    SyncConnector,
    TrackingStatus,
)
from semester_ops.domain.time import operational_day_bounds, resolve_wall_time
from semester_ops.domain.tracking import effective_status
from semester_ops.integrations.blackboard import BlackboardFeedClient
from semester_ops.integrations.google_calendar import (
    GoogleCalendarConfigurationError,
    GoogleCalendarGateway,
)


class SemesterOpsService:
    """Shared adapter-facing facade; domain rules stay in focused services."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.schedule = ScheduleService(session)
        self.tracking = TrackingService(session)
        self.imports = ImportService(session)

    def get_import_schema(self) -> dict[str, Any]:
        schema_path = Path(__file__).resolve().parents[3] / "schemas" / "import-v1.json"
        return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))

    def get_planning_context(self, start_date: date | str, end_date: date | str) -> dict[str, Any]:
        start_day = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        end_day = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
        if end_day < start_day:
            raise ValueError("end_date must be on or after start_date")
        settings = get_or_create_settings(self.session)
        start_utc, _ = operational_day_bounds(
            start_day, settings.timezone, settings.operational_day_boundary
        )
        _, end_utc = operational_day_bounds(
            end_day, settings.timezone, settings.operational_day_boundary
        )
        blocks = self.schedule.list_occurrences(start_utc, end_utc)
        semester_name = None
        if settings.active_semester_id:
            from semester_ops.db.models import Semester

            active_semester = self.session.get(Semester, settings.active_semester_id)
            semester_name = active_semester.name if active_semester else None
        return {
            "semester_name": semester_name,
            "schedule_revision": settings.schedule_revision,
            "timezone": settings.timezone,
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "blocks": [self._block_dto(item) for item in blocks],
            "free_windows": self._free_windows(start_utc, end_utc, blocks),
            "assignments": self._assignment_rows(AssignmentInboxStatus.INBOX.value),
        }

    def list_assignment_inbox(self, status: str = "inbox") -> list[dict[str, Any]]:
        return self._assignment_rows(status)

    def create_import_draft(
        self,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        draft = self.imports.create_draft(
            payload,
            idempotency_key=idempotency_key,
            base_revision=base_revision,
        )
        self.session.commit()
        return self._draft_dto(draft)

    def create_planning_draft(
        self,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        return self.create_import_draft(payload, idempotency_key, base_revision)

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return self._draft_dto(self.imports.get_draft(draft_id))

    def get_today(self, day: date | str | None = None) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        if day is None:
            local_today = datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date()
        else:
            local_today = date.fromisoformat(day) if isinstance(day, str) else day
        blocks = self.schedule.get_today(local_today)
        conflicts = self.schedule.conflicts(blocks)
        conflicted_ids = {
            item_id
            for conflict in conflicts
            for item_id in (conflict.first_occurrence_id, conflict.second_occurrence_id)
        }
        block_rows = [self._block_dto(item) for item in blocks]
        for index, row in enumerate(block_rows):
            previous_end = (
                blocks[index - 1].planned_end_utc
                if index
                else operational_day_bounds(
                    local_today, settings.timezone, settings.operational_day_boundary
                )[0]
            )
            row["gap_before_minutes"] = max(
                0, int((blocks[index].planned_start_utc - previous_end).total_seconds() // 60)
            )
            row["conflict"] = row["id"] in conflicted_ids
        nutrition = self.schedule.nutrition_totals(blocks)
        trackable = [item for item in blocks if item.requires_completion]
        completed = sum(item.status is TrackingStatus.COMPLETED for item in trackable)
        total_sets = sum(
            len(exercise.sets) for block in blocks for exercise in block.workout_exercises
        )
        completed_sets = sum(
            workout_set.completed_at is not None
            for block in blocks
            for exercise in block.workout_exercises
            for workout_set in exercise.sets
        )
        return {
            "selected_date": local_today.isoformat(),
            "date_label": f"{local_today.strftime('%A, %B')} {local_today.day}",
            "previous_date": (local_today - timedelta(days=1)).isoformat(),
            "next_date": (local_today + timedelta(days=1)).isoformat(),
            "timezone": settings.timezone,
            "schedule_revision": settings.schedule_revision,
            "blocks": block_rows,
            "summary": {
                "completed_blocks": completed,
                "trackable_blocks": len(trackable),
                "completion_percent": round(completed / len(trackable) * 100) if trackable else 0,
                "calories_consumed": str(nutrition.consumed_calories),
                "calorie_target": settings.calorie_target or 0,
                "calorie_percent": (
                    min(
                        100,
                        round(float(nutrition.consumed_calories) / settings.calorie_target * 100),
                    )
                    if settings.calorie_target
                    else 0
                ),
                "protein_consumed": str(nutrition.consumed_protein_grams),
                "protein_target": settings.protein_target_grams or 0,
                "workout_sets_completed": completed_sets,
                "workout_sets_total": total_sets,
                "workout_percent": round(completed_sets / total_sets * 100) if total_sets else 0,
                "workout_actual_minutes": sum(
                    int((item.actual_end_utc - item.actual_start_utc).total_seconds() // 60)
                    for item in blocks
                    if item.actual_start_utc
                    and item.actual_end_utc
                    and item.category is BlockCategory.WORKOUT
                ),
            },
            "sync": self._sync_card(),
            "current_block": next((row for row in block_rows if row["is_current"]), None),
            "now_label": datetime.now(UTC)
            .astimezone(ZoneInfo(settings.timezone))
            .strftime("%I:%M %p"),
            "conflicts": [
                {
                    "first_occurrence_id": item.first_occurrence_id,
                    "second_occurrence_id": item.second_occurrence_id,
                    "overlap_start_utc": item.overlap_start_utc.isoformat(),
                    "overlap_end_utc": item.overlap_end_utc.isoformat(),
                }
                for item in conflicts
            ],
        }

    def get_week(self, start: date | str | None = None) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        if start is None:
            today = datetime.now(UTC).astimezone(zone).date()
            start_date = today - timedelta(days=today.weekday())
        else:
            start_date = date.fromisoformat(start) if isinstance(start, str) else start
        blocks = self.schedule.get_week(start_date)
        conflicts = self.schedule.conflicts(blocks)
        conflicted_ids = {
            item_id
            for conflict in conflicts
            for item_id in (conflict.first_occurrence_id, conflict.second_occurrence_id)
        }
        days = []
        today = datetime.now(UTC).astimezone(zone).date()
        for offset in range(7):
            current = start_date + timedelta(days=offset)
            rows = [
                self._block_dto(item)
                for item in blocks
                if self._operational_date(
                    item.planned_start_utc,
                    zone=zone,
                    boundary=settings.operational_day_boundary,
                )
                == current
            ]
            for row in rows:
                row["conflict"] = row["id"] in conflicted_ids
            days.append(
                {
                    "date": current.isoformat(),
                    "weekday_short": current.strftime("%a").upper(),
                    "day_number": current.day,
                    "is_today": current == today,
                    "blocks": rows,
                }
            )
        planned_minutes = sum(
            int((item.planned_end_utc - item.planned_start_utc).total_seconds() // 60)
            for item in blocks
        )
        fixed_minutes = sum(
            int((item.planned_end_utc - item.planned_start_utc).total_seconds() // 60)
            for item in blocks
            if item.flexibility is Flexibility.FIXED
        )
        end_date = start_date + timedelta(days=6)
        deadlines = [
            item
            for item in self._assignment_rows()
            if item["due_date"] and start_date <= date.fromisoformat(item["due_date"]) <= end_date
        ]
        return {
            "week_label": (
                f"{start_date.strftime('%B')} {start_date.day} - "
                f"{end_date.strftime('%B')} {end_date.day}"
            ),
            "anchor_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "previous_anchor": (start_date - timedelta(days=7)).isoformat(),
            "next_anchor": (start_date + timedelta(days=7)).isoformat(),
            "days": days,
            "summary": {
                "planned_hours": round(planned_minutes / 60, 1),
                "fixed_hours": round(fixed_minutes / 60, 1),
                "open_hours": round(max(0, 7 * 24 * 60 - planned_minutes) / 60, 1),
                "block_count": len(blocks),
                "conflict_count": len(conflicts),
            },
            "deadlines": deadlines,
        }

    def _assignment_rows(self, state: str | None = None) -> list[dict[str, Any]]:
        statement = (
            select(Assignment)
            .options(
                selectinload(Assignment.course),
                selectinload(Assignment.block_links).selectinload(AssignmentBlockLink.occurrence),
            )
            .order_by(Assignment.due_at_utc, Assignment.due_date, Assignment.title)
        )
        if state:
            statement = statement.where(Assignment.inbox_status == AssignmentInboxStatus(state))
        zone = ZoneInfo(get_or_create_settings(self.session).timezone)
        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        for item in self.session.scalars(statement):
            due_local = item.due_at_utc.astimezone(zone) if item.due_at_utc else None
            due_date = item.due_date or (due_local.date() if due_local else None)
            deadline = item.due_at_utc
            if deadline is None and due_date is not None:
                deadline = resolve_wall_time(due_date, time(23, 59), str(zone)).astimezone(UTC)
            urgency = "normal"
            if deadline is not None:
                if deadline < now:
                    urgency = "overdue"
                elif deadline <= now + timedelta(hours=72):
                    urgency = "soon"
            linked_blocks = [
                {
                    "id": link.occurrence.id,
                    "date_label": link.occurrence.occurrence_date.strftime("%b %d"),
                    "time_label": link.occurrence.planned_start_utc.astimezone(zone).strftime(
                        "%I:%M %p"
                    ),
                    "needs_replanning": link.needs_replanning,
                }
                for link in item.block_links
            ]
            rows.append(
                {
                    "id": item.id,
                    "course_id": item.course_id,
                    "course_code": item.course.code if item.course else None,
                    "course_name": item.course.name if item.course else None,
                    "title": item.title,
                    "due_precision": item.due_precision.value,
                    "due_date": due_date.isoformat() if due_date else None,
                    "due_at_utc": item.due_at_utc.isoformat() if item.due_at_utc else None,
                    "due_day": due_date.strftime("%b %d") if due_date else "TBD",
                    "due_time": due_local.strftime("%I:%M %p") if due_local else "",
                    "due_label": (
                        due_local.strftime("%b %d at %I:%M %p")
                        if due_local
                        else due_date.strftime("%b %d")
                        if due_date
                        else "TBD"
                    ),
                    "urgency": urgency,
                    "url": item.url,
                    "source_url": item.url,
                    "status": item.inbox_status.value,
                    "state": item.inbox_status.value,
                    "source_state": item.source_state.value,
                    "estimated_effort_minutes": item.estimated_effort_minutes,
                    "estimated_minutes": item.estimated_effort_minutes,
                    "linked_block_count": len(linked_blocks),
                    "linked_blocks": linked_blocks,
                    "source_changed": item.source_changed,
                }
            )
        return rows

    def list_assignments(self, state: str | None = None) -> dict[str, Any]:
        rows = self._assignment_rows(state)
        all_rows = self._assignment_rows()
        settings = get_or_create_settings(self.session)
        due_soon = sum(item["urgency"] in {"soon", "overdue"} for item in all_rows)
        blackboard_state = self.session.scalar(
            select(ExternalSourceState)
            .where(ExternalSourceState.connector == SyncConnector.BLACKBOARD)
            .order_by(ExternalSourceState.last_success_at.desc())
        )
        return {
            "assignments": rows,
            "active_state": state,
            "counts": {
                status.value: sum(item["status"] == status.value for item in all_rows)
                for status in AssignmentInboxStatus
            }
            | {"due_soon": due_soon},
            "source": {
                "status": "connected" if settings.blackboard_ics_url else "unconfigured",
                "label": "Connected" if settings.blackboard_ics_url else "Not configured",
                "last_refreshed_at": (
                    blackboard_state.last_success_at.isoformat()
                    if blackboard_state and blackboard_state.last_success_at
                    else None
                ),
            },
        }

    def list_imports(self) -> dict[str, Any]:
        drafts = self.session.scalars(
            select(ImportDraft)
            .options(selectinload(ImportDraft.changes), selectinload(ImportDraft.issues))
            .order_by(ImportDraft.created_at.desc())
        )
        rows = [self._draft_dto(item) for item in drafts]
        return {
            "drafts": rows,
            "counts": {
                "pending": sum(item["status"] in {"ready", "blocked"} for item in rows),
                "applied": sum(item["status"] == "applied" for item in rows),
                "rejected": sum(item["status"] == "rejected" for item in rows),
            },
        }

    def get_import(self, draft_id: str) -> dict[str, Any]:
        draft_model = self.imports.get_draft(draft_id)
        draft = self._draft_dto(draft_model)
        current = get_or_create_settings(self.session).schedule_revision
        draft["current_revision"] = current
        draft["is_stale"] = draft["base_revision"] != current
        return {
            "draft": draft,
            "changes": [self._import_change_view(item) for item in draft["changes"]],
            "issues": draft["issues"],
            "error_count": sum(item["blocking"] for item in draft["issues"]),
            "warning_count": sum(item["severity"] == "warning" for item in draft["issues"]),
            "payload_json": json.dumps(draft_model.payload_json, indent=2, sort_keys=True),
        }

    def set_block_status(self, block_id: str, action: str) -> dict[str, Any]:
        action_to_status = {
            "start": TrackingStatus.IN_PROGRESS,
            "complete": TrackingStatus.COMPLETED,
            "skip": TrackingStatus.SKIPPED,
            "reopen": TrackingStatus.PLANNED,
        }
        status = action_to_status.get(action)
        if status is None:
            status = TrackingStatus(action)
        block = self.tracking.set_status(block_id, status)
        self.session.commit()
        return {"message": f"{block.title} is now {block.status.value}."}

    def get_settings_view(self) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        runtime = get_runtime_settings()
        summary = self.sync_summary()
        source_states = list(self.session.scalars(select(ExternalSourceState)))
        open_conflicts = list(
            self.session.scalars(
                select(SyncConflict)
                .where(SyncConflict.status == SyncConflictStatus.OPEN)
                .order_by(SyncConflict.created_at.desc())
                .limit(20)
            )
        )
        zone = ZoneInfo(settings.timezone)
        conflict_rows: list[dict[str, Any]] = []
        for conflict in open_conflicts:
            occurrence = self.session.get(BlockOccurrence, conflict.occurrence_id)
            if occurrence is None:
                continue
            conflict_rows.append(
                {
                    "id": conflict.id,
                    "occurrence_id": occurrence.id,
                    "title": occurrence.title,
                    "planner_start_local": occurrence.planned_start_utc.astimezone(zone),
                    "planner_end_local": occurrence.planned_end_utc.astimezone(zone),
                    "remote_start_local": conflict.remote_start_utc.astimezone(zone),
                    "remote_end_local": conflict.remote_end_utc.astimezone(zone),
                    "created_at": conflict.created_at,
                }
            )

        def last_success(connector: SyncConnector) -> str:
            values = [
                item.last_success_at
                for item in source_states
                if item.connector is connector and item.last_success_at is not None
            ]
            return max(values).isoformat() if values else "Never"

        google_ready = bool(
            settings.google_calendar_id
            and runtime.google_client_secret_file
            and runtime.google_token_file.is_file()
        )
        return {
            "settings": {
                "timezone": settings.timezone,
                "operational_day_start": settings.operational_day_boundary.strftime("%H:%M"),
                "missed_grace_minutes": settings.missed_grace_minutes,
                "calorie_target": settings.calorie_target,
                "protein_target_grams": settings.protein_target_grams,
                "weight_unit": settings.weight_unit,
                "blackboard_configured": bool(settings.blackboard_ics_url),
            },
            "connectors": [
                {
                    "kind": "GOOGLE",
                    "name": "Semester Ops - Dev",
                    "status": (
                        "connected"
                        if google_ready
                        else "attention"
                        if settings.google_calendar_id
                        else "unconfigured"
                    ),
                    "status_label": (
                        "Ready"
                        if google_ready
                        else "OAuth needed"
                        if settings.google_calendar_id
                        else "Not configured"
                    ),
                    "description": (
                        "Only the app-created development calendar can receive owned events."
                    ),
                    "details": [
                        {
                            "label": "Calendar ID",
                            "value": "Stored locally" if settings.google_calendar_id else "Missing",
                        },
                        {
                            "label": "Last success",
                            "value": last_success(SyncConnector.GOOGLE),
                        },
                    ],
                },
                {
                    "kind": "BLACKBOARD",
                    "name": "Assignment feed",
                    "status": "connected" if settings.blackboard_ics_url else "unconfigured",
                    "status_label": (
                        "Configured" if settings.blackboard_ics_url else "Not configured"
                    ),
                    "description": "Private ICS feed; Semester Ops never writes to Blackboard.",
                    "details": [
                        {
                            "label": "Feed URL",
                            "value": "Stored locally" if settings.blackboard_ics_url else "Missing",
                        },
                        {
                            "label": "Last success",
                            "value": last_success(SyncConnector.BLACKBOARD),
                        },
                    ],
                },
            ],
            "sync_runs": [
                {
                    **run,
                    "summary": f"{run['connector'].title()} sync {run['status']}",
                    "duration_ms": 0,
                }
                for run in summary["runs"]
            ],
            "sync_conflicts": conflict_rows,
        }

    def get_block(self, block_id: str) -> dict[str, Any]:
        block = self.session.get(BlockOccurrence, block_id)
        if block is None:
            raise NotFoundError(f"block occurrence {block_id} was not found")
        row = self._block_dto(block)
        return {
            "block": row,
            "timezone": get_or_create_settings(self.session).timezone,
            "categories": [
                {"value": category.value, "label": category.value.replace("_", " ").title()}
                for category in BlockCategory
            ],
        }

    def update_block(self, block_id: str, command: Any) -> None:
        block = self.session.get(BlockOccurrence, block_id)
        if block is None:
            raise NotFoundError(f"block occurrence {block_id} was not found")
        start = self._local_command_time(command.planned_start_local)
        end = self._local_command_time(command.planned_end_local)
        self.schedule.move_occurrence(block_id, start, end)
        block.title = command.title
        block.category = BlockCategory(command.category)
        block.flexibility = Flexibility(command.flexibility)
        block.notes = command.notes
        block.calendar_projection = command.project_to_calendar
        self.session.commit()

    def move_block(self, block_id: str, minutes: int) -> None:
        if not minutes or minutes % 15:
            raise ValueError("blocks move in non-zero 15-minute increments")
        block = self.session.get(BlockOccurrence, block_id)
        if block is None:
            raise NotFoundError(f"block occurrence {block_id} was not found")
        self.schedule.move_occurrence(
            block_id,
            block.planned_start_utc + timedelta(minutes=minutes),
            block.planned_end_utc + timedelta(minutes=minutes),
        )
        self.session.commit()

    def set_checklist_item(self, item_id: str, *, completed: bool) -> None:
        self.tracking.set_checklist_item_completed(item_id, completed)
        self.session.commit()

    def set_meal_item(self, item_id: str, command: Any) -> None:
        self.tracking.set_meal_item_completed(
            item_id,
            command.completed,
            consumed_quantity=command.consumed_quantity,
        )
        self.session.commit()

    def set_workout_set(self, set_id: str, command: Any) -> None:
        self.tracking.complete_workout_set(
            set_id,
            command.completed,
            actual_reps=command.actual_reps,
            actual_weight=command.actual_weight,
        )
        self.session.commit()

    def set_assignment_state(
        self,
        assignment_id: str,
        *,
        state: str,
        estimated_minutes: int | None,
    ) -> None:
        assignment = self.session.get(Assignment, assignment_id)
        if assignment is None:
            raise NotFoundError(f"assignment {assignment_id} was not found")
        target = AssignmentInboxStatus(state)
        assignment.inbox_status = target
        assignment.estimated_effort_minutes = estimated_minutes
        if target in {
            AssignmentInboxStatus.PLANNED,
            AssignmentInboxStatus.COMPLETED,
            AssignmentInboxStatus.IGNORED,
        }:
            assignment.source_changed = False
            for link in assignment.block_links:
                link.needs_replanning = False
        self.session.commit()

    def approve_import(self, draft_id: str, *, allow_warnings: bool) -> dict[str, Any]:
        result = self.apply_import(draft_id, allow_warnings)
        return {"message": f"Applied {len(result['changes'])} reviewed changes."}

    def reject_import(self, draft_id: str) -> None:
        self.imports.reject_draft(draft_id)
        self.session.commit()

    def update_settings(self, command: Any) -> None:
        if command.timezone != "America/Chicago":
            raise ValueError("v1 supports America/Chicago only")
        boundary = time.fromisoformat(command.operational_day_start)
        settings = get_or_create_settings(self.session)
        settings.timezone = command.timezone
        settings.operational_day_boundary = boundary
        settings.missed_grace_minutes = command.missed_grace_minutes
        settings.calorie_target = command.calorie_target
        settings.protein_target_grams = command.protein_target_grams
        settings.weight_unit = command.weight_unit
        if command.clear_blackboard_ics:
            settings.blackboard_ics_url = None
        elif command.blackboard_ics_url:
            settings.blackboard_ics_url = command.blackboard_ics_url
        settings.updated_at = utc_now()
        self.session.commit()

    def sync_now(self) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        if not settings.google_calendar_id and not settings.blackboard_ics_url:
            return {
                "tone": "warning",
                "message": "Configure Google Calendar or Blackboard before synchronizing.",
            }
        runtime = get_runtime_settings()
        synchronizers: list[ConnectorSynchronizer] = []
        if settings.blackboard_ics_url:
            synchronizers.append(BlackboardAssignmentSync(BlackboardFeedClient()))
        if settings.google_calendar_id:

            def google_gateway() -> GoogleCalendarGateway:
                if runtime.google_client_secret_file is None:
                    raise GoogleCalendarConfigurationError(
                        "Run the explicit Google setup command before synchronizing"
                    )
                if not runtime.google_token_file.is_file():
                    raise GoogleCalendarConfigurationError(
                        "Run the explicit Google setup command before synchronizing"
                    )
                return GoogleCalendarGateway.from_oauth_files(
                    client_secret_file=runtime.google_client_secret_file,
                    token_file=runtime.google_token_file,
                )

            synchronizers.append(GoogleCalendarProjectionSync(google_gateway))

        self.session.commit()
        factory = sessionmaker(
            bind=self.session.get_bind(),
            expire_on_commit=False,
            class_=Session,
        )
        batch = SyncService(factory, synchronizers).sync_now()
        succeeded = sum(run.status.value == "succeeded" for run in batch.runs)
        needs_attention = len(batch.runs) - succeeded
        if batch.succeeded:
            message = f"Synchronization complete: {succeeded} connector(s) succeeded."
            tone = "success"
        else:
            message = (
                "Synchronization finished with attention: "
                f"{succeeded} succeeded, {needs_attention} need review."
            )
            tone = "warning"
        return {"tone": tone, "message": message, **batch.as_dict()}

    def resolve_sync_conflict(self, conflict_id: str, resolution: str) -> dict[str, str]:
        try:
            resolved_status = SyncConflictStatus(resolution)
        except ValueError as exc:
            raise ValidationError("choose Keep planner or Use Google time") from exc
        if resolved_status is SyncConflictStatus.OPEN:
            raise ValidationError("an open conflict requires a resolution")

        conflict = self.session.get(SyncConflict, conflict_id)
        if conflict is None:
            raise NotFoundError(f"sync conflict {conflict_id} was not found")
        if conflict.status is not SyncConflictStatus.OPEN:
            if conflict.status is resolved_status:
                return {"message": "That calendar conflict was already resolved."}
            raise ValidationError("that calendar conflict has already been resolved")

        occurrence = self.session.get(BlockOccurrence, conflict.occurrence_id)
        if occurrence is None:
            raise NotFoundError(f"block occurrence {conflict.occurrence_id} was not found")
        if resolved_status is SyncConflictStatus.USE_REMOTE:
            self.schedule.move_occurrence(
                occurrence.id,
                conflict.remote_start_utc,
                conflict.remote_end_utc,
                actor="google-conflict-resolution",
            )
            occurrence.override_reason = "Accepted Google Calendar time"
        elif occurrence.calendar_link is not None:
            # Treat the observed remote range as the new base so the next sync sees
            # only the chosen planner range as changed and pushes it to Google.
            occurrence.calendar_link.last_synced_start_utc = conflict.remote_start_utc
            occurrence.calendar_link.last_synced_end_utc = conflict.remote_end_utc

        conflict.status = resolved_status
        conflict.resolved_at = utc_now()
        add_audit_event(
            self.session,
            event_type="calendar.conflict_resolved",
            entity_type="sync_conflict",
            entity_id=conflict.id,
            data={"resolution": resolved_status.value, "occurrence_id": occurrence.id},
        )
        self.session.commit()
        choice = (
            "Google time" if resolved_status is SyncConflictStatus.USE_REMOTE else "planner time"
        )
        return {"message": f"Conflict resolved with {choice}. Sync again to reconcile Google."}

    def toggle_checklist(self, item_id: str, completed: bool | None = None) -> dict[str, Any]:
        item = self.session.get(ChecklistItem, item_id)
        if item is None:
            raise NotFoundError(f"checklist item {item_id} was not found")
        resolved = item.completed_at is None if completed is None else completed
        item = self.tracking.set_checklist_item_completed(item_id, resolved)
        self.session.commit()
        return {
            "id": item.id,
            "completed": item.completed_at is not None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        }

    def apply_import(self, draft_id: str, allow_warnings: bool = False) -> dict[str, Any]:
        draft = self.imports.apply_draft(draft_id, allow_warnings=allow_warnings)
        self.session.commit()
        return self._draft_dto(draft)

    def sync_summary(self) -> dict[str, Any]:
        latest = self.session.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(20))
        open_conflicts = self.session.scalar(
            select(func.count(SyncConflict.id)).where(
                SyncConflict.status == SyncConflictStatus.OPEN
            )
        )
        return {
            "runs": [
                {
                    "id": run.id,
                    "connector": run.connector.value,
                    "status": run.status.value,
                    "started_at": run.started_at.isoformat(),
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "created": run.created_count,
                    "updated": run.updated_count,
                    "deleted": run.deleted_count,
                    "conflicts": run.conflict_count,
                    "errors": run.error_count,
                }
                for run in latest
            ],
            "open_conflicts": open_conflicts or 0,
        }

    def _block_dto(self, block: BlockOccurrence) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        start_local = block.planned_start_utc.astimezone(zone)
        end_local = block.planned_end_utc.astimezone(zone)
        now = datetime.now(UTC)
        status = effective_status(
            block.status,
            planned_end_utc=block.planned_end_utc,
            now_utc=now,
            requires_completion=block.requires_completion,
            grace_minutes=settings.missed_grace_minutes,
        )
        planned_calories, planned_protein = block.planned_nutrition()
        consumed_calories, consumed_protein = block.consumed_nutrition()
        workout_exercises: list[dict[str, Any]] = [
            {
                "id": exercise.id,
                "name": exercise.name,
                "planned_sets": exercise.planned_sets,
                "completed_sets": sum(item.completed_at is not None for item in exercise.sets),
                "rep_target": (
                    f"{exercise.rep_min}-{exercise.rep_max} reps"
                    if exercise.rep_min is not None and exercise.rep_max is not None
                    else f"{exercise.rep_min or exercise.rep_max} reps"
                    if exercise.rep_min is not None or exercise.rep_max is not None
                    else ""
                ),
                "sets": [
                    {
                        "id": workout_set.id,
                        "completed": workout_set.completed_at is not None,
                        "actual_reps": workout_set.actual_reps,
                        "actual_weight": (
                            str(workout_set.actual_weight)
                            if workout_set.actual_weight is not None
                            else None
                        ),
                    }
                    for workout_set in exercise.sets
                ],
            }
            for exercise in block.workout_exercises
        ]
        meal_items = [
            {
                "id": item.id,
                "name": item.food_name,
                "unit": item.unit,
                "planned_quantity": str(item.planned_quantity),
                "consumed_quantity": (
                    str(item.consumed_quantity) if item.consumed_quantity is not None else None
                ),
                "calories": str(item.calories_per_unit * item.planned_quantity),
                "protein_grams": str(item.protein_grams_per_unit * item.planned_quantity),
                "completed": item.completed_at is not None,
            }
            for item in block.meal_items
        ]
        return {
            "id": block.id,
            "title": block.title,
            "category": block.category.value,
            "flexibility": block.flexibility.value,
            "planned_start_utc": block.planned_start_utc.isoformat(),
            "planned_end_utc": block.planned_end_utc.isoformat(),
            "start_local": start_local,
            "end_local": end_local,
            "duration_minutes": int(
                (block.planned_end_utc - block.planned_start_utc).total_seconds() // 60
            ),
            "actual_start_utc": (
                block.actual_start_utc.isoformat() if block.actual_start_utc else None
            ),
            "actual_end_utc": block.actual_end_utc.isoformat() if block.actual_end_utc else None,
            "status": status.value,
            "persisted_status": block.status.value,
            "notes": block.notes,
            "location": block.location,
            "status_label": status.value.replace("_", " ").title(),
            "category_label": block.category.value.replace("_", " ").title(),
            "is_current": block.planned_start_utc <= now < block.planned_end_utc,
            "remaining_minutes": max(0, int((block.planned_end_utc - now).total_seconds() // 60)),
            "conflict": False,
            "unsynced": block.calendar_projection
            and block.cancelled_at is None
            and (
                block.calendar_link is None
                or block.calendar_link.last_synced_local_revision < block.revision
            ),
            "calendar_event_id": block.calendar_link.event_id if block.calendar_link else None,
            "project_to_calendar": block.calendar_projection,
            "actual_start_local": (
                block.actual_start_utc.astimezone(zone) if block.actual_start_utc else None
            ),
            "actual_end_local": (
                block.actual_end_utc.astimezone(zone) if block.actual_end_utc else None
            ),
            "requires_completion": block.requires_completion,
            "calendar_projection": block.calendar_projection,
            "revision": block.revision,
            "checklist_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "label": item.title,
                    "required": item.required,
                    "completed": item.completed_at is not None,
                }
                for item in block.checklist_items
            ],
            "nutrition": {
                "planned_calories": str(planned_calories),
                "planned_protein_grams": str(planned_protein),
                "consumed_calories": str(consumed_calories),
                "consumed_protein_grams": str(consumed_protein),
            },
            "meal_items": meal_items,
            "meal_summary": {
                "planned_calories": str(planned_calories),
                "consumed_calories": str(consumed_calories),
            },
            "workout_exercises": workout_exercises,
            "workout_summary": {
                "completed_sets": sum(
                    workout_set.completed_at is not None
                    for exercise in block.workout_exercises
                    for workout_set in exercise.sets
                ),
                "total_sets": sum(len(exercise.sets) for exercise in block.workout_exercises),
            },
        }

    @staticmethod
    def _draft_dto(draft: ImportDraft) -> dict[str, Any]:
        payload = draft.payload_json
        semester = payload.get("semester") or {}
        source = payload.get("source") or {}
        title = semester.get("name") or source.get("filename") or "Review proposed changes"
        add_count = sum(item.operation.value == "add" for item in draft.changes)
        cancel_count = sum(item.operation.value in {"cancel", "delete"} for item in draft.changes)
        change_count = len(draft.changes) - add_count - cancel_count
        error_count = sum(item.blocking for item in draft.issues)
        return {
            "id": draft.id,
            "schema_version": draft.schema_version,
            "status": draft.status.value,
            "mode": draft.mode.value,
            "managed_dataset": draft.managed_dataset,
            "title": title,
            "base_revision": draft.base_revision,
            "idempotency_key": draft.idempotency_key,
            "payload_hash": draft.payload_hash,
            "source_filename": draft.source_filename,
            "source_media_type": draft.source_media_type,
            "source_hash": draft.source_sha256,
            "assumptions": draft.assumptions,
            "start_date": draft.scope_start_date.isoformat(),
            "end_date": draft.scope_end_date.isoformat(),
            "scope_label": (
                f"{draft.scope_start_date.strftime('%b')} {draft.scope_start_date.day} - "
                f"{draft.scope_end_date.strftime('%b')} {draft.scope_end_date.day}"
            ),
            "scope": {
                "start_date": draft.scope_start_date.isoformat(),
                "end_date": draft.scope_end_date.isoformat(),
            },
            "created_at": draft.created_at.isoformat(),
            "applied_at": draft.applied_at.isoformat() if draft.applied_at else None,
            "add_count": add_count,
            "change_count": change_count,
            "cancel_count": cancel_count,
            "error_count": error_count,
            "changes": [
                {
                    "id": item.id,
                    "operation": item.operation.value,
                    "entity_type": item.entity_type.value,
                    "target_id": item.target_id,
                    "before": item.before_json,
                    "after": item.after_json,
                }
                for item in draft.changes
            ],
            "issues": [
                {
                    "severity": item.severity.value,
                    "code": item.code,
                    "message": item.message,
                    "path": item.path,
                    "blocking": item.blocking,
                }
                for item in draft.issues
            ],
            "review_url": f"/imports/{draft.id}",
        }

    def _import_change_view(self, change: dict[str, Any]) -> dict[str, Any]:
        value = change.get("after") or change.get("before") or {}
        if not isinstance(value, dict):
            value = {}
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        start_local: datetime | str | None = value.get("planned_start_utc")
        end_local: datetime | str | None = value.get("planned_end_utc")
        if isinstance(start_local, str):
            start_local = datetime.fromisoformat(start_local).astimezone(zone)
        if isinstance(end_local, str):
            end_local = datetime.fromisoformat(end_local).astimezone(zone)
        occurrence_date = value.get("occurrence_date") or value.get("effective_start_date")
        entity_type = str(change.get("entity_type", "record"))
        title = value.get("title") or value.get("name") or entity_type.replace("_", " ").title()
        return {
            **change,
            "title": title,
            "category": value.get("category", entity_type),
            "flexibility": value.get("flexibility", "fixed"),
            "date_label": occurrence_date or "",
            "start_local": start_local or value.get("start_time"),
            "end_local": end_local,
            "before": self._change_summary(change.get("before")),
            "after": self._change_summary(change.get("after")),
        }

    @staticmethod
    def _change_summary(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        title = value.get("title") or value.get("name")
        start = value.get("start_time") or value.get("planned_start_utc")
        parts = [str(item) for item in (title, start) if item]
        return " / ".join(parts) if parts else "Record details changed"

    @staticmethod
    def _free_windows(
        start_utc: datetime,
        end_utc: datetime,
        blocks: list[BlockOccurrence],
    ) -> list[dict[str, str]]:
        cursor = start_utc
        windows: list[dict[str, str]] = []
        for block in sorted(blocks, key=lambda item: item.planned_start_utc):
            if block.planned_start_utc > cursor:
                windows.append(
                    {
                        "start_utc": cursor.isoformat(),
                        "end_utc": block.planned_start_utc.isoformat(),
                    }
                )
            cursor = max(cursor, block.planned_end_utc)
        if cursor < end_utc:
            windows.append({"start_utc": cursor.isoformat(), "end_utc": end_utc.isoformat()})
        return windows

    @staticmethod
    def _local_command_time(value: datetime) -> datetime:
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(UTC)
        return resolve_wall_time(value.date(), value.time(), "America/Chicago").astimezone(UTC)

    @staticmethod
    def _operational_date(value: datetime, *, zone: ZoneInfo, boundary: time) -> date:
        local_value = value.astimezone(zone)
        if local_value.time() < boundary:
            return local_value.date() - timedelta(days=1)
        return local_value.date()

    def _sync_card(self) -> dict[str, Any]:
        last_success = self.session.scalar(
            select(SyncRun)
            .where(SyncRun.status.in_(["succeeded", "partial"]))
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )
        dirty = self.session.scalar(
            select(func.count(BlockOccurrence.id))
            .outerjoin(
                CalendarEventLink,
                CalendarEventLink.occurrence_id == BlockOccurrence.id,
            )
            .where(
                BlockOccurrence.cancelled_at.is_(None),
                BlockOccurrence.calendar_projection.is_(True),
                or_(
                    CalendarEventLink.id.is_(None),
                    CalendarEventLink.last_synced_local_revision < BlockOccurrence.revision,
                ),
            )
        )
        return {
            "dirty_count": dirty or 0,
            "last_success_at": (
                last_success.finished_at if last_success and last_success.finished_at else None
            ),
        }
