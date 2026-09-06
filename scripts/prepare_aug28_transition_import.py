from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from semester_ops.application.common import get_or_create_settings
from semester_ops.application.imports import ImportService
from semester_ops.db.models import (
    BlockOccurrence,
    ImportDraft,
    Semester,
    WorkoutExercise,
)
from semester_ops.db.session import get_session_factory
from semester_ops.domain.enums import ChangeOperation, DraftStatus, IssueSeverity
from semester_ops.domain.import_contract import ImportPayload

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATH = ROOT / "var" / "aug28-transition-import-payload.json"
RESULT_PATH = ROOT / "var" / "aug28-transition-draft-result.json"
SEMESTER_NAME = "Fall 2026"
SEMESTER_START = date(2026, 8, 24)
SEMESTER_END = date(2026, 12, 20)
START_DATE = date(2026, 8, 25)
END_DATE = date(2026, 8, 28)
DATASET = "source_bundle.fall_weekly_plan.v1"
IDEMPOTENCY_KEY = "fall-transition-work-through-2026-08-28-v2"


def _load_occurrence(
    session: Session,
    semester_id: str,
    source_key: str,
) -> BlockOccurrence:
    occurrence = session.scalar(
        select(BlockOccurrence)
        .where(
            BlockOccurrence.semester_id == semester_id,
            BlockOccurrence.managed_dataset == DATASET,
            BlockOccurrence.source_key == source_key,
        )
        .options(
            selectinload(BlockOccurrence.checklist_items),
            selectinload(BlockOccurrence.meal_items),
            selectinload(BlockOccurrence.workout_exercises).selectinload(WorkoutExercise.sets),
            selectinload(BlockOccurrence.assignment_links),
        )
    )
    if occurrence is None:
        raise RuntimeError(f"required Fall occurrence is missing: {source_key}")
    if occurrence.cancelled_at is not None:
        raise RuntimeError(f"required Fall occurrence is already cancelled: {source_key}")
    return occurrence


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _occurrence_value(
    occurrence: BlockOccurrence,
    *,
    start_time: str,
    duration_minutes: int,
    title: str | None = None,
) -> dict[str, Any]:
    return {
        "source_key": occurrence.source_key,
        "occurrence_date": occurrence.occurrence_date.isoformat(),
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "title": title or occurrence.title,
        "category": occurrence.category.value,
        "flexibility": occurrence.flexibility.value,
        "description": occurrence.description,
        "location": occurrence.location,
        "priority": occurrence.priority,
        "preferred_duration_minutes": occurrence.preferred_duration_minutes,
        "minimum_duration_minutes": occurrence.minimum_duration_minutes,
        "may_split": occurrence.may_split,
        "requires_completion": occurrence.requires_completion,
        "calendar_projection": occurrence.calendar_projection,
        "checklist_items": [
            {
                "title": item.title,
                "required": item.required,
                "position": item.position,
            }
            for item in occurrence.checklist_items
        ],
        "meal_items": [
            {
                "food_name": item.food_name,
                "unit": item.unit,
                "planned_quantity": str(item.planned_quantity),
                "calories_per_unit": str(item.calories_per_unit),
                "protein_grams_per_unit": str(item.protein_grams_per_unit),
                "required": item.required,
                "position": item.position,
            }
            for item in occurrence.meal_items
        ],
        "workout_exercises": [
            {
                "name": exercise.name,
                "planned_sets": exercise.planned_sets,
                "rep_min": exercise.rep_min,
                "rep_max": exercise.rep_max,
                "target_weight": _decimal(exercise.target_weight),
                "weight_unit": exercise.weight_unit,
                "required": exercise.required,
                "position": exercise.position,
                "notes": exercise.notes,
                "sets": [
                    {
                        "set_number": workout_set.set_number,
                        "target_reps": workout_set.target_reps,
                    }
                    for workout_set in exercise.sets
                ],
            }
            for exercise in occurrence.workout_exercises
        ],
        "assignment_ids": [link.assignment_id for link in occurrence.assignment_links],
    }


def _new_occurrence(
    *,
    source_key: str,
    occurrence_date: str,
    start_time: str,
    duration_minutes: int,
    title: str,
    category: str,
    flexibility: str,
    description: str,
    priority: int,
    requires_completion: bool = True,
    checklist_items: list[dict[str, Any]] | None = None,
    meal_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "occurrence_date": occurrence_date,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "title": title,
        "category": category,
        "flexibility": flexibility,
        "description": description,
        "priority": priority,
        "may_split": False,
        "requires_completion": requires_completion,
        "calendar_projection": True,
        "checklist_items": checklist_items or [],
        "meal_items": meal_items or [],
        "workout_exercises": [],
        "assignment_ids": [],
    }


def _work_value(day: str) -> dict[str, Any]:
    return _new_occurrence(
        source_key=f"transition-work-{day}",
        occurrence_date=day,
        start_time="12:30:00",
        duration_minutes=300,
        title="Work",
        category="work",
        flexibility="fixed",
        description=(
            "Temporary work schedule through August 28. This occurrence replaces the "
            "normal Fall work block for this date."
        ),
        priority=100,
    )


def _mediterranean_lunch() -> dict[str, Any]:
    return _new_occurrence(
        source_key="transition-wed-lunch-2026-08-26",
        occurrence_date="2026-08-26",
        start_time="11:30:00",
        duration_minutes=45,
        title="Cook and eat Mediterranean chicken pita",
        category="meal",
        flexibility="flexible",
        description=(
            "Ingredients: 5 oz chicken breast, whole-grain pita, tomato, cucumber, red "
            "onion, spinach, feta, hummus, Greek yogurt, lemon, garlic, and dill or "
            "parsley. Season and sear the chicken, mix quick tzatziki, warm the pita, "
            "then fill it with hummus, vegetables, feta, chicken, and tzatziki."
        ),
        priority=80,
        checklist_items=[
            {
                "title": "Season and sear chicken; rest and slice",
                "required": True,
                "position": 0,
            },
            {
                "title": "Mix yogurt, cucumber, lemon, garlic, and herbs",
                "required": True,
                "position": 1,
            },
            {
                "title": (
                    "Warm pita and fill with hummus, vegetables, feta, chicken, and tzatziki"
                ),
                "required": True,
                "position": 2,
            },
        ],
        meal_items=[
            {
                "food_name": "Mediterranean chicken pita with tzatziki",
                "unit": "recipe serving",
                "planned_quantity": "1",
                "calories_per_unit": "620",
                "protein_grams_per_unit": "46",
                "required": True,
                "position": 0,
            }
        ],
    )


def _snack_value() -> dict[str, Any]:
    return _new_occurrence(
        source_key="transition-fri-snack-2026-08-28",
        occurrence_date="2026-08-28",
        start_time="17:30:00",
        duration_minutes=15,
        title="Protein snack and decompress",
        category="meal",
        flexibility="optional",
        description=(
            "Have a quick protein-forward snack, hydrate, and change for Lift C. "
            "Examples: Greek yogurt, a protein shake, or cottage cheese and fruit."
        ),
        priority=60,
        requires_completion=False,
        meal_items=[
            {
                "food_name": "Protein snack",
                "unit": "serving",
                "planned_quantity": "1",
                "calories_per_unit": "220",
                "protein_grams_per_unit": "25",
                "required": False,
                "position": 0,
            }
        ],
    )


def build_payload(session: Session, semester_id: str, base_revision: int) -> dict[str, Any]:
    updates = {
        "template:tue-lunch:2026-08-25": ("10:45:00", 15, "Eat prepacked chicken Caesar wrap"),
        "template:wed-coursework:2026-08-26": ("08:30:00", 180, None),
        "template:wed-snack:2026-08-26": ("17:30:00", 30, None),
        "template:wed-lift-b:2026-08-26": ("18:00:00", 70, None),
        "template:wed-dinner:2026-08-26": ("19:15:00", 60, None),
        "template:fri-coursework:2026-08-28": ("10:10:00", 80, None),
        "template:fri-lunch:2026-08-28": ("11:30:00", 45, None),
        "template:fri-lift-c:2026-08-28": ("17:45:00", 70, None),
        "template:fri-dinner:2026-08-28": ("19:00:00", 60, None),
        "template:fri-social:2026-08-28": ("20:00:00", 210, None),
    }
    cancellations = [
        "template:tue-remote-job:2026-08-25",
        "template:tue-conditioning:2026-08-25",
        "template:tue-mobility:2026-08-25",
        "template:wed-software-work:2026-08-26",
        "template:fri-remote-job:2026-08-28",
    ]

    operations: list[dict[str, Any]] = []
    for source_key, (start_time, duration_minutes, title) in updates.items():
        occurrence = _load_occurrence(session, semester_id, source_key)
        operations.append(
            {
                "operation": "update",
                "entity_type": "occurrence",
                "target_source_key": source_key,
                "value": _occurrence_value(
                    occurrence,
                    start_time=start_time,
                    duration_minutes=duration_minutes,
                    title=title,
                ),
            }
        )
    for source_key in cancellations:
        _load_occurrence(session, semester_id, source_key)
        operations.append(
            {
                "operation": "cancel",
                "entity_type": "occurrence",
                "target_source_key": source_key,
            }
        )
    for value in (
        _work_value("2026-08-25"),
        _mediterranean_lunch(),
        _work_value("2026-08-26"),
        _work_value("2026-08-28"),
        _snack_value(),
    ):
        operations.append(
            {
                "operation": "add",
                "entity_type": "occurrence",
                "value": value,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": "patch",
        "managed_dataset": DATASET,
        "idempotency_key": IDEMPOTENCY_KEY,
        "base_revision": base_revision,
        "scope": {
            "semester_id": semester_id,
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "source": {
            "filename": "schedule-through-2026-08-28.txt",
            "media_type": "text/plain",
            "description": (
                "One-week Fall transition preserving the temporary Tuesday, Wednesday, "
                "and Friday 12:30-5:30 work schedule through August 28."
            ),
        },
        "assumptions": [
            "Fall 2026 still begins August 24; the Pre-Semester period still ends August 23.",
            "Work is fixed Tuesday, Wednesday, and Friday from 12:30 PM to 5:30 PM Central.",
            "Classes and commutes remain fixed; meals, workouts, and coursework move around work.",
            "The Tuesday chicken Caesar wrap is prepared before class and eaten between classes.",
        ],
        "unresolved_fields": [],
        "templates": [],
        "occurrences": [],
        "operations": operations,
    }
    validated = ImportPayload.model_validate(payload).model_dump(mode="json")
    return cast(dict[str, Any], validated)


def _fall_semester(session: Session) -> Semester:
    semester = session.scalar(
        select(Semester).where(
            Semester.name == SEMESTER_NAME,
            Semester.start_date == SEMESTER_START,
            Semester.end_date == SEMESTER_END,
            Semester.is_active.is_(True),
        )
    )
    if semester is None:
        raise RuntimeError(f"{SEMESTER_NAME} does not exist")
    if semester.start_date > START_DATE or semester.end_date < END_DATE:
        raise RuntimeError("Fall 2026 does not cover the complete transition scope")
    return semester


def _draft_summary(draft: ImportDraft) -> dict[str, Any]:
    operation_counts = {
        operation: sum(change.operation is operation for change in draft.changes)
        for operation in ChangeOperation
    }
    return {
        "id": draft.id,
        "status": draft.status.value,
        "adds": operation_counts[ChangeOperation.ADD],
        "updates": operation_counts[ChangeOperation.UPDATE],
        "cancels": operation_counts[ChangeOperation.CANCEL],
        "errors": sum(issue.severity is IssueSeverity.ERROR for issue in draft.issues),
        "issues": [
            {
                "severity": issue.severity.value,
                "code": issue.code,
                "message": issue.message,
                "blocking": issue.blocking,
            }
            for issue in draft.issues
        ],
    }


def preflight_live() -> dict[str, Any]:
    factory = get_session_factory()
    with factory() as session:
        semester = _fall_semester(session)
        revision = get_or_create_settings(session).schedule_revision
        payload = build_payload(session, semester.id, revision)
        if payload != build_payload(session, semester.id, revision):
            raise RuntimeError("transition payload generation is not deterministic")
        draft = ImportService(session).create_draft(payload)
        summary = _draft_summary(draft)
        session.rollback()

    if summary["status"] != "ready" or summary["errors"]:
        raise RuntimeError(f"transition preflight failed: {summary}")
    if (summary["adds"], summary["updates"], summary["cancels"]) != (5, 10, 5):
        raise RuntimeError(f"unexpected transition change counts: {summary}")
    return summary


def result_data(result: CallToolResult) -> dict[str, Any]:
    if result.isError:
        messages = [item.text for item in result.content if isinstance(item, TextContent)]
        raise RuntimeError("; ".join(messages) or "MCP tool returned an error")
    if result.structuredContent is not None:
        if not isinstance(result.structuredContent, dict):
            raise TypeError("MCP structured content must be a JSON object")
        return result.structuredContent
    text_items = [item.text for item in result.content if isinstance(item, TextContent)]
    if len(text_items) != 1:
        raise RuntimeError("MCP tool did not return one JSON result")
    value = json.loads(text_items[0])
    if not isinstance(value, dict):
        raise TypeError("MCP tool result must be a JSON object")
    return value


def _without_base_revision(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    normalized["base_revision"] = 0
    return normalized


async def main(*, dry_run: bool = False) -> None:
    factory = get_session_factory()
    with factory() as session:
        applied = session.scalar(
            select(ImportDraft).where(
                ImportDraft.idempotency_key == IDEMPOTENCY_KEY,
                ImportDraft.status == DraftStatus.APPLIED,
            )
        )
        if applied is not None:
            summary = _draft_summary(applied)
            print(f"draft_id={summary['id']}")
            print(f"status={summary['status']}")
            print(f"adds={summary['adds']}")
            print(f"updates={summary['updates']}")
            print(f"cancels={summary['cancels']}")
            print(f"errors={summary['errors']}")
            print(f"issues={len(summary['issues'])}")
            return

    preflight = preflight_live()
    if dry_run:
        print(f"status={preflight['status']}")
        print(f"adds={preflight['adds']}")
        print(f"updates={preflight['updates']}")
        print(f"cancels={preflight['cancels']}")
        print(f"errors={preflight['errors']}")
        print(f"issues={len(preflight['issues'])}")
        return

    with factory() as session:
        semester = _fall_semester(session)
        existing = session.scalar(
            select(ImportDraft).where(ImportDraft.idempotency_key == IDEMPOTENCY_KEY)
        )
        existing_data = (
            {
                "id": existing.id,
                "status": existing.status.value,
                "base_revision": existing.base_revision,
                "payload": existing.payload_json,
            }
            if existing is not None
            else None
        )
        semester_id = semester.id

    params = StdioServerParameters(
        command=str(ROOT / ".venv" / "Scripts" / "python.exe"),
        args=["-m", "semester_ops.mcp_server"],
        cwd=ROOT,
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        context = result_data(
            await session.call_tool(
                "get_planning_context",
                {"start_date": START_DATE.isoformat(), "end_date": END_DATE.isoformat()},
            )
        )
        with factory() as database_session:
            validated = build_payload(
                database_session,
                semester_id,
                context["schedule_revision"],
            )
        PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        PAYLOAD_PATH.write_text(
            json.dumps(validated, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        if existing_data is None:
            created = result_data(
                await session.call_tool(
                    "create_import_draft",
                    {
                        "payload": validated,
                        "idempotency_key": IDEMPOTENCY_KEY,
                        "base_revision": context["schedule_revision"],
                    },
                )
            )
            draft_id = created["id"]
        else:
            if _without_base_revision(existing_data["payload"]) != _without_base_revision(
                validated
            ):
                raise RuntimeError(
                    "the existing draft has different content; bump IDEMPOTENCY_KEY before "
                    "creating a replacement"
                )
            if (
                existing_data["status"] == "ready"
                and existing_data["base_revision"] != context["schedule_revision"]
            ):
                raise RuntimeError(
                    "the existing ready draft is stale; bump IDEMPOTENCY_KEY before creating "
                    "a replacement"
                )
            draft_id = existing_data["id"]
        reviewed = result_data(await session.call_tool("get_draft", {"draft_id": draft_id}))

    RESULT_PATH.write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"draft_id={reviewed['id']}")
    print(f"status={reviewed['status']}")
    print(f"base_revision={reviewed['base_revision']}")
    print(f"changes={reviewed['add_count'] + reviewed['change_count'] + reviewed['cancel_count']}")
    print(f"adds={reviewed['add_count']}")
    print(f"updates={reviewed['change_count']}")
    print(f"cancels={reviewed['cancel_count']}")
    print(f"errors={reviewed['error_count']}")
    print(f"issues={len(reviewed['issues'])}")
    print(f"review_url={reviewed['review_url']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare the reviewable Fall transition schedule through August 28."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate against the live schedule and roll back without saving a draft.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(dry_run=arguments.dry_run))
