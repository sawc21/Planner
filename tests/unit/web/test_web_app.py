from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import nullcontext
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from semester_ops.config import Settings
from semester_ops.web.main import create_app
from semester_ops.web.security import safe_return_path
from semester_ops.web.services import (
    BlockEditCommand,
    MealItemCommand,
    SettingsCommand,
    ViewData,
    WorkoutSetCommand,
)


class FakeWebServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.sync_conflicts: list[ViewData] = []

    def get_today(self, day: date | None = None) -> ViewData:
        return {
            "selected_date": str(day or date(2026, 7, 28)),
            "date_label": "Tuesday, July 28",
            "previous_date": "2026-07-27",
            "next_date": "2026-07-29",
            "semester_name": "Fall field test",
            "summary": {
                "completion_percent": 50,
                "completed_blocks": 1,
                "trackable_blocks": 2,
                "calories_consumed": 540,
                "calorie_target": 2600,
                "calorie_percent": 21,
                "protein_consumed": 42,
                "protein_target": 180,
                "workout_sets_completed": 2,
                "workout_sets_total": 5,
                "workout_percent": 40,
                "workout_actual_minutes": 18,
            },
            "sync": {"dirty_count": 1, "last_success_at": None},
            "current_block": {"title": "Deep work", "remaining_minutes": 35},
            "now_label": "9:25 AM",
            "blocks": [self._block()],
        }

    def get_week(self, anchor: date | None = None) -> ViewData:
        block = self._block()
        return {
            "week_label": "July 27 - August 2",
            "anchor_date": str(anchor or date(2026, 7, 27)),
            "previous_anchor": "2026-07-20",
            "next_anchor": "2026-08-03",
            "summary": {
                "planned_hours": 22,
                "block_count": 14,
                "fixed_hours": 11,
                "open_hours": 18,
                "conflict_count": 0,
            },
            "days": [
                {
                    "weekday_short": "TUE",
                    "day_number": 28,
                    "is_today": True,
                    "blocks": [block],
                }
            ],
            "deadlines": [],
        }

    def list_assignments(self, state: str | None = None) -> ViewData:
        return {
            "active_state": state,
            "counts": {"inbox": 1, "planned": 0, "due_soon": 1},
            "source": {"status": "connected", "label": "Connected", "last_refreshed_at": None},
            "assignments": [
                {
                    "id": "a1",
                    "state": "inbox",
                    "course_code": "CS 401",
                    "course_name": "Distributed Systems",
                    "course_color": "#3b5e77",
                    "title": "Consensus notes",
                    "due_day": "FRI 31",
                    "due_time": "11:59 PM",
                    "urgency": "high",
                    "estimated_minutes": 60,
                    "linked_block_count": 0,
                    "linked_blocks": [],
                }
            ],
        }

    def list_imports(self) -> ViewData:
        return {
            "counts": {"pending": 1, "applied": 0, "rejected": 0},
            "drafts": [
                {
                    "id": "d1",
                    "status": "pending",
                    "mode": "patch",
                    "managed_dataset": "semester",
                    "title": "Fall schedule",
                    "scope_label": "July 28 - December 12",
                    "created_at": "2026-07-28",
                    "base_revision": 1,
                    "add_count": 3,
                    "change_count": 1,
                    "cancel_count": 0,
                }
            ],
        }

    def get_import(self, draft_id: str) -> ViewData:
        return {
            "draft": {
                "id": draft_id,
                "title": "Fall schedule",
                "status": "pending",
                "mode": "patch",
                "managed_dataset": "semester",
                "start_date": "2026-08-20",
                "end_date": "2026-12-12",
                "base_revision": 1,
                "current_revision": 1,
                "is_stale": False,
            },
            "issues": [],
            "changes": [
                {
                    "operation": "add",
                    "date_label": "MON 24",
                    "start_local": "2026-08-24T09:00:00",
                    "end_local": "2026-08-24T10:00:00",
                    "title": "Algorithms",
                }
            ],
            "error_count": 0,
            "warning_count": 0,
            "payload_json": "{}",
        }

    def get_settings_view(self) -> ViewData:
        return {
            "settings": {
                "operational_day_start": "04:00",
                "missed_grace_minutes": 30,
                "weight_unit": "lb",
                "calorie_target": 2600,
                "protein_target_grams": 180,
                "blackboard_configured": False,
            },
            "connectors": [],
            "sync_runs": [],
            "sync_conflicts": self.sync_conflicts,
        }

    def get_block(self, block_id: str) -> ViewData:
        block = self._block()
        block.update(
            start_local="2026-07-28T09:00:00",
            end_local="2026-07-28T10:30:00",
            project_to_calendar=True,
        )
        return {
            "block": block,
            "return_to": "/",
            "timezone": "America/Chicago",
            "categories": [{"value": "study", "label": "Study"}],
        }

    def set_block_status(self, block_id: str, action: str) -> Mapping[str, Any]:
        self.calls.append(("status", (block_id, action)))
        return {"message": "Block started."}

    def update_block(self, block_id: str, command: BlockEditCommand) -> None:
        self.calls.append(("edit", (block_id, command)))

    def move_block(self, block_id: str, minutes: int) -> None:
        self.calls.append(("move", (block_id, minutes)))

    def set_checklist_item(self, item_id: str, *, completed: bool) -> None:
        self.calls.append(("checklist", (item_id, completed)))

    def set_meal_item(self, item_id: str, command: MealItemCommand) -> None:
        self.calls.append(("meal", (item_id, command)))

    def set_workout_set(self, set_id: str, command: WorkoutSetCommand) -> None:
        self.calls.append(("workout", (set_id, command)))

    def set_assignment_state(
        self,
        assignment_id: str,
        *,
        state: str,
        estimated_minutes: int | None,
    ) -> None:
        self.calls.append(("assignment", (assignment_id, state, estimated_minutes)))

    def approve_import(self, draft_id: str, *, allow_warnings: bool) -> Mapping[str, Any]:
        self.calls.append(("approve", (draft_id, allow_warnings)))
        return {"message": "Draft applied."}

    def reject_import(self, draft_id: str) -> None:
        self.calls.append(("reject", draft_id))

    def update_settings(self, command: SettingsCommand) -> None:
        self.calls.append(("settings", command))

    def sync_now(self) -> Mapping[str, Any]:
        self.calls.append(("sync", None))
        return {"message": "Sync complete.", "tone": "success"}

    def resolve_sync_conflict(self, conflict_id: str, resolution: str) -> Mapping[str, Any]:
        self.calls.append(("resolve_conflict", (conflict_id, resolution)))
        return {"message": "Conflict resolved."}

    @staticmethod
    def _block() -> ViewData:
        return {
            "id": "b1",
            "title": "Deep work",
            "category": "study",
            "category_label": "Study",
            "status": "planned",
            "status_label": "Planned",
            "flexibility": "flexible",
            "start_local": "2026-07-28T09:00:00",
            "end_local": "2026-07-28T10:30:00",
            "duration_minutes": 90,
            "gap_before_minutes": 30,
            "checklist_items": [
                {"id": "c1", "label": "Open notes", "completed": False, "required": True}
            ],
            "meal_items": [],
            "workout_exercises": [],
        }


@pytest.fixture
def fake_services() -> FakeWebServices:
    return FakeWebServices()


@pytest.fixture
def client(fake_services: FakeWebServices) -> TestClient:
    settings = Settings(
        database_path="var/unused-web-test.db",
        secret_key="test-secret-that-is-not-used-outside-tests",
    )
    app = create_app(
        settings=settings,
        service_factory=lambda: nullcontext(fake_services),
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", "Deep work"),
        ("/week", "July 27 - August 2"),
        ("/assignments", "Consensus notes"),
        ("/imports", "Fall schedule"),
        ("/imports/d1", "Proposed changes"),
        ("/settings", "Connections with boundaries"),
        ("/blocks/b1/edit", "Precise schedule edit"),
    ],
)
def test_primary_pages_render(client: TestClient, path: str, expected: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert expected.lower() in response.text.lower()
    assert response.headers["x-frame-options"] == "DENY"
    assert "Semester Ops" in response.text


def test_status_action_requires_csrf_and_calls_service(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    token = _csrf_from(client.get("/").text)

    response = client.post(
        "/blocks/b1/status",
        data={"_csrf": token, "action": "start", "return_to": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert ("status", ("b1", "start")) in fake_services.calls


def test_invalid_csrf_is_rejected(client: TestClient, fake_services: FakeWebServices) -> None:
    client.get("/")

    response = client.post(
        "/blocks/b1/status",
        data={"_csrf": "wrong", "action": "start"},
    )

    assert response.status_code == 403
    assert fake_services.calls == []


def test_import_approval_and_manual_sync(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    token = _csrf_from(client.get("/imports/d1").text)

    approval = client.post(
        "/imports/d1/approve",
        data={"_csrf": token, "allow_warnings": "true"},
        follow_redirects=False,
    )
    sync = client.post(
        "/sync",
        data={"_csrf": token, "return_to": "/settings"},
        follow_redirects=False,
    )

    assert approval.status_code == 303
    assert sync.status_code == 303
    assert ("approve", ("d1", True)) in fake_services.calls
    assert ("sync", None) in fake_services.calls


def test_calendar_conflict_resolution_requires_csrf_and_calls_service(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    token = _csrf_from(client.get("/settings").text)

    response = client.post(
        "/sync-conflicts/conflict-1/resolve",
        data={"_csrf": token, "resolution": "use_remote"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings"
    assert ("resolve_conflict", ("conflict-1", "use_remote")) in fake_services.calls


def test_settings_renders_both_calendar_conflict_choices(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    fake_services.sync_conflicts = [
        {
            "id": "conflict-1",
            "title": "Calculus I",
            "planner_start_local": datetime(2026, 8, 25, 8, 0),
            "planner_end_local": datetime(2026, 8, 25, 9, 0),
            "remote_start_local": datetime(2026, 8, 25, 9, 0),
            "remote_end_local": datetime(2026, 8, 25, 10, 0),
        }
    ]

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Calendar conflicts" in response.text
    assert "Keep planner" in response.text
    assert "Use Google time" in response.text


def test_return_path_never_redirects_off_site() -> None:
    assert safe_return_path("/week?anchor=2026-07-27") == "/week?anchor=2026-07-27"
    assert safe_return_path("https://example.com") == "/"
    assert safe_return_path("//example.com") == "/"


def _csrf_from(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
    assert match is not None
    return match.group(1)
