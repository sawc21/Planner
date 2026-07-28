# Semester Ops agent guide

Semester Ops is a single-user, localhost-only Python application. SQLite is authoritative; Google Calendar is a controlled projection and Blackboard ICS is read-only.

## Commands

- Install: `.venv\Scripts\uv sync --locked --extra dev`
- Migrate: `python -m alembic upgrade head`
- Run web: `python -m semester_ops.web.main`
- Run MCP: `python -m semester_ops.mcp_server`
- Test: `python -m pytest`
- Lint: `python -m ruff check src tests migrations`
- Format check: `python -m ruff format --check src tests migrations`
- Type check: `python -m mypy src`

## Architecture rules

- Keep business rules in `domain/` and `application/`; web, MCP, and integrations are adapters.
- MCP may create drafts but must not approve them, mutate the live schedule directly, or trigger sync.
- Never write to Google `primary`; use only the configured app-created development calendar.
- Never write to Blackboard.
- Use timezone-aware UTC instants for occurrences and `America/Chicago` wall-clock rules for templates.
- Preserve audit history with soft cancellation where behavior must remain explainable.
- Surface explicit errors; do not swallow integration or validation failures.

## Verification rules

- Use fake adapters for automated Google tests and fixture ICS feeds for Blackboard tests.
- Live Google testing is opt-in and restricted to `Semester Ops - Dev`.
- Do not commit databases, OAuth credentials/tokens, private ICS URLs, or uploaded source documents.
