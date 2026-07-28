# Import contract

Semester Ops accepts normalized JSON drafts, not raw document uploads. An MCP-capable AI host reads
the attached PDF, DOCX, text, HTML, image, or pasted notes and submits a review-only draft to the
local server. The checked-in machine contract is `schemas/import-v1.json`; the live
`get_import_schema` MCP tool is authoritative at runtime.

## Safe workflow

1. Read the source and retain filename, media type, hash, and relevant provenance.
2. Retrieve the live schema and the smallest bounded planning context.
3. Use the context's current schedule revision as `base_revision`.
4. Choose `replace_scope` only for a complete named dataset inside an explicit date range; use
   `patch` for targeted changes to known records.
5. Submit stable source keys and an idempotency key. A retry returns the existing draft.
6. Review findings and the computed diff in `/imports/{draft_id}`.
7. If facts are wrong or unresolved, answer the AI and generate a new draft. Submitted drafts remain
   immutable so their provenance and audit trail stay truthful.
8. Apply only in the browser. Application is atomic and advances the schedule revision once.

Missing semester bounds, uncertain portal times, unknown targets, stale revisions, and unbounded
replacement scopes are blocking errors. Overlaps are visible warnings that require explicit review.
The importer preserves uncertainty rather than inventing facts.

## MCP boundary

The local STDIO server exposes six operations: schema lookup, bounded planning context, assignment
Inbox lookup, import-draft creation, planning-draft creation, and draft lookup. It exposes no tool
for approval, rejection, live mutation, external synchronization, or conflict resolution.

The project-local `$semester-ops-import` skill in `.agents/skills/semester-ops-import/` follows this
contract without copying schema rules into the skill. Raw source files, submitted payloads, local
databases, connector secrets, and OAuth tokens stay outside Git.
