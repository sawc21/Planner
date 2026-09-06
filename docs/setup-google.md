# Google Calendar development setup

Semester Ops uses one app-created secondary calendar named `Semester Ops - Dev`. It never
targets `primary`, searches calendars by display name, or writes to an event without matching
private ownership tags.

Live setup is optional. All automated tests use a fake gateway and make no Google requests.

## 1. Create the OAuth client

1. Create or choose a personal project in Google Cloud Console.
2. Enable the Google Calendar API.
3. Configure the OAuth consent screen for the Google account that will own the calendar.
4. Create an OAuth client with application type **Desktop app**.
5. Download the client JSON to `var/google-client-secret.json`.

Do not commit the client JSON. Semester Ops requests only:

```text
https://www.googleapis.com/auth/calendar.app.created
```

That scope allows the app to create secondary calendars and manage events on calendars the app
created. It does not grant access to the primary calendar.

If an external OAuth project remains in Google's **Testing** publishing state, refresh tokens for
sensitive scopes can expire after seven days. For a long-lived personal connection, review the
current consent-screen policy and move the project to **In production** when appropriate. A
single-user unverified-app warning is expected for a personal project.

## 2. Configure local paths

Copy `.env.example` to `.env` and set:

```dotenv
SEMOPS_GOOGLE_CLIENT_SECRET_FILE=var/google-client-secret.json
SEMOPS_GOOGLE_TOKEN_FILE=var/google-token.json
SEMOPS_GOOGLE_INITIAL_SYNC_WRITE_LIMIT=1
SEMOPS_GOOGLE_SYNC_WRITE_LIMIT=50
```

The first successful Google synchronization writes at most one event. After that smoke event is
verified, each press of **Sync now** writes at most 50 remote changes. Keep the initial limit at
`1`; the normal limit may be reduced, but must stay between `1` and `250` and cannot be smaller
than the initial limit.

Apply the database migration, then run the explicit one-time setup command:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\semester-ops-google-setup.exe
```

The command refuses to start when the client-secret file is absent, opens a localhost browser
OAuth flow, and calls `calendars.insert` exactly once to create `Semester Ops - Dev`. It validates
that Google returned a secondary-calendar ID and persists that opaque ID directly in the singleton
`AppSettings` row. It never prints the ID, OAuth token, client secret, or their contents.

Running the command again is safe: when the database already contains the setup calendar ID, it
reports that setup is complete and does not create another calendar. Never enter `primary` or a
calendar display name as an ID.

If authorization expires or is revoked, reauthorize explicitly:

```powershell
.\.venv\Scripts\semester-ops-google-setup.exe --reauthorize
```

Reauthorization replaces the local OAuth token only after the browser flow succeeds. It preserves
the existing opaque calendar ID and never calls `calendars.insert`, so it cannot create a duplicate
development calendar. Do not delete the token first.

The OAuth token and calendar ID are local runtime state. Never commit the token file or database.

## 3. Verify safely

1. Confirm Google Calendar shows a secondary calendar named `Semester Ops - Dev`.
2. Add or approve at least one test block in Semester Ops.
3. Press **Sync now** once. The one-event safety limit applies automatically.
4. Confirm one individually timed event appears on the development calendar.
5. Return to Settings. If more changes remain, the Google card shows the latest attempted count
   and remaining count. Each additional **Sync now** processes the next bounded batch.
6. Drag the smoke-test event, press **Sync now** again, and confirm only its start/end time is
   pulled into Semester Ops.
7. Change the title in Google and sync; Semester Ops should restore its canonical title.

The app deliberately retains the prior incremental token until all bounded batches finish. A
repeated button press therefore continues the same safe reconciliation without duplicating events.

Never perform the smoke test against a real semester calendar. Promotion is a later, explicit
calendar-ID configuration change.

## Troubleshooting

- `An explicit app-created secondary Google calendar ID is required`: the ID is blank or set to
  `primary`.
- `Refusing to mutate ... ownership tags`: the event is not owned by Semester Ops or its
  occurrence identity does not match. The adapter intentionally stops.
- `oauth_required` or `oauth_refresh_failed`: confirm the client JSON, then run setup with
  `--reauthorize`. The saved calendar ID remains unchanged.
- `calendar_permission_denied`: make sure the signed-in Google account owns the app-created
  development calendar, then reauthorize with that account.
- `calendar_not_found`: stop synchronizing. The stored development calendar is unavailable and
  requires an explicit rebuild; the app will not silently switch calendars or use `primary`.
- `calendar_rate_limited`: wait a few minutes, then press **Sync now** again. Completed items are
  retained and deterministic event IDs prevent duplicates.
- `calendar_temporarily_unavailable`: check the network connection and retry later.
- A Settings card labeled **Sync in progress** is not an error. Press **Sync now** again to process
  the remaining bounded batch.
- Expired incremental token: the next manual sync performs a full remote rescan; SQLite is never
  cleared.

Official references:

- https://developers.google.com/workspace/calendar/api/auth
- https://developers.google.com/workspace/calendar/api/guides/extended-properties
- https://developers.google.com/workspace/calendar/api/guides/sync
- https://developers.google.com/workspace/calendar/api/v3/reference/events
