---
name: semester-ops-import
description: Convert attached schedules, syllabi, assignment lists, meal plans, workout plans, or change notes into safe, review-only Semester Ops import or planning drafts through the local MCP server. Use when adding or revising Semester Ops data from PDF, DOCX, text, HTML, images, or pasted notes; never use it to approve a draft or synchronize an external service.
---

# Semester Ops Import

Create a bounded draft that the user can inspect in the Semester Ops Imports screen. Treat the live MCP schema and planning context as authoritative.

## Workflow

1. Read every supplied source and retain its filename, media type, and relevant provenance. Do not copy source documents into the repository.
2. Call `get_import_schema`. Build against the returned contract; never rely on a remembered or copied schema.
3. Choose the smallest affected date range and call `get_planning_context(start_date, end_date)`. Use its current schedule revision as `base_revision`.
4. For assignment planning, also call `list_assignment_inbox` and use only returned assignment IDs.
5. Normalize explicit source facts into either:
   - `replace_scope` for a named managed dataset and bounded range; or
   - `patch` for targeted changes to known records.
6. Put every uncertain date, time, quantity, identity, or interpretation in `assumptions` or `unresolved_fields`. Do not silently invent portal times, semester bounds, nutrition macros, or assignment identities.
7. Use stable semantic `source_key` values and a stable idempotency key so retries return the same draft.
8. Call `create_import_draft` for schedule/content imports or `create_planning_draft` for proposed assignment study placement.
9. Call `get_draft` and report its review URL, blocking errors, warnings, scope, and assumptions. Stop there.

## Guardrails

- Never approve, apply, reject, delete, or synchronize through this skill.
- Never bypass a stale base revision; retrieve fresh context and create a new draft.
- Never broaden a replacement scope to solve a validation error.
- Never place private meal, checklist, or workout details in Google Calendar descriptions.
- Preserve `America/Chicago` unless the user explicitly changes the app setting.
- Prefer a blocked but honest draft over a plausible guess.

## Draft Quality

Use individual occurrences when a block must be independently movable. Use recurring templates only for genuinely repeating rules with explicit effective bounds and exceptions. Keep sleep, meals, classes, work, study, exercise, commute, chores, and recovery distinct so the full day remains trackable.
