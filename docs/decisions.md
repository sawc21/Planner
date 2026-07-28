# Semester Ops decisions

This is the concise implementation record. The complete interview ledger and delivery plan remain in [PROJECT_PLAN.md](PROJECT_PLAN.md).

1. Semester Ops is a single-user full-day execution tracker, initially bound only to localhost.
2. The Python application is a clean replacement; the old Next.js Planner remains reference-only on `main`.
3. SQLite is authoritative. Google Calendar is a controlled projection and Blackboard ICS is read-only.
4. All imports and AI-generated schedules are reversible drafts until approved in the web UI.
5. Codex reads attached source documents and calls a local STDIO MCP server. Semester Ops has no model API key.
6. Repeating templates materialize dated occurrences. Google receives individual app-owned events, never recurring series.
7. Today is the primary surface. Week, Assignments, Imports, and Settings support it.
8. Blocks share scheduling/tracking fields and may contain checklists; meals and workouts retain typed details.
9. External synchronization is manual through `Sync now` and reports each connector independently.
10. Google writes are restricted to the explicitly app-created `Semester Ops - Dev` calendar.
11. Simultaneous local and Google time edits create an explicit user-resolved conflict.
12. Advanced groceries, Apple Health, notifications, background sync, Pi deployment, and public access are deferred.
