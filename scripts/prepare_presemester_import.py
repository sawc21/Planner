from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from semester_ops.application.imports import ImportService
from semester_ops.application.schedule import ScheduleService
from semester_ops.db.base import Base
from semester_ops.db.models import ImportDraft, Semester
from semester_ops.db.session import get_session_factory
from semester_ops.domain.import_contract import ImportPayload

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PAYLOAD_PATH = ROOT / "var" / "fall-2026-resolved-import-payload.json"
PAYLOAD_PATH = ROOT / "var" / "presemester-2026-import-payload.json"
RESULT_PATH = ROOT / "var" / "presemester-2026-draft-result.json"
START_DATE = "2026-07-29"
END_DATE = "2026-08-23"
PERIOD_NAME = "Pre-Semester 2026"
DATASET = "source_bundle.presemester_2026.v1"
IDEMPOTENCY_KEY = "presemester-2026-07-29-through-08-23-v1"
START_DAY = date.fromisoformat(START_DATE)
END_DAY = date.fromisoformat(END_DATE)


def _templates_by_key(source_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_templates = source_payload.get("templates")
    if not isinstance(source_templates, list):
        raise ValueError("source payload templates must be a list")

    indexed: dict[str, dict[str, Any]] = {}
    for template in source_templates:
        if not isinstance(template, dict) or not isinstance(template.get("source_key"), str):
            raise ValueError("every source template must have a string source_key")
        source_key = template["source_key"]
        if source_key in indexed:
            raise ValueError(f"duplicate source template key: {source_key}")
        indexed[source_key] = template
    return indexed


def _ensure_unique_source_keys(templates: list[dict[str, Any]]) -> None:
    source_keys = [template.get("source_key") for template in templates]
    duplicates = sorted(
        str(source_key) for source_key in set(source_keys) if source_keys.count(source_key) > 1
    )
    if duplicates:
        raise ValueError(f"duplicate generated template source keys: {', '.join(duplicates)}")


def _clock(value: str) -> str:
    return value if value.count(":") == 2 else f"{value}:00"


def _base_template(
    *,
    source_key: str,
    title: str,
    category: str,
    weekdays: list[int],
    start_time: str,
    duration_minutes: int,
    flexibility: str = "flexible",
    priority: int = 60,
    description: str | None = None,
    requires_completion: bool = True,
    may_split: bool = False,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "source_key": f"prep-{source_key}",
        "title": title,
        "category": category,
        "flexibility": flexibility,
        "priority": priority,
        "requires_completion": requires_completion,
        "calendar_projection": True,
        "may_split": may_split,
        "weekdays": weekdays,
        "start_time": _clock(start_time),
        "duration_minutes": duration_minutes,
        "effective_start_date": START_DATE,
        "effective_end_date": END_DATE,
        "excluded_dates": [],
    }
    if description:
        value["description"] = description
    return value


def _clone_template(
    templates_by_key: dict[str, dict[str, Any]],
    source_template: str,
    *,
    source_key: str,
    weekdays: list[int],
    start_time: str,
    duration_minutes: int,
    title: str | None = None,
    description: str | None = None,
    meal_from: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(templates_by_key[source_template])
    value.update(
        {
            "source_key": f"prep-{source_key}",
            "weekdays": weekdays,
            "start_time": _clock(start_time),
            "duration_minutes": duration_minutes,
            "effective_start_date": START_DATE,
            "effective_end_date": END_DATE,
            "excluded_dates": [],
        }
    )
    if title is not None:
        value["title"] = title
    if description is not None:
        value["description"] = description
    if meal_from is not None:
        value["meal_items"] = deepcopy(templates_by_key[meal_from].get("meal_items", []))
    if value.get("workout_exercises"):
        recovery = (
            "Recovery: cool down for 5-10 minutes, hydrate, eat a protein-containing meal, "
            "and protect the midnight-to-8:00 sleep window. Reduce accessory work if soreness "
            "or performance declines across multiple sessions."
        )
        value["description"] = f"{value.get('description', '').strip()} {recovery}".strip()
    return value


def build_templates(source_payload: dict[str, Any]) -> list[dict[str, Any]]:
    source_templates = _templates_by_key(source_payload)
    templates: list[dict[str, Any]] = []

    templates.append(
        _clone_template(
            source_templates,
            "daily-sleep",
            source_key="daily-sleep",
            weekdays=list(range(7)),
            start_time="00:00",
            duration_minutes=480,
            title="Sleep",
            description="Midnight-to-8:00 sleep anchor from the supplied operating plan.",
        )
    )
    templates.append(
        _base_template(
            source_key="daily-wind-down",
            title="Wind down and prepare for sleep",
            category="custom",
            weekdays=list(range(7)),
            start_time="23:00",
            duration_minutes=60,
            flexibility="optional",
            priority=70,
            requires_completion=False,
            description=(
                "Dim screens, complete the 10-minute reset, and use easy mobility or quiet time."
            ),
        )
    )
    templates.append(
        _base_template(
            source_key="work",
            title="Work",
            category="work",
            weekdays=[1, 2, 4],
            start_time="12:30",
            duration_minutes=300,
            flexibility="fixed",
            priority=100,
            description=(
                "Fixed work shift supplied by the user: Tuesday, Wednesday, and "
                "Friday, 12:30-5:30 PM."
            ),
        )
    )

    def focus(
        key: str,
        weekday: int,
        start: str,
        duration: int,
        title: str = "Personal project / semester preparation",
    ) -> None:
        templates.append(
            _base_template(
                source_key=key,
                title=title,
                category="study",
                weekdays=[weekday],
                start_time=start,
                duration_minutes=duration,
                priority=75,
                may_split=True,
                description=(
                    "Flexible focused work. Start with one defined outcome and use "
                    "50-minute focus / 10-minute movement cycles."
                ),
            )
        )

    def free(key: str, weekday: int, start: str, duration: int, title: str) -> None:
        templates.append(
            _base_template(
                source_key=key,
                title=title,
                category="free_time",
                weekdays=[weekday],
                start_time=start,
                duration_minutes=duration,
                flexibility="optional",
                priority=25,
                requires_completion=False,
            )
        )

    # Monday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "mon-wake-breakfast",
                source_key="mon-breakfast",
                weekdays=[0],
                start_time="08:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "mon-lunch",
                source_key="mon-lunch",
                weekdays=[0],
                start_time="12:00",
                duration_minutes=40,
            ),
            _clone_template(
                source_templates,
                "mon-lift-a",
                source_key="mon-lift-a",
                weekdays=[0],
                start_time="13:30",
                duration_minutes=70,
            ),
            _clone_template(
                source_templates,
                "mon-cooldown-snack",
                source_key="mon-recovery-snack",
                weekdays=[0],
                start_time="14:40",
                duration_minutes=35,
            ),
            _clone_template(
                source_templates,
                "mon-cook-dinner",
                source_key="mon-dinner",
                weekdays=[0],
                start_time="17:15",
                duration_minutes=75,
                title="Cook and eat lemon-Parmesan chicken dinner",
                meal_from="mon-dinner",
            ),
            _clone_template(
                source_templates,
                "mon-guitar",
                source_key="mon-guitar",
                weekdays=[0],
                start_time="20:30",
                duration_minutes=20,
            ),
        ]
    )
    focus("mon-focus-1", 0, "09:00", 180)
    focus("mon-focus-2", 0, "15:15", 120)
    focus("mon-light-focus", 0, "18:30", 120, "Light project work or weekly preparation")
    free("mon-free", 0, "20:50", 130, "Free time, friends, reading, or hobbies")

    # Tuesday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "tue-breakfast",
                source_key="tue-breakfast",
                weekdays=[1],
                start_time="08:00",
                duration_minutes=30,
                title="Wake, water, and cinnamon-banana protein French toast",
            ),
            _clone_template(
                source_templates,
                "tue-lunch",
                source_key="tue-lunch",
                weekdays=[1],
                start_time="11:30",
                duration_minutes=45,
            ),
            _clone_template(
                source_templates,
                "tue-conditioning",
                source_key="tue-conditioning",
                weekdays=[1],
                start_time="17:45",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "tue-mobility",
                source_key="tue-mobility",
                weekdays=[1],
                start_time="18:15",
                duration_minutes=15,
            ),
            _clone_template(
                source_templates,
                "tue-cook-dinner",
                source_key="tue-dinner",
                weekdays=[1],
                start_time="18:30",
                duration_minutes=45,
                title="Cook and eat beef and broccoli stir-fry",
                meal_from="tue-dinner",
            ),
            _clone_template(
                source_templates,
                "tue-guitar",
                source_key="tue-guitar",
                weekdays=[1],
                start_time="22:00",
                duration_minutes=20,
            ),
        ]
    )
    focus("tue-focus-1", 1, "08:30", 180)
    focus("tue-focus-2", 1, "20:00", 120, "Project work or semester preparation")
    free("tue-relax", 1, "22:20", 40, "Relax and prepare for Wednesday")

    # Wednesday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "wed-breakfast",
                source_key="wed-breakfast",
                weekdays=[2],
                start_time="08:00",
                duration_minutes=30,
            ),
            _base_template(
                source_key="wed-lunch",
                title="Cook and eat Mediterranean chicken pita",
                category="meal",
                weekdays=[2],
                start_time="11:30",
                duration_minutes=45,
                priority=80,
                description=(
                    "Ingredients: 5 oz chicken breast; whole-grain pita; tomato; "
                    "cucumber; red onion; spinach; feta; hummus; Greek yogurt; lemon; "
                    "garlic; dill or parsley."
                ),
            )
            | {
                "meal_items": [
                    {
                        "food_name": "Mediterranean chicken pita with tzatziki",
                        "unit": "recipe serving",
                        "planned_quantity": 1,
                        "calories_per_unit": 620,
                        "protein_grams_per_unit": 46,
                    }
                ],
                "checklist_items": [
                    {"title": "Season and sear chicken; rest and slice", "position": 0},
                    {"title": "Mix yogurt, cucumber, lemon, garlic, and herbs", "position": 1},
                    {
                        "title": (
                            "Warm pita and fill with hummus, vegetables, feta, chicken, "
                            "and tzatziki"
                        ),
                        "position": 2,
                    },
                ],
            },
            _clone_template(
                source_templates,
                "wed-snack",
                source_key="wed-snack",
                weekdays=[2],
                start_time="17:30",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "wed-lift-b",
                source_key="wed-lift-b",
                weekdays=[2],
                start_time="18:00",
                duration_minutes=70,
            ),
            _clone_template(
                source_templates,
                "wed-dinner",
                source_key="wed-dinner",
                weekdays=[2],
                start_time="19:15",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "wed-guitar-stretch",
                source_key="wed-guitar-stretch",
                weekdays=[2],
                start_time="21:45",
                duration_minutes=20,
            ),
        ]
    )
    focus("wed-focus-1", 2, "08:30", 180)
    focus("wed-focus-2", 2, "20:15", 90, "Project work, coding, or semester preparation")
    free("wed-free", 2, "22:05", 55, "Free time")

    # Thursday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "thu-breakfast",
                source_key="thu-breakfast",
                weekdays=[3],
                start_time="08:00",
                duration_minutes=30,
                title="Wake, water, and spinach-feta omelet with breakfast potatoes",
            ),
            _clone_template(
                source_templates,
                "thu-lunch",
                source_key="thu-lunch",
                weekdays=[3],
                start_time="12:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "thu-cook-dinner",
                source_key="thu-dinner",
                weekdays=[3],
                start_time="17:30",
                duration_minutes=60,
                title="Cook and eat turkey meatballs, spaghetti, and zucchini",
                meal_from="thu-dinner",
            ),
            _clone_template(
                source_templates,
                "thu-mobility",
                source_key="thu-mobility",
                weekdays=[3],
                start_time="21:00",
                duration_minutes=15,
            ),
        ]
    )
    focus("thu-focus-1", 3, "08:30", 210)
    focus("thu-focus-2", 3, "13:00", 180, "Personal project, errands, or semester preparation")
    free("thu-buffer", 3, "16:00", 90, "Buffer, errands, or unplanned time")
    free("thu-free", 3, "18:30", 150, "Free time or hobbies")
    focus("thu-admin", 3, "21:15", 45, "Plan Friday and handle light admin")
    free("thu-relax", 3, "22:00", 60, "Relax")

    # Friday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "fri-breakfast",
                source_key="fri-breakfast",
                weekdays=[4],
                start_time="08:00",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "fri-lunch",
                source_key="fri-lunch",
                weekdays=[4],
                start_time="11:30",
                duration_minutes=45,
            ),
            _clone_template(
                source_templates,
                "fri-lift-c",
                source_key="fri-lift-c",
                weekdays=[4],
                start_time="17:45",
                duration_minutes=70,
            ),
            _clone_template(
                source_templates,
                "fri-dinner",
                source_key="fri-dinner",
                weekdays=[4],
                start_time="19:00",
                duration_minutes=60,
                title="Shower, cook shrimp tacos, and eat",
            ),
        ]
    )
    focus("fri-focus", 4, "08:30", 180)
    free("fri-decompress", 4, "17:30", 15, "Snack and decompress")
    free("fri-social", 4, "20:00", 180, "Friends, social time, guitar, or rest")

    # Saturday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "sat-wake-breakfast",
                source_key="sat-breakfast",
                weekdays=[5],
                start_time="08:00",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "sat-mobility-walk",
                source_key="sat-mobility",
                weekdays=[5],
                start_time="08:30",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "sat-lunch",
                source_key="sat-lunch",
                weekdays=[5],
                start_time="12:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "sat-chores",
                source_key="sat-chores",
                weekdays=[5],
                start_time="13:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "sat-cook-dinner",
                source_key="sat-dinner",
                weekdays=[5],
                start_time="18:00",
                duration_minutes=45,
            ),
        ]
    )
    focus("sat-focus-1", 5, "09:00", 180)
    focus("sat-focus-2", 5, "14:00", 180, "Major personal project or semester preparation")
    free("sat-buffer", 5, "17:00", 60, "Buffer or errands")
    free("sat-social", 5, "19:00", 240, "Friends, hobbies, events, or rest")

    # Sunday
    templates.extend(
        [
            _clone_template(
                source_templates,
                "sun-wake-breakfast",
                source_key="sun-breakfast",
                weekdays=[6],
                start_time="08:00",
                duration_minutes=30,
            ),
            _clone_template(
                source_templates,
                "sun-lunch",
                source_key="sun-lunch",
                weekdays=[6],
                start_time="12:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "sun-conditioning",
                source_key="sun-conditioning",
                weekdays=[6],
                start_time="13:00",
                duration_minutes=40,
            ),
            _clone_template(
                source_templates,
                "sun-mobility",
                source_key="sun-mobility",
                weekdays=[6],
                start_time="13:40",
                duration_minutes=20,
            ),
            _clone_template(
                source_templates,
                "sun-grocery-prep",
                source_key="sun-grocery-prep",
                weekdays=[6],
                start_time="17:00",
                duration_minutes=60,
            ),
            _clone_template(
                source_templates,
                "sun-cook-dinner",
                source_key="sun-dinner",
                weekdays=[6],
                start_time="18:00",
                duration_minutes=45,
            ),
            _clone_template(
                source_templates,
                "sun-plan-week",
                source_key="sun-plan-week",
                weekdays=[6],
                start_time="19:00",
                duration_minutes=30,
                title="Plan the week and check priorities",
            ),
            _clone_template(
                source_templates,
                "sun-guitar",
                source_key="sun-guitar",
                weekdays=[6],
                start_time="19:30",
                duration_minutes=30,
            ),
        ]
    )
    focus("sun-focus-1", 6, "09:00", 180)
    focus(
        "sun-focus-2", 6, "14:00", 180, "Creative work, personal project, or semester preparation"
    )
    free("sun-free", 6, "20:00", 180, "Free time")

    _ensure_unique_source_keys(templates)
    return templates


def build_payload(period_id: str, base_revision: int) -> dict[str, Any]:
    source_payload = json.loads(SOURCE_PAYLOAD_PATH.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": "replace_scope",
        "managed_dataset": DATASET,
        "idempotency_key": IDEMPOTENCY_KEY,
        "base_revision": base_revision,
        "scope": {
            "semester_id": period_id,
            "start_date": START_DATE,
            "end_date": END_DATE,
        },
        "source": {
            "filename": "Fresh_7-Day_Nutrition_Fitness_and_Weekly_Schedule.txt",
            "media_type": "text/plain",
            "sha256": ("a93c0ae80f36465902082e2581c2e45b21867acd18f2e6d0411dd8851d6e0f5f"),
            "description": (
                "Pre-semester plan combined with the user's fixed Tue/Wed/Fri "
                "12:30-5:30 work schedule."
            ),
        },
        "assumptions": [
            (
                "The pre-semester planning period includes July 29 through August 23; "
                "Fall 2026 remains active beginning August 24."
            ),
            (
                "Work is fixed Tuesday, Wednesday, and Friday from 12:30 PM to 5:30 PM "
                "Central; no commute was added because none was provided."
            ),
            (
                "Meals, exercise selection, recovery guidance, and estimated macros "
                "reuse the supplied seven-day nutrition and fitness plan."
            ),
            (
                "Personal-project, buffer, hobby, and free-time blocks are flexible "
                "and may be rearranged manually."
            ),
        ],
        "unresolved_fields": [],
        "templates": build_templates(source_payload),
        "occurrences": [],
        "operations": [],
    }
    validated = ImportPayload.model_validate(payload).model_dump(mode="json")
    return cast(dict[str, Any], validated)


def preflight_payload() -> dict[str, Any]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        schedule = ScheduleService(session)
        period = schedule.create_semester(
            name=PERIOD_NAME,
            start_date=START_DAY,
            end_date=END_DAY,
            activate=False,
        )
        payload = build_payload(period.id, schedule.get_settings().schedule_revision)
        if payload != build_payload(period.id, schedule.get_settings().schedule_revision):
            raise RuntimeError("pre-semester payload generation is not deterministic")
        draft = ImportService(session).create_draft(payload)

        issues = [f"{issue.severity.value}:{issue.code}:{issue.message}" for issue in draft.issues]
        if draft.status.value != "ready" or issues:
            detail = "; ".join(issues) or f"draft status is {draft.status.value}"
            raise RuntimeError(f"pre-semester payload preflight failed: {detail}")

        occurrence_records = [
            change.after_json
            for change in draft.changes
            if change.entity_type.value == "occurrence" and change.after_json is not None
        ]
        occurrence_keys = [record["source_key"] for record in occurrence_records]
        if len(occurrence_keys) != len(set(occurrence_keys)):
            raise RuntimeError("preflight generated duplicate occurrence source keys")
        occurrence_dates = [record["occurrence_date"] for record in occurrence_records]
        if min(occurrence_dates) != START_DATE or max(occurrence_dates) != END_DATE:
            raise RuntimeError(
                "materialized occurrence dates do not cover the complete import scope"
            )

        earliest_start = min(
            datetime.fromisoformat(record["planned_start_utc"]) for record in occurrence_records
        )
        latest_end = max(
            datetime.fromisoformat(record["planned_end_utc"]) for record in occurrence_records
        )
        expected_start = datetime(2026, 7, 29, 5, tzinfo=UTC)
        expected_end = datetime(2026, 8, 24, 5, tzinfo=UTC)
        if earliest_start != expected_start or latest_end != expected_end:
            raise RuntimeError(
                "materialized UTC boundaries do not match midnight Central at both ends"
            )

        work_dates = [
            record["occurrence_date"]
            for record in occurrence_records
            if record["source_key"].startswith("template:prep-work:")
        ]
        expected_work_dates: list[str] = []
        current = START_DAY
        while current <= END_DAY:
            if current.weekday() in {1, 2, 4}:
                expected_work_dates.append(current.isoformat())
            current += timedelta(days=1)
        if work_dates != expected_work_dates:
            raise RuntimeError(
                "fixed-work recurrence mismatch: "
                f"expected {expected_work_dates}, generated {work_dates}"
            )

        return {
            "status": draft.status.value,
            "templates": len(payload["templates"]),
            "occurrences": len(occurrence_records),
            "work_dates": work_dates,
            "issues": issues,
        }


def ensure_planning_period() -> tuple[str, dict[str, Any] | None]:
    factory = get_session_factory()
    with factory() as session:
        period = session.scalars(
            select(Semester).where(
                Semester.name == PERIOD_NAME,
                Semester.start_date == START_DAY,
                Semester.end_date == END_DAY,
            )
        ).one_or_none()
        if period is None:
            period = ScheduleService(session).create_semester(
                name=PERIOD_NAME,
                start_date=START_DAY,
                end_date=END_DAY,
                activate=False,
            )
            session.commit()
        existing_draft = session.scalar(
            select(ImportDraft).where(ImportDraft.idempotency_key == IDEMPOTENCY_KEY)
        )
        if existing_draft is None:
            return period.id, None
        if (
            existing_draft.semester_id != period.id
            or existing_draft.managed_dataset != DATASET
            or existing_draft.scope_start_date != START_DAY
            or existing_draft.scope_end_date != END_DAY
        ):
            raise RuntimeError(f"idempotency key {IDEMPOTENCY_KEY!r} belongs to a different import")
        return period.id, {
            "id": existing_draft.id,
            "status": existing_draft.status.value,
            "base_revision": existing_draft.base_revision,
            "payload": existing_draft.payload_json,
        }


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
    preflight = preflight_payload()
    if dry_run:
        print(f"status={preflight['status']}")
        print(f"templates={preflight['templates']}")
        print(f"occurrences={preflight['occurrences']}")
        print(f"work_dates={','.join(preflight['work_dates'])}")
        print(f"issues={len(preflight['issues'])}")
        return

    period_id, existing_draft = ensure_planning_period()

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
                {"start_date": START_DATE, "end_date": END_DATE},
            )
        )
        validated = build_payload(period_id, context["schedule_revision"])
        PAYLOAD_PATH.write_text(
            json.dumps(validated, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        if existing_draft is None:
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
            if _without_base_revision(existing_draft["payload"]) != _without_base_revision(
                validated
            ):
                raise RuntimeError(
                    "the existing draft has different content; bump IDEMPOTENCY_KEY "
                    "before creating a replacement"
                )
            if (
                existing_draft["status"] == "ready"
                and existing_draft["base_revision"] != context["schedule_revision"]
            ):
                raise RuntimeError(
                    "the existing ready draft is stale; bump IDEMPOTENCY_KEY before "
                    "creating a replacement"
                )
            draft_id = existing_draft["id"]
        reviewed = result_data(await session.call_tool("get_draft", {"draft_id": draft_id}))

    RESULT_PATH.write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"draft_id={reviewed['id']}")
    print(f"status={reviewed['status']}")
    print(f"base_revision={reviewed['base_revision']}")
    print(f"templates={preflight['templates']}")
    total_changes = reviewed["add_count"] + reviewed["change_count"] + reviewed["cancel_count"]
    print(f"changes={total_changes}")
    print(f"adds={reviewed['add_count']}")
    print(f"updates={reviewed['change_count']}")
    print(f"cancels={reviewed['cancel_count']}")
    print(f"errors={reviewed['error_count']}")
    print(f"issues={len(reviewed['issues'])}")
    print(f"review_url={reviewed['review_url']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate and prepare the reviewable pre-semester schedule import."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate in memory without reading or mutating the live Semester Ops database.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(dry_run=arguments.dry_run))
