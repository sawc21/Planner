# Google Calendar synchronization contract

SQLite is canonical. Google Calendar is a controlled projection and a constrained source of
start/end changes for app-owned events. Synchronization runs only after the user presses
**Sync now**.

## Safety boundary

- The configured calendar ID must be the app-created `Semester Ops - Dev` secondary calendar.
- `primary` is rejected and calendar names are never resolved to IDs.
- Every projected occurrence is a separate event with a deterministic client-generated ID.
- Private properties include `appId`, `occurrenceId`, `schemaVersion`, and `revision`.
- Untagged events and events with a different occurrence identity are never changed or deleted.
- Only the parent timed block is projected. Checklists, nutrition, and workout details remain local.
- Local cancellation is soft; its owned remote projection is deleted on the next manual sync.

Google event IDs are UUIDv5-derived and use only the API's base32hex character set. Retrying an
insert therefore cannot create a second event. An ID collision with an unowned event stops with an
ownership error rather than overwriting it.

## Manual sync order

1. Refresh Blackboard independently.
2. Read every Google change page using the stored `syncToken`.
3. Filter ownership locally and update the persisted remote view.
4. Compare planner state, the last successful snapshot, and current Google state.
5. Pull non-conflicting Google-only time changes.
6. Push the canonical projection and record a new snapshot.
7. Report each connector and item result independently.

The sync token is saved only after every page succeeds. A `410 Gone` discards only the expired
token and performs one full remote rescan. It never clears SQLite or assumes a missing remote event
means the local block should be deleted.

## Three-way reconciliation matrix

| Planner since snapshot | Google since snapshot | Result |
|---|---|---|
| unchanged | unchanged | No mutation. |
| time moved | unchanged | Push planner time. |
| unchanged | time moved | Pull Google start/end as an occurrence override. |
| moved to same range | moved to same range | Converge and refresh owned metadata if needed. |
| moved | moved to different range | Create a conflict; choose **Keep planner** or **Use Google time**. |
| title/description changed | unchanged | Push canonical planner text. |
| unchanged | title/description changed | Restore canonical planner text. |
| active | remotely deleted | Recreate the deterministic owned event and report it. |
| locally canceled/disabled | active remotely | Delete only the matching owned projection. |
| any | remote event untagged | Ignore it. |
| new local occurrence | absent remotely | Insert its deterministic event. |

Conflicted occurrences produce no local-time or remote-time mutation until explicitly resolved.
Unrelated occurrences continue synchronizing.

## Remote adapter behavior

- Initial and incremental reads use identical list parameters, page completely, and request
  deletion tombstones.
- Incremental reads do not use an extended-property filter because Google restricts filters when a
  `syncToken` is present; ownership is filtered locally.
- Upsert first reads the deterministic ID, validates ownership when present, then updates or
  inserts. A retryable insert conflict is re-read and ownership-checked.
- Delete first reads and ownership-checks the event. `404` is idempotent success/no-op.
- Google API failures are explicit and item-scoped; no success-shaped fallback is returned.

## Required fake-gateway coverage

- local-only move, Google-only move, and divergent two-sided move;
- remote text repair and remote deletion recreation;
- local cancellation deletion;
- untagged-event isolation;
- two unchanged syncs with zero mutations;
- complete paging, missing final token, and expired-token full rescan;
- deterministic event identity and ownership tags.

Live smoke tests are opt-in and restricted to `Semester Ops - Dev`.
