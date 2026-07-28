# Local operations

## Bootstrap

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install uv
.venv\Scripts\uv sync --locked --extra dev
Copy-Item .env.example .env
.venv\Scripts\python -m alembic upgrade head
```

Set a unique local `SEMOPS_SECRET_KEY` in `.env`. Leave connector values empty until their setup is complete.

## Run

Start the web application:

```powershell
.venv\Scripts\python -m semester_ops.web.main
```

Start the MCP server in a separate process only when testing outside Codex:

```powershell
.venv\Scripts\python -m semester_ops.mcp_server
```

The server intentionally refuses non-loopback bind addresses in v1.

## Verify

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check src tests migrations
.venv\Scripts\python -m ruff format --check src tests migrations
.venv\Scripts\python -m mypy src
```

Live Google smoke tests are never part of the default suite. Run them only after confirming the configured calendar ID belongs to `Semester Ops - Dev`.

## Back up

Stop the web and MCP processes before a manual backup. Copy the database and local configuration to a private location:

```powershell
Copy-Item var\semester-ops.db var\semester-ops.backup.db
Copy-Item .env var\env.backup
```

OAuth tokens and the Blackboard ICS URL are secrets. Do not put backups in Git or a shared folder.

## Restore

1. Stop both processes.
2. Preserve the current database under a different filename.
3. Copy the selected backup to `var\semester-ops.db`.
4. Run `.venv\Scripts\python -m alembic upgrade head`.
5. Start the web app and verify Today, Imports, and Settings before using `Sync now`.
