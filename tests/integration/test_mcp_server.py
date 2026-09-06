from typing import Any

import pytest

from semester_ops.mcp_server import McpTools, create_mcp_server


class FakePlannerService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def get_import_schema(self):
        self.calls.append(("get_import_schema", ()))
        return {"schema_version": "1"}

    def get_planning_context(self, start_date, end_date):
        self.calls.append(("get_planning_context", (start_date, end_date)))
        return {"revision": 7, "blocks": []}

    def list_assignment_inbox(self, status):
        self.calls.append(("list_assignment_inbox", (status,)))
        return {"assignments": []}

    def get_assignment_study_schema(self):
        self.calls.append(("get_assignment_study_schema", ()))
        return {"schema_version": "1.0", "payload_schema": {}}

    def get_assignment_study(self, assignment_id):
        self.calls.append(("get_assignment_study", (assignment_id,)))
        return {"assignment": {"id": assignment_id}, "study": None}

    def submit_assignment_study_set(self, assignment_id, payload, idempotency_key):
        self.calls.append(
            (
                "submit_assignment_study_set",
                (assignment_id, payload, idempotency_key),
            )
        )
        return {
            "assignment_id": assignment_id,
            "status": "created",
            "review_url": f"/assignments/{assignment_id}",
        }

    def create_import_draft(self, payload, idempotency_key, base_revision):
        self.calls.append(("create_import_draft", (payload, idempotency_key, base_revision)))
        return {"draft_id": "draft-1", "review_url": "/imports/draft-1"}

    def create_planning_draft(self, payload, idempotency_key, base_revision):
        self.calls.append(("create_planning_draft", (payload, idempotency_key, base_revision)))
        return {"draft_id": "draft-2", "review_url": "/imports/draft-2"}

    def get_draft(self, draft_id):
        self.calls.append(("get_draft", (draft_id,)))
        return {"draft_id": draft_id, "status": "pending"}


def test_mcp_adapter_exposes_planning_and_assignment_study_service_calls() -> None:
    service = FakePlannerService()
    tools = McpTools(lambda: service)

    assert tools.get_import_schema()["schema_version"] == "1"
    assert tools.get_planning_context("2026-08-24", "2026-08-30")["revision"] == 7
    assert tools.list_assignment_inbox("INBOX") == {"assignments": []}
    assert tools.get_assignment_study_schema()["schema_version"] == "1.0"
    assert tools.get_assignment_study("assignment-1")["assignment"]["id"] == "assignment-1"
    assert (
        tools.submit_assignment_study_set(
            "assignment-1",
            {"schema_version": "1.0"},
            "study-key-1",
        )["status"]
        == "created"
    )
    assert tools.create_import_draft({"mode": "patch"}, "key-1", 7)["draft_id"] == "draft-1"
    assert tools.create_planning_draft({"mode": "patch"}, "key-2", 7)["draft_id"] == "draft-2"
    assert tools.get_draft("draft-1")["status"] == "pending"
    assert {name for name, _ in service.calls} == {
        "get_import_schema",
        "get_planning_context",
        "list_assignment_inbox",
        "get_assignment_study_schema",
        "get_assignment_study",
        "submit_assignment_study_set",
        "create_import_draft",
        "create_planning_draft",
        "get_draft",
    }


def test_mcp_adapter_rejects_unbounded_or_stale_shaped_inputs_before_service_call() -> None:
    service = FakePlannerService()
    tools = McpTools(lambda: service)

    with pytest.raises(ValueError, match="end_date"):
        tools.get_planning_context("2026-08-30", "2026-08-24")
    with pytest.raises(ValueError, match="idempotency_key"):
        tools.create_import_draft({}, " ", 0)
    with pytest.raises(ValueError, match="base_revision"):
        tools.create_planning_draft({}, "key", -1)
    with pytest.raises(ValueError, match="assignment_id"):
        tools.get_assignment_study(" ")
    with pytest.raises(ValueError, match="idempotency_key"):
        tools.submit_assignment_study_set("assignment-1", {}, " ")
    assert not service.calls


def test_fastmcp_server_can_be_constructed_with_fake_service() -> None:
    service = FakePlannerService()
    server = create_mcp_server(lambda: service)

    assert server.name == "Semester Ops"
