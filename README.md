# Semester Ops

A localhost-first full-day execution tracker built with FastAPI and SQLite. It combines a Today timeline, recurring schedule blocks, completion tracking, basic meal/workout logging, reviewed AI imports through MCP, an assignment Inbox from Blackboard ICS, and a controlled Google Calendar development projection.

The implementation contract is in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).

## Development quickstart

The bundled scripts create the environment, install the locked dependencies, migrate SQLite, and
start the loopback-only server:

```powershell
.\scripts\bootstrap.ps1
.\scripts\dev.ps1
```

Or run the same steps manually:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install uv
.venv\Scripts\uv sync --locked --extra dev
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m semester_ops.web.main
```

Open `http://127.0.0.1:8000`.

Run the local MCP server with:

```powershell
.venv\Scripts\python -m semester_ops.mcp_server
```

The repository's `.codex/config.toml` registers that STDIO server for Codex. After bootstrapping,
attach schedule documents and invoke `$semester-ops-import`; it retrieves the live contract and
creates a draft that can only be applied from the Imports screen. See
[`docs/import-contract.md`](docs/import-contract.md) for the boundary and review flow.

Google Calendar and Blackboard setup are optional. The application runs without either connector and reports them as unconfigured. `uv.lock` pins the complete cross-platform dependency graph.

To connect Google Calendar after adding the desktop OAuth client file, run the one-time setup
command. It opens Google's localhost consent flow, creates only `Semester Ops - Dev`, and saves
the opaque calendar ID in SQLite without printing it:

```powershell
.venv\Scripts\semester-ops-google-setup.exe
```

See [`docs/setup-google.md`](docs/setup-google.md) for the Cloud Console and safety details.
For assignments, paste Blackboard's private read-only ICS subscription in Settings; see
[`docs/setup-blackboard.md`](docs/setup-blackboard.md).

## Safety boundaries

- SQLite is the source of truth.
- AI/MCP writes only reviewable drafts.
- Google synchronization is manual and limited to an explicitly app-created `Semester Ops - Dev` calendar.
- Blackboard is read-only.
- External credentials and runtime data stay under ignored local paths.
