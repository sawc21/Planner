# Semester Ops Project Plan

Status: Approved; localhost v1 implemented, real-data draft awaiting corrections
Prepared: 2026-07-28
Branch: `codex/semester-ops`
Worktree: `C:\Users\SawyerCawthon\source\Planner\.worktrees\semester-ops`

Sawyer approved implementation of this plan on 2026-07-28. The supplied documents completed the
AI-to-MCP review path, but their first draft remains correctly blocked until exact semester dates,
class times, Thursday timing, nutrition values, and one workout-set ambiguity are resolved.

## 1. Product outcome

Semester Ops is a single-user, localhost-only, Python-first full-day execution tracker. It opens to Today, covers the day from waking through sleep, and combines scheduling, completion tracking, assignment planning, meals, and workouts without becoming a general-purpose Life OS.

SQLite is the canonical record. Google Calendar is a controlled projection of individually materialized blocks, and Blackboard is a read-only assignment source. An AI host such as Codex reads attached source documents and submits strict JSON drafts through a local MCP server. The AI cannot apply drafts or trigger external synchronization.

The current Next.js Planner is not reused. It remains available on `main` as read-only reference material for shortcuts, useful wording, or domain ideas.

## 2. Complete question and answer record

### 2.1 Decisions established during the interview

| # | Question | Final answer | Basis |
|---|---|---|---|
| 1 | What is the product fundamentally optimizing for? | A personal full-day Semester Ops execution system, not a generic planner or SaaS product. | Resolved by the later full-day tracking direction. |
| 2 | Should the existing Planner application be reused? | No. Start clean on `codex/semester-ops`; consult the old code only when it provides a shortcut. | User direction. |
| 3 | Should v1 be a Python-first local application? | Yes. Use a modular FastAPI application backed by SQLite. | User direction and accepted recommendation. |
| 4 | Should v1 be localhost-only? | Yes. Bind to loopback with no application login, hosting, Tailscale, or Pi service setup yet. | Confirmed. |
| 5 | Which system is authoritative? | SQLite is authoritative. Google Calendar is a projection plus a constrained source of user-made time changes. | Confirmed. |
| 6 | What may Google Calendar change in SQLite? | Only start and end times of app-owned events. Remote title, description, deletion, and unowned events do not alter the canonical schedule. | Confirmed. |
| 7 | Should document imports apply immediately? | No. Every import becomes a diff-style draft that requires explicit review and approval. | Confirmed. |
| 8 | Should FastAPI call an AI model to parse documents? | No. The AI host reads the attachment and creates the normalized JSON. Semester Ops holds no model API key. | User correction. |
| 9 | Where are source documents uploaded? | Attach PDF, DOCX, text, or HTML files to a local MCP-capable AI host such as Codex. The planner receives only validated JSON and provenance metadata. | Confirmed. |
| 10 | Which side is the MCP server? | Semester Ops is the MCP server; Codex is the host/client that calls its tools. | Accepted recommendation. |
| 11 | How are repeating schedules represented? | A recurring template generates materialized dated occurrences. A one-date change becomes an occurrence override. | Confirmed. |
| 12 | Should Google receive recurring series? | No. Each materialized occurrence is a separate Google event with a stable occurrence identity. | Confirmed. |
| 13 | What must the first release contain? | A thin but complete full-day tracker: scheduling, statuses, checklists, basic meals/workouts, reviewed imports, Google dev sync, and Blackboard Inbox. | Reconciles the narrow vertical slice with the later full-day requirement. |
| 14 | Which tracking states exist? | `planned`, `in_progress`, `completed`, `skipped`, and derived `missed`. Cancellation is a scheduling lifecycle state, not a completion outcome. | Confirmed tracking behavior, normalized recommendation. |
| 15 | What actual execution data is retained? | Actual start/end, notes, and quick actions to start, complete, skip, and reopen a block. | Confirmed. |
| 16 | Which Google calendar is used while building? | Only `Semester Ops - Dev`. Never write to the primary calendar. | Confirmed. |
| 17 | How is a production calendar introduced? | Later, by an explicit configuration change after dev reconciliation passes. Never guess a calendar by display name. | Confirmed. |
| 18 | Which import modes are required? | `replace_scope` for a complete bounded desired state and `patch` for additions, edits, moves, and cancellations. | Confirmed. |
| 19 | How do overlaps behave? | They are visible, rearrangeable warnings that can be approved deliberately. Invalid ranges, unknown targets, or unbounded replacements are hard errors. | Confirmed. |
| 20 | What is the core timeline object? | A shared schedule block for waking, sleep, commute, class, work, study, meals, workouts, chores, appointments, free time, and custom categories. | Confirmed. |
| 21 | How is specialized tracking represented? | Every block may have generic checklist items; meals have typed food entries and workouts have typed exercises and sets. | Confirmed. |
| 22 | What is the main UI? | A mobile-friendly Today timeline. Week, Assignments, Imports, and Settings are secondary screens. | Confirmed. |
| 23 | Can Blackboard assignments be connected? | Yes, through a private read-only ICS subscription in v1. The REST API and all Blackboard writeback are deferred. | Confirmed. |
| 24 | How do Blackboard assignments enter the plan? | They enter an Inbox with course, title, due date, link, and source state. They consume no schedule time until a study draft is approved. | Confirmed. |
| 25 | Who proposes assignment study time? | The AI reads schedule and assignment context through MCP, submits a draft, and FastAPI validates it. Manual move/edit remains available. | Confirmed. |
| 26 | How is movability expressed? | Every block is `fixed`, `flexible`, or `optional`. AI cannot move fixed blocks, may propose moves for flexible blocks, and may shrink/drop optional blocks. | Confirmed. |
| 27 | How are the supplied schedule and dashboard files used? | They are the first real AI-to-MCP reviewed import, not hardcoded seed fixtures. | Recommendation delegated by the user. |
| 28 | How are meal totals calculated? | Retain planned and consumed quantities. Consumed calorie/protein totals include checked food items using their adjusted consumed quantities. | Confirmed. |
| 29 | How detailed are v1 workouts? | Exercises, planned sets, rep ranges, optional target weight, completed sets, actual reps/weight, and actual duration. | Confirmed. |
| 30 | Do child items complete their parent? | Completing all required actionable children completes the block. Optional items do not block completion, and manual block completion never fakes child completion. | Confirmed. |
| 31 | Which time zone is used? | Central Time, stored as `America/Chicago`; instants are persisted in UTC and rendered with daylight-saving rules. | User direction. |
| 32 | Is synchronization automatic? | No. v1 uses a visible manual `Sync now` action only. | Confirmed. |

### 2.2 Remaining questions resolved with the requested recommendations

The user asked that all remaining branches be resolved using the recommended answer. These defaults
were accepted with the implementation approval and are part of the v1 contract.

| # | Question | Recommended answer applied |
|---|---|---|
| 33 | What happens when the same block moved locally and in Google after the last sync? | Create an explicit conflict with `Keep planner` and `Use Google time`; continue synchronizing unrelated events. |
| 34 | What is the working product name? | `Semester Ops`. Use `semester_ops` for the Python package and `semops` for internal identifiers. |
| 35 | What project shape should replace Next.js? | A Python modular monolith with separate web and STDIO MCP entry points sharing the same application services. |
| 36 | Which backend libraries should be used? | FastAPI, Pydantic Settings, synchronous SQLAlchemy 2, Alembic, and SQLite. Avoid async database complexity in this single-user app. |
| 37 | How should Python dependencies be managed? | Use `pyproject.toml` and a reproducible lock file. Prefer `uv` for speed while retaining standard virtualenv/pip-compatible installation instructions. Support Python 3.12 or newer and verify against the actual development interpreter. |
| 38 | Which frontend architecture should be used? | Jinja templates, purposeful CSS, and minimal local vanilla JavaScript. Ship precise move/edit controls first; drag/resize can follow without changing the server contract. No SPA or required Node runtime. |
| 39 | Which MCP transport should v1 use? | Local STDIO launched by Codex from project configuration. It requires no extra port or authentication. Streamable HTTP is deferred to Pi/remote access. |
| 40 | What can MCP mutate? | MCP may read planning context and create reversible drafts only. It cannot approve/apply, delete live data, resolve sync conflicts, or trigger Google/Blackboard synchronization. |
| 41 | Are raw source documents stored by Semester Ops? | No. Store the submitted JSON, source filename/type/hash, assumptions, and audit metadata; leave the original attachment in the AI host. |
| 42 | How many semesters are supported? | The schema supports many semesters, but v1 exposes one active semester at a time. Applying a semester import requires exact start/end dates. |
| 43 | What if a source document has approximate or missing dates/times? | Preserve them as unresolved draft findings and block approval until exact values are supplied. Never guess portal times or semester bounds. |
| 44 | When does a logical day begin? | Default to a configurable 4:00 AM Central operational-day boundary so post-midnight activity stays with the intended day. |
| 45 | When does a planned block become missed? | Derive `missed` on page load/action 30 minutes after its planned end when it is still `planned` and requires completion. Allow retroactive correction. |
| 46 | Does `fixed` prevent the user from moving a block? | No. It prevents automated movement only. The user retains explicit manual control in the planner or Google. |
| 47 | What additional scheduling constraints support AI planning? | Store priority, preferred/minimum duration, earliest start, latest end, and whether the block may split. Empty time remains visible and valid. |
| 48 | What happens when a template changes? | Regenerate only unmodified future occurrences within an explicit scope. Preserve overrides, in-progress/completed history, and past occurrences. |
| 49 | How safe is `replace_scope`? | It affects only its named managed dataset and bounded date range. It cannot erase manual blocks, Blackboard records, another import set, or out-of-scope dates. |
| 50 | How are MCP retries and stale plans handled? | Require schema version, idempotency key, bounded scope, and base schedule revision. A duplicate returns its existing draft; a stale base revision blocks approval. |
| 51 | How is the dev Google calendar created? | During explicit setup, the app creates `Semester Ops - Dev`, records the returned calendar ID, and subsequently addresses only that ID. |
| 52 | Which Google OAuth scope is preferred? | Request the narrow `calendar.app.created` scope so the app can create and manage only secondary calendars it created and their events. |
| 53 | How are Google events identified? | Use one deterministic client-generated event ID per block plus short private extended properties containing app ID, occurrence ID, schema version, and revision. |
| 54 | Which block details go to Google? | Only the timed parent block and a concise planner-owned description. Checklist, meal, and workout details remain in Semester Ops. Each block can explicitly disable calendar projection. |
| 55 | What happens to remote title/description edits or remote deletion? | Planner-owned text is restored on sync. A remotely deleted active event is recreated and reported. Unowned events are ignored. |
| 56 | What happens when a local block is canceled? | Soft-cancel it with audit history and delete its owned Google projection during the next sync. |
| 57 | What exactly does `Sync now` do? | Refresh Blackboard, pull Google changes, perform three-way reconciliation, then push the canonical projection. Return independent results for each connector; one failure is not reported as total success and does not roll back a successful independent connector. |
| 58 | How is incremental Google sync implemented? | Store `syncToken`, page completely, filter ownership locally, and recover from `410 Gone` with a full remote rescan that never clears canonical SQLite data. |
| 59 | What happens when a Blackboard item disappears? | Explicit ICS cancellation marks it canceled; unexplained absence marks it stale rather than deleting it or its study blocks. |
| 60 | How are Blackboard all-day due dates treated? | Preserve date-only semantics. For planning validation, interpret the usable deadline as 11:59 PM Central without rewriting the source value. |
| 61 | Does completing an assignment write back to Blackboard? | No. Completion/archive state is local. A changed Blackboard due date flags linked study blocks for replanning rather than silently moving them. |
| 62 | Are every minute and every block required to be tracked? | No. Full-day means the complete intended day can be represented; intentional empty windows and non-trackable free-time blocks remain valid. |
| 63 | Which nutrition functionality is in v1? | Planned and consumed calories/protein, quantities, daily targets, and totals. Macro optimization, micronutrients, and recipe intelligence are deferred. |
| 64 | Which grocery functionality is in v1? | None beyond preserving source/import data. A dedicated grocery checklist, inventory, recurring-shop logic, and recipe aggregation follow v1. |
| 65 | How is Apple Health handled? | Define a future activity-import adapter, but defer implementation. HealthKit requires an authorized Apple-platform companion or export bridge. |
| 66 | Are notifications or background workers included? | No. Missed-state derivation and all external refreshes happen on user interaction in v1. |
| 67 | Is the localhost UI still responsive? | Yes. Build Today and Week for desktop and narrow mobile viewports from the start, with keyboard-accessible forms as a fallback to dragging. |
| 68 | How are localhost mutations protected without login? | Bind to `127.0.0.1`, validate Host/Origin, use CSRF tokens on browser mutations, and never enable permissive CORS. |
| 69 | Where are secrets and runtime data kept? | Ignored local files under `var/` or configured paths. Never commit OAuth client files, refresh tokens, the Blackboard ICS URL, databases, or imported source documents. |
| 70 | How are failures and history exposed? | Persist sync runs, conflicts, import approvals, and key schedule mutations. Show actionable errors and last-success state; never swallow an exception or return a success-shaped fallback. |
| 71 | Is a `memory.md` the source of truth? | No. Use versioned decision, schema, sync, and setup documents. Add a project-local Semester Ops import skill only after the JSON contract stabilizes. |
| 72 | What is the commit strategy after approval? | Small vertical-slice commits on `codex/semester-ops`; never mix or copy the dirty `main` worktree changes. No commit is made during planning. |

## 3. Scope boundary

### Included in v1

- One active semester in Central Time.
- Today full-day timeline and Week view.
- Recurring templates, materialized occurrences, one-off blocks, and occurrence overrides.
- Fixed/flexible/optional constraints, priorities, time windows, and overlap warnings.
- Planned/in-progress/completed/skipped/missed tracking, actual timing, and notes.
- Required/optional checklist items.
- Basic typed meal tracking with planned/consumed calories and protein.
- Basic typed workout tracking with exercises, sets, reps, weight, and actual duration.
- Versioned `replace_scope` and `patch` drafts with review/edit/apply.
- Local STDIO MCP tools for context and draft creation.
- Manual, isolated Google Calendar synchronization to `Semester Ops - Dev`.
- Read-only Blackboard ICS refresh, assignment Inbox, and reviewable AI study plans.
- The two supplied source files as the first real import acceptance case.

### Explicitly deferred

- Production Google calendar promotion.
- Pi deployment, systemd, Tailscale, hosted access, authentication, or multiple users.
- Background sync, reminders, push notifications, or a worker process.
- Direct file upload or an embedded OpenAI/API-model integration.
- Blackboard REST API, scraping, assignment submission, or writeback.
- Apple Health/HealthKit companion application.
- Grocery/inventory UI, recipe database, barcode scanning, or recurring-shop automation.
- Macro slider/optimizer, micronutrients, advanced nutrition analysis, and health advice.
- Workout programming, progression analytics, charts, wearable sync, or social features.
- A generic Life OS or unrelated Planner modules.

## 4. Architecture

```text
Browser -> FastAPI + Jinja + vanilla JS ----\
                                        -> application services -> SQLAlchemy -> SQLite
Codex   -> local STDIO MCP -----------/
                                                   |
                                                   +-> Google Calendar adapter
                                                   +-> Blackboard ICS adapter
```

The web layer and MCP layer are adapters. They do not contain duplicate business rules. All draft validation, recurrence, tracking, and reconciliation behavior lives in shared domain/application services.

Recommended source layout:

```text
src/semester_ops/
  domain/
  application/
  db/
  integrations/google_calendar/
  integrations/blackboard/
  web/
  mcp_server.py
templates/
static/
migrations/
schemas/
tests/unit/
tests/integration/
tests/e2e/
docs/
var/                  # ignored runtime state
```

SQLite enables foreign keys, WAL mode, and a busy timeout because the web and MCP entry points can write concurrently. Business identifiers use UUIDs. Bulk draft application is transactional, and records requiring history use soft cancellation rather than destructive deletion.

## 5. Domain model

| Model | Purpose |
|---|---|
| `Semester` | Name, exact bounds, IANA time zone, and active state. |
| `BlockTemplate` | Weekly wall-clock recurrence, effective dates, category, flexibility, priority, time-window constraints, and managed source. |
| `BlockOccurrence` | Stable UUID, optional template, planned/actual UTC range, status, notes, override/revision state, tracking requirement, and calendar-projection flag. |
| `ChecklistItem` | Ordered required/optional action with completion timestamp. |
| `MealItem` | Food, unit, planned/consumed quantity, calories, protein, and completion state. Numeric nutrition values use decimal-safe storage. |
| `WorkoutExercise` / `WorkoutSet` | Ordered exercise targets and actual set/reps/weight/completion data. |
| `Course` / `Assignment` | Blackboard UID, course, source date precision, due value, URL, source state, estimated effort, and Inbox state. |
| `AssignmentBlockLink` | Links assignments to one or more study occurrences. |
| `ImportDraft` / `ImportChange` / `ImportIssue` | Immutable submitted payload, computed diff, findings, idempotency, base revision, and approval state. |
| `CalendarEventLink` | Occurrence/event IDs, calendar ID, ETag, last-synced local revision, and last-synced projection snapshot. |
| `ExternalSourceState` | Blackboard fetch metadata and Google incremental-sync token. |
| `SyncRun` / `SyncConflict` | Per-connector results, item failures, and three-way conflict values/resolution. |
| `AuditEvent` | Applied imports, status changes, schedule edits, cancellations, and conflict resolutions. |
| `Settings` | Active semester, Central Time, operational-day boundary, missed grace, units, and dev calendar ID. |

Template rules retain local wall-clock values in `America/Chicago`; generated occurrences store UTC instants. This avoids daylight-saving drift while retaining correct historical timestamps.

## 6. MCP v1 contract

MCP uses the official Python SDK over STDIO. Protocol logs go to stderr because stdout is reserved for MCP messages.

| Tool/resource | Behavior |
|---|---|
| `get_import_schema()` | Returns the supported schema version, definitions, examples, and validation rules. |
| `get_planning_context(start_date, end_date)` | Returns stable IDs, current revision, fixed/flexible/optional blocks, free windows, constraints, and open assignments. |
| `list_assignment_inbox(status)` | Returns read-only Blackboard assignment records. |
| `create_import_draft(payload, idempotency_key, base_revision)` | Creates a validated `replace_scope` or `patch` draft and returns its review URL. |
| `create_planning_draft(payload, idempotency_key, base_revision)` | Creates a study-placement proposal through the same diff/validation engine. |
| `get_draft(draft_id)` | Returns validation findings, diff summary, current state, and review URL. |

There are deliberately no MCP tools for approval, direct mutation, deletion, conflict resolution, or external synchronization in v1.

Every submitted draft includes:

- `schema_version`
- `mode`
- `managed_dataset`
- bounded semester/date scope
- `idempotency_key`
- `base_revision`
- source/provenance metadata
- templates, occurrences, or patch operations
- assumptions and unresolved fields

## 7. Synchronization contracts

### Google Calendar

- Request the narrow `calendar.app.created` OAuth scope.
- Create and record the ID of `Semester Ops - Dev` during explicit setup.
- Create one deterministic, individually tagged Google event for each projected occurrence.
- Never use `primary`, search by name, or touch an untagged event.
- Pull only start/end changes from owned events.
- Use the last-synced snapshot for three-way conflict detection.
- Restore planner-owned title/description and recreate remotely deleted active events.
- Delete the projection of a locally canceled occurrence.
- Store and page through incremental `syncToken` results; on `410 Gone`, rebuild the remote snapshot without clearing SQLite.
- Run only when the user presses `Sync now`.

Google's current API supports private extended event properties and incremental sync tokens. Incremental requests cannot also filter by private extended property, so the dedicated calendar is read and ownership is filtered locally.

### Blackboard

- Store the private ICS URL only in ignored configuration.
- Fetch on `Sync now` with timeouts, response-size limits, ETag/Last-Modified support, and no logging of the URL.
- Upsert by source plus `UID` and `RECURRENCE-ID`; preserve `SEQUENCE`, `DTSTAMP`, and `LAST-MODIFIED`.
- Treat explicit `STATUS:CANCELLED` as cancellation; treat unexplained absence as stale.
- Preserve date-only deadlines as date-only.
- Never write to Blackboard.
- Assignment planning creates separate schedule occurrences through a reviewed draft.

## 8. User experience

### Today

- Opens by default and presents the operational day from wake to sleep.
- Shows current/next blocks, empty windows, status, checklist progress, meal totals, and workout progress.
- Offers start, complete, skip, reopen, edit, and exact-time actions.
- Supports 15-minute move controls and exact-time keyboard/mobile forms; drag/resize is an optional later enhancement.
- Shows planned versus consumed calories/protein and planned versus actual workout progress.
- Shows unsynced state, last sync result, and actionable conflicts.

### Week

- Compact weekly schedule with category and flexibility cues.
- Manual rearrangement and precise edit controls.
- Conflict markers and assignment deadlines.

### Assignments

- Blackboard Inbox states: inbox, planned, completed, ignored, stale, and canceled.
- Course, title, due value, source link, estimated effort, and linked study blocks.
- AI planning creates a draft rather than moving blocks directly.

### Imports

- Diff sections for additions, changes, cancellations, assumptions, warnings, and errors.
- Keep submitted drafts immutable; correct source facts through a newly generated draft, then make any personal timing adjustment with the precise block editor after approval.
- Atomic apply or no apply.
- Visible provenance and audit history.

### Settings

- Active semester and exact dates.
- Central Time, 4:00 AM day boundary, 30-minute missed grace, and units.
- Google OAuth/dev-calendar status and Blackboard feed status.
- Manual `Sync now` with independent connector results.

## 9. Delivery plan

### Phase 0 - Approved foundation

1. Receive explicit approval of this plan.
2. Remove the old Next.js application only from `codex/semester-ops`.
3. Create the Python package, configuration, dependency lock, lint/type/test setup, and ignored runtime paths.
4. Add FastAPI startup, Alembic, SQLite configuration, and shared ports/adapters.
5. Preserve the versioned decision and schema documents.

Verification:

- Fresh install succeeds from documented commands.
- `alembic upgrade head` succeeds against an empty database.
- The app binds only to `127.0.0.1`.
- The original dirty `main` worktree remains unchanged.

### Phase 1 - Walking vertical slice

Build one complete path before broad scaffolding:

1. One recurring template creates one materialized occurrence.
2. MCP creates one idempotent reviewable draft.
3. Imports displays and approves it transactionally.
4. Today displays and tracks the block.
5. `Sync now` pushes it through a fake Google adapter.
6. A fake remote time move reconciles back as an override.

Verification:

- One integration test covers MCP -> draft -> approval -> SQLite -> Today -> fake Google -> pullback.
- Retrying the same import or sync creates no duplicate draft, occurrence, or event.
- A reconciliation matrix test exists before live Google work begins.

### Phase 2 - First usable full-day tracker

1. Complete Today and Week.
2. Add categories, constraints, statuses, actual timing, notes, conflicts, and precise rearrangement.
3. Add recurring-series scopes and override preservation.
4. Add required/optional checklist items and parent completion.
5. Add meal items and planned/consumed calorie/protein totals.
6. Add workout exercises, sets, actual values, and duration.

Verification:

- Fake-clock tests cover status transitions and 30-minute missed grace.
- Recurrence covers semester bounds, exclusions, one-date overrides, DST, and cross-midnight blocks.
- Nutrition totals use only checked/adjusted quantities.
- Workout progress persists across restart.
- Browser tests cover desktop and mobile Today views plus non-drag editing.

This phase is the first genuinely useful local tracker and should be usable before waiting for live integrations.

### Phase 3 - Safe import and MCP loop

1. Finalize schema-v1 `replace_scope` and `patch` contracts.
2. Add complete validation, diff, edit, warning override, and atomic apply behavior.
3. Add idempotency and base-revision protection.
4. Implement the complete read/draft-only MCP surface through shared application services.
5. Register project-local Codex MCP configuration.

Verification:

- Invalid drafts cannot partially apply.
- Replacement cannot affect another source or out-of-scope data.
- Unknown patch targets and unresolved critical fields block approval.
- Duplicate idempotency keys return the existing draft.
- Real MCP tool round trips match the checked-in JSON Schema.

### Phase 4 - Google Calendar dev projection

1. Add OAuth setup and create/bind `Semester Ops - Dev`.
2. Add deterministic event identity and private ownership tags.
3. Implement bounded, retry-safe push and incremental pull.
4. Implement three-way reconciliation, partial failure reporting, and conflict resolution.
5. Keep all sync user-triggered.

Required reconciliation tests:

- Local-only move pushes.
- Google-only move pulls.
- Two-sided move creates a conflict.
- Remote text changes are corrected.
- Remote deletion recreates an active occurrence.
- Local cancellation removes its projection.
- Untagged and primary-calendar events remain untouched.
- Two unchanged syncs cause zero mutations.
- Partial failure retries safely.
- Expired sync token triggers a safe remote rescan.

Live smoke testing is opt-in and restricted to `Semester Ops - Dev`.

### Phase 5 - Blackboard Inbox and AI planning

1. Add private ICS configuration and manual refresh.
2. Reconcile assignments using stable ICS identity and source revision fields.
3. Add Inbox states and due-date change warnings.
4. Expose assignments and free-window context to MCP.
5. Accept AI study proposals through the standard draft review flow.

Verification:

- Reimporting the same feed is idempotent.
- Due-date and sequence changes update the source assignment.
- Explicit cancellation and unexplained absence behave differently.
- A study proposal cannot move a fixed block or silently schedule after its deadline.

### Phase 6 - Real-data acceptance and hardening

1. Attach `semester-ops-dashboard_1.html` and `Fresh_7-Day_Nutrition_Fitness_and_Weekly_Schedule.txt` to Codex.
2. Generate one schema-v1 MCP draft with explicit assumptions and unresolved portal times.
3. Review, correct, and approve the draft.
4. Verify Today, Week, meals, workouts, and assignments.
5. Run `Sync now` against only `Semester Ops - Dev`.
6. Restart both entry points and verify persistent, duplicate-free state.
7. Finish setup, backup, troubleshooting, and privacy documentation.

## 10. Definition of done

V1 is complete only when all of the following are true:

- The old dirty Planner worktree remains untouched and the new branch contains a clean Python replacement.
- A documented fresh install, empty-database migration, start, and restart all work.
- Today supports a full wake-to-sleep plan with empty windows, tracking states, actual times, notes, and rearrangement.
- Recurrence and overrides remain correct across Central-Time daylight-saving transitions.
- Checklists, consumed nutrition totals, and workout set/duration tracking follow the agreed rules.
- AI can create both draft modes through MCP but cannot bypass review or invoke live external writes.
- Applying a draft is atomic, idempotent, revision-safe, and bounded to its declared managed scope.
- Google sync touches only app-owned events on the configured dev calendar and passes the complete reconciliation matrix.
- Blackboard refresh is read-only and idempotent, and assignment planning uses reviewed drafts.
- Both supplied files pass through the actual AI -> MCP -> review -> apply workflow.
- Errors are explicit and actionable; no failed operation is represented as success.
- Unit, integration, migration, contract, and browser tests pass.
- No database, source attachment, OAuth credential/token, or private ICS URL is committed.

## 11. Documentation and future skill

The repository should eventually contain:

- `docs/decisions.md` derived from this approved ledger.
- `docs/import-contract.md` plus a machine-readable JSON Schema.
- `docs/google-sync-contract.md` with the reconciliation matrix.
- `docs/setup-google.md` and `docs/setup-blackboard.md`.
- `docs/operations.md` for backup, restore, and later Pi deployment.

After the import schema stabilizes, create a project-local `semester-ops-import` skill that teaches Codex how to read schedule documents, retrieve the current schema/context, state assumptions, and submit safe drafts. The skill must call the MCP tools and must not duplicate the JSON schema or business rules.

## 12. Authoritative external references

- OpenAI/Codex MCP host-client-server model and supported transports: https://learn.chatgpt.com/docs/extend/mcp
- Official Python MCP SDK: https://github.com/modelcontextprotocol/python-sdk
- Google Calendar OAuth scopes: https://developers.google.com/workspace/calendar/api/auth
- Google event private extended properties: https://developers.google.com/workspace/calendar/api/guides/extended-properties
- Google incremental synchronization: https://developers.google.com/workspace/calendar/api/guides/sync
- Google Events.list sync restrictions: https://developers.google.com/workspace/calendar/api/v3/reference/events/list
- Google OAuth Testing refresh-token expiration: https://support.google.com/cloud/answer/15549945
- Blackboard student calendar and ICS sharing: https://help.blackboard.com/Learn/Student/Ultra/Stay_in_the_Loop/Calendar
- Blackboard REST integration administrator requirements: https://docs.anthology.com/docs/blackboard/rest-apis/getting-started/rest-and-learn
- Apple HealthKit platform and authorization model: https://developer.apple.com/documentation/healthkit

## 13. Approval gate

Approval of this document authorized implementation on `codex/semester-ops` in the phase order above. It does not authorize production-calendar writes, Pi deployment, public exposure, Blackboard REST access, or Apple Health work.
