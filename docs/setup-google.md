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
```

Apply the database migration, then run the explicit one-time setup command:

```powershell
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\semester-ops-google-setup.exe
```

The command refuses to start when the client-secret file is absent, opens a localhost browser
OAuth flow, and calls `calendars.insert` exactly once to create `Semester Ops - Dev`. It validates
that Google returned a secondary-calendar ID and persists that opaque ID directly in the singleton
`AppSettings` row. It never prints the ID, OAuth token, client secret, or their contents.

Running the command again is safe: when the database already contains the setup calendar ID, it
reports that setup is complete and does not create another calendar. Never enter `primary` or a
calendar display name as an ID.

The OAuth token and calendar ID are local runtime state. Never commit the token file or database.

## 3. Verify safely

1. Confirm Google Calendar shows a secondary calendar named `Semester Ops - Dev`.
2. Add or approve one test block in Semester Ops.
3. Press **Sync now** once.
4. Confirm one individually timed event appears on the development calendar.
5. Drag that event, press **Sync now** again, and confirm only its start/end time is proposed or
   pulled into Semester Ops.
6. Change the title in Google and sync; Semester Ops should restore its canonical title.

Never perform the smoke test against a real semester calendar. Promotion is a later, explicit
calendar-ID configuration change.

## Troubleshooting

- `An explicit app-created secondary Google calendar ID is required`: the ID is blank or set to
  `primary`.
- `Refusing to mutate ... ownership tags`: the event is not owned by Semester Ops or its
  occurrence identity does not match. The adapter intentionally stops.
- OAuth refresh failure: remove only `var/google-token.json`, confirm the client JSON, and repeat
  the explicit setup flow.
- Expired incremental token: the next manual sync performs a full remote rescan; SQLite is never
  cleared.

Official references:

- https://developers.google.com/workspace/calendar/api/auth
- https://developers.google.com/workspace/calendar/api/guides/extended-properties
- https://developers.google.com/workspace/calendar/api/guides/sync
- https://developers.google.com/workspace/calendar/api/v3/reference/events
