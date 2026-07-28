from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import date
from importlib import import_module
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

JsonObject = dict[str, Any]
JsonResult = JsonObject | list[Any]
ServiceFactory = Callable[[], "PlannerMcpService"]


class PlannerMcpService(Protocol):
    """Read/draft-only application facade consumed by the local MCP adapter."""

    def get_import_schema(self) -> JsonObject: ...

    def get_planning_context(self, start_date: str, end_date: str) -> JsonObject: ...

    def list_assignment_inbox(self, status: str | None) -> JsonObject: ...

    def create_import_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject: ...

    def create_planning_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject: ...

    def get_draft(self, draft_id: str) -> JsonObject: ...


class McpServiceUnavailable(RuntimeError):
    pass


class McpTools:
    """Validated tool functions kept independent from the STDIO transport for tests."""

    def __init__(self, service_factory: ServiceFactory) -> None:
        self._service_factory = service_factory

    def get_import_schema(self) -> JsonObject:
        """Return the canonical versioned JSON contract for reviewable imports."""

        return self._result(self._service_factory().get_import_schema())

    def get_planning_context(self, start_date: str, end_date: str) -> JsonObject:
        """Read blocks, constraints, free windows, revision, and assignments for a date range."""

        start = _iso_date(start_date, "start_date")
        end = _iso_date(end_date, "end_date")
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        return self._result(
            self._service_factory().get_planning_context(start.isoformat(), end.isoformat())
        )

    def list_assignment_inbox(self, status: str | None = None) -> JsonObject:
        """Read Blackboard assignment records; this tool never refreshes Blackboard."""

        allowed = {"inbox", "planned", "completed", "ignored", "stale", "canceled"}
        normalized = status.strip().lower() if status else None
        if normalized is not None and normalized not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        return self._result(self._service_factory().list_assignment_inbox(normalized))

    def create_import_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        """Create a reversible schedule import draft; never approve or apply it."""

        key = _idempotency_key(idempotency_key)
        revision = _revision(base_revision)
        return self._result(self._service_factory().create_import_draft(payload, key, revision))

    def create_planning_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        """Create a reversible study-placement draft; never move a live block directly."""

        key = _idempotency_key(idempotency_key)
        revision = _revision(base_revision)
        return self._result(self._service_factory().create_planning_draft(payload, key, revision))

    def get_draft(self, draft_id: str) -> JsonObject:
        """Read validation findings and a localhost review URL for an existing draft."""

        normalized = draft_id.strip()
        if not normalized:
            raise ValueError("draft_id cannot be blank")
        return self._result(self._service_factory().get_draft(normalized))

    @staticmethod
    def _result(value: JsonObject) -> JsonObject:
        if not isinstance(value, dict):
            raise TypeError("Planner MCP facade methods must return JSON objects")
        return value


def create_mcp_server(service_factory: ServiceFactory | None = None) -> FastMCP:
    tools = McpTools(service_factory or _default_service_factory)
    server = FastMCP(
        "Semester Ops",
        instructions=(
            "Read local planning context and create reviewable drafts only. "
            "No tool can approve a draft or synchronize an external service."
        ),
    )

    @server.tool()
    def get_import_schema() -> JsonObject:
        """Return the canonical versioned JSON contract for reviewable imports."""

        return tools.get_import_schema()

    @server.tool()
    def get_planning_context(start_date: str, end_date: str) -> JsonObject:
        """Read planning context within an inclusive ISO date range."""

        return tools.get_planning_context(start_date, end_date)

    @server.tool()
    def list_assignment_inbox(status: str | None = None) -> JsonObject:
        """List local read-only Blackboard assignments, optionally filtered by state."""

        return tools.list_assignment_inbox(status)

    @server.tool()
    def create_import_draft(
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        """Validate and save an import as a draft requiring browser approval."""

        return tools.create_import_draft(payload, idempotency_key, base_revision)

    @server.tool()
    def create_planning_draft(
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        """Validate and save study-placement changes as a reviewable draft."""

        return tools.create_planning_draft(payload, idempotency_key, base_revision)

    @server.tool()
    def get_draft(draft_id: str) -> JsonObject:
        """Read one draft and its validation/diff summary without applying it."""

        return tools.get_draft(draft_id)

    return server


class _SessionScopedPlannerService:
    """Open and close one SQLite transaction for every MCP tool invocation."""

    def get_import_schema(self) -> JsonObject:
        return self._object("get_import_schema")

    def get_planning_context(self, start_date: str, end_date: str) -> JsonObject:
        return self._object("get_planning_context", start_date, end_date)

    def list_assignment_inbox(self, status: str | None) -> JsonObject:
        result = self._invoke("list_assignment_inbox", status)
        if isinstance(result, list):
            return {"assignments": result}
        if isinstance(result, dict):
            return result
        raise TypeError("SemesterOpsService.list_assignment_inbox must return JSON data")

    def create_import_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        return self._object(
            "create_import_draft",
            payload,
            idempotency_key,
            base_revision,
        )

    def create_planning_draft(
        self,
        payload: JsonObject,
        idempotency_key: str,
        base_revision: int,
    ) -> JsonObject:
        return self._object(
            "create_planning_draft",
            payload,
            idempotency_key,
            base_revision,
        )

    def get_draft(self, draft_id: str) -> JsonObject:
        return self._object("get_draft", draft_id)

    @classmethod
    def _object(cls, method_name: str, *args: object) -> JsonObject:
        result = cls._invoke(method_name, *args)
        if not isinstance(result, dict):
            raise TypeError(f"SemesterOpsService.{method_name} must return a JSON object")
        return result

    @staticmethod
    def _invoke(method_name: str, *args: object) -> JsonResult:
        try:
            facade_module = import_module("semester_ops.application.facade")
            service_type = facade_module.SemesterOpsService
            from semester_ops.db.session import get_session_factory
        except (ImportError, AttributeError) as exc:
            raise McpServiceUnavailable(
                "Semester Ops application facade is unavailable; "
                "install and migrate the project first"
            ) from exc

        with get_session_factory()() as session:
            try:
                service = service_type(session)
                result = getattr(service, method_name)(*args)
                session.commit()
            except Exception:
                session.rollback()
                raise
        if not isinstance(result, (dict, list)):
            raise TypeError(f"SemesterOpsService.{method_name} must return JSON data")
        return result


def _default_service_factory() -> PlannerMcpService:
    return _SessionScopedPlannerService()


def _iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc


def _idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("idempotency_key cannot be blank")
    if len(normalized) > 200:
        raise ValueError("idempotency_key cannot exceed 200 characters")
    return normalized


def _revision(value: int) -> int:
    if value < 0:
        raise ValueError("base_revision cannot be negative")
    return value


mcp = create_mcp_server()


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
