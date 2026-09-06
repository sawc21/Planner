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
    BlockCreateCommand,
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
        self.connectors: list[ViewData] = []
        self.sync_runs: list[ViewData] = []
        self.block_override: ViewData | None = None

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
                    "date": "2026-07-28",
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
            "connectors": self.connectors,
            "sync_runs": self.sync_runs,
            "sync_conflicts": self.sync_conflicts,
        }

    def get_block(self, block_id: str) -> ViewData:
        block = dict(self.block_override or self._block())
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

    def get_new_block(self, day: date | None = None) -> ViewData:
        target_day = day or date(2026, 7, 28)
        self.calls.append(("new", target_day))
        return {
            "block": {
                "title": "",
                "category": "study",
                "flexibility": "flexible",
                "start_local": datetime.combine(target_day, datetime.min.time()).replace(hour=9),
                "end_local": datetime.combine(target_day, datetime.min.time()).replace(hour=10),
                "notes": None,
                "project_to_calendar": True,
            },
            "timezone": "America/Chicago",
            "categories": [{"value": "study", "label": "Study"}],
        }

    def create_block(self, command: BlockCreateCommand) -> str:
        self.calls.append(("create", command))
        return "created-block"

    def duplicate_block(self, block_id: str) -> str:
        self.calls.append(("duplicate", block_id))
        return "duplicate-block"

    def delete_block(self, block_id: str) -> None:
        self.calls.append(("delete", block_id))

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
        ("/blocks/new?day=2026-07-28", "Create schedule block"),
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


def test_settings_renders_safe_google_failure_and_reauthorization_command(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    fake_services.connectors = [
        {
            "kind": "GOOGLE",
            "name": "Semester Ops - Dev",
            "status": "error",
            "status_label": "Action required",
            "description": "Only the app-created calendar receives events.",
            "details": [{"label": "Calendar ID", "value": "Stored locally"}],
            "notice": {
                "tone": "error",
                "title": "oauth refresh failed",
                "message": "Google authorization expired or was revoked.",
                "recovery": "Run Google setup with --reauthorize.",
                "command": (".\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize"),
            },
        }
    ]
    fake_services.sync_runs = [
        {
            "status": "failed",
            "summary": "Google sync failed",
            "started_at": datetime(2026, 7, 29, 9, 0),
            "duration_label": "1.2s",
            "message": "Google authorization expired or was revoked.",
            "recovery": "Run Google setup with --reauthorize.",
            "continuation_required": False,
        }
    ]

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Action required" in response.text
    assert "Google authorization expired or was revoked." in response.text
    assert "semester-ops-google-setup.exe --reauthorize" in response.text
    assert "1.2s" in response.text


def test_settings_renders_bounded_google_sync_progress(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    fake_services.connectors = [
        {
            "kind": "GOOGLE",
            "name": "Semester Ops - Dev",
            "status": "progress",
            "status_label": "Sync in progress",
            "description": "Only the app-created calendar receives events.",
            "details": [{"label": "Write safety", "value": "1 first / 50 later"}],
            "notice": {
                "tone": "progress",
                "title": "Bounded calendar bootstrap",
                "message": "The latest safe batch attempted 50 changes; 1428 remain.",
                "recovery": "Press Sync now again to process the next bounded batch.",
                "command": None,
            },
        }
    ]
    fake_services.sync_runs = [
        {
            "status": "partial",
            "summary": "Google sync partial",
            "started_at": datetime(2026, 7, 29, 9, 0),
            "duration_label": "8.4s",
            "message": None,
            "recovery": None,
            "continuation_required": True,
            "remote_mutations_attempted": 50,
            "remote_mutations_deferred": 1428,
        }
    ]

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Sync in progress" in response.text
    assert "1 first / 50 later" in response.text
    assert "50 attempted / 1428 remaining" in response.text
    assert "Press Sync now again" in response.text


def test_google_sync_write_limit_defaults_and_ordering() -> None:
    assert Settings.model_fields["google_initial_sync_write_limit"].default == 1
    assert Settings.model_fields["google_sync_write_limit"].default == 50

    with pytest.raises(ValueError, match="cannot exceed"):
        Settings(
            _env_file=None,
            google_initial_sync_write_limit=51,
            google_sync_write_limit=50,
        )


def test_return_path_never_redirects_off_site() -> None:
    assert safe_return_path("/week?anchor=2026-07-27") == "/week?anchor=2026-07-27"
    assert safe_return_path("https://example.com") == "/"
    assert safe_return_path("//example.com") == "/"


def test_week_block_link_preserves_the_calendar_anchor(client: TestClient) -> None:
    response = client.get("/week?anchor=2026-07-27")

    assert response.status_code == 200
    assert 'href="/blocks/b1/edit?return_to=/week%3Fanchor%3D2026-07-27"' in response.text
    assert '<meta name="theme-color" content="#102a37">' in response.text


def test_edit_page_has_a_safe_calendar_back_link(client: TestClient) -> None:
    response = client.get("/blocks/b1/edit?return_to=%2Fweek%3Fanchor%3D2026-07-27")

    assert response.status_code == 200
    assert 'aria-label="Back to calendar"' in response.text
    assert 'href="/week?anchor=2026-07-27"' in response.text
    assert 'href="/week" class="nav-link is-active"' in response.text


def test_edit_page_rejects_an_external_back_link(client: TestClient) -> None:
    response = client.get("/blocks/b1/edit?return_to=https%3A%2F%2Fexample.com%2Fcalendar")

    assert response.status_code == 200
    assert 'aria-label="Back to calendar"' in response.text
    assert 'href="/" aria-label="Back to calendar"' in response.text


def test_edit_page_renders_meal_ingredients_and_cooking_steps(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    block = fake_services._block()
    block.update(
        title="Lemon-Parmesan chicken dinner",
        category="meal",
        meal_items=[
            {
                "name": "Lemon-Parmesan chicken",
                "planned_quantity": "1",
                "unit": "serving",
                "calories": "720",
                "protein_grams": "58",
                "required": True,
            }
        ],
        meal_guide={
            "name": "Lemon-Parmesan chicken, potatoes, and green beans",
            "ingredients": ["6 oz chicken breast", "10 oz baby potatoes", "green beans"],
            "steps": [
                "Roast the potatoes for 15 minutes.",
                "Add the chicken and green beans and roast until the chicken reaches 165 F.",
            ],
            "source_label": "Fresh 7-day source plan",
            "missing_message": None,
        },
    )
    fake_services.block_override = block

    response = client.get("/blocks/b1/edit")

    assert response.status_code == 200
    assert "MEAL EXECUTION" in response.text
    assert "Ingredients" in response.text
    assert "6 oz chicken breast" in response.text
    assert "Cook it" in response.text
    assert "chicken reaches 165 F" in response.text
    assert "720 kcal / 58g protein" in response.text


def test_edit_page_renders_workout_sets_reps_and_recovery(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    block = fake_services._block()
    block.update(
        title="Full-body Lift B",
        category="workout",
        source_notes="Hinge, overhead push, and vertical pull.",
        workout_summary={"completed_sets": 1, "total_sets": 2},
        workout_exercises=[
            {
                "name": "Standing overhead press",
                "planned_sets": 2,
                "rep_target": "6-10 reps",
                "target_weight": "40",
                "weight_unit": "lb",
                "notes": "Keep the ribs stacked.",
                "sets": [
                    {
                        "set_number": 1,
                        "target_reps": 8,
                        "completed": True,
                        "actual_reps": 8,
                        "actual_weight": "40",
                    },
                    {
                        "set_number": 2,
                        "target_reps": 8,
                        "completed": False,
                        "actual_reps": None,
                        "actual_weight": None,
                    },
                ],
            }
        ],
        workout_guidance=[
            {"label": "Before", "text": "Warm up for 5-8 minutes."},
            {"label": "Between sets", "text": "Rest 2-3 minutes for compounds."},
            {"label": "After", "text": "Rehydrate and prioritize sleep."},
        ],
    )
    fake_services.block_override = block

    response = client.get("/blocks/b1/edit")

    assert response.status_code == 200
    assert "TRAINING PLAN" in response.text
    assert "Standing overhead press" in response.text
    assert "2 sets" in response.text
    assert "6-10 reps" in response.text
    assert "8 target reps" in response.text
    assert "Logged: 8 reps @ 40 lb" in response.text
    assert "Rest 2-3 minutes for compounds." in response.text


def test_edit_redirects_back_to_the_same_calendar_week(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    return_to = "/week?anchor=2026-07-27"
    token = _csrf_from(client.get(f"/blocks/b1/edit?return_to={return_to}").text)

    response = client.post(
        "/blocks/b1/edit",
        data={
            "_csrf": token,
            "title": "Deep work",
            "planned_start_local": "2026-07-28T09:00",
            "planned_end_local": "2026-07-28T10:30",
            "category": "study",
            "flexibility": "flexible",
            "notes": "",
            "project_to_calendar": "true",
            "return_to": return_to,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == return_to
    assert any(call_name == "edit" for call_name, _ in fake_services.calls)


def test_new_block_form_uses_requested_day_and_preserves_return_path(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    response = client.get("/blocks/new?day=2026-08-03&return_to=%2Fweek%3Fanchor%3D2026-08-03")

    assert response.status_code == 200
    assert 'value="2026-08-03T09:00"' in response.text
    assert 'value="/week?anchor=2026-08-03"' in response.text
    assert ("new", date(2026, 8, 3)) in fake_services.calls


def test_create_block_requires_csrf_and_redirects_to_the_calendar(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    return_to = "/week?anchor=2026-08-03"
    token = _csrf_from(
        client.get("/blocks/new?day=2026-08-03&return_to=%2Fweek%3Fanchor%3D2026-08-03").text
    )
    payload = {
        "title": "Office hours",
        "planned_start_local": "2026-08-03T13:00",
        "planned_end_local": "2026-08-03T14:00",
        "category": "study",
        "flexibility": "flexible",
        "notes": "Bring questions",
        "project_to_calendar": "true",
        "return_to": return_to,
    }

    rejected = client.post("/blocks", data=payload, follow_redirects=False)
    created = client.post(
        "/blocks",
        data={"_csrf": token, **payload},
        follow_redirects=False,
    )

    assert rejected.status_code == 422
    assert created.status_code == 303
    assert created.headers["location"] == return_to
    create_calls = [value for name, value in fake_services.calls if name == "create"]
    assert len(create_calls) == 1
    assert create_calls[0].title == "Office hours"


def test_duplicate_creates_an_independent_block_and_opens_its_editor(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    return_to = "/week?anchor=2026-07-27"
    token = _csrf_from(client.get("/blocks/b1/edit").text)

    response = client.post(
        "/blocks/b1/duplicate",
        data={"_csrf": token, "return_to": return_to},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/blocks/duplicate-block/edit?return_to=%2Fweek%3Fanchor%3D2026-07-27"
    )
    assert ("duplicate", "b1") in fake_services.calls


def test_delete_requires_confirmation_and_preserves_safe_return_path(
    client: TestClient,
    fake_services: FakeWebServices,
) -> None:
    token = _csrf_from(client.get("/blocks/b1/edit").text)

    missing_confirmation = client.post(
        "/blocks/b1/delete",
        data={"_csrf": token, "return_to": "/week"},
        follow_redirects=False,
    )
    removed = client.post(
        "/blocks/b1/delete",
        data={
            "_csrf": token,
            "confirmation": "true",
            "return_to": "https://example.com/calendar",
        },
        follow_redirects=False,
    )

    assert missing_confirmation.status_code == 422
    assert removed.status_code == 303
    assert removed.headers["location"] == "/"
    assert fake_services.calls.count(("delete", "b1")) == 1


def test_calendar_views_offer_direct_block_creation(client: TestClient) -> None:
    today = client.get("/?day=2026-07-28")
    week = client.get("/week?anchor=2026-07-27")

    assert "/blocks/new?day=2026-07-28" in today.text
    assert "/blocks/new?day=2026-07-28" in week.text
    assert "return_to=/week%3Fanchor%3D2026-07-27" in week.text


def _csrf_from(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
    assert match is not None
    return match.group(1)
