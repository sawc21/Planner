# Blackboard read-only calendar setup

V1 reads Blackboard's private ICS calendar subscription. It does not use the Blackboard REST API,
scrape pages, submit work, change due dates, or mark assignments complete in Blackboard.

## 1. Copy the private calendar URL

In modern Blackboard Learn (Ultra):

1. Open the global **Calendar**.
2. Open **Calendar Settings**.
3. Open the three-dot menu (`...`) and choose **Share Calendar**.
4. Copy the private calendar subscription link.

Do not choose **Add Calendar**; that imports another calendar into Blackboard instead of exposing
your Blackboard deadlines. On older Blackboard installations, look for **Get External Calendar
Link** under **My Blackboard > Calendar** or **My Institution > Tools > Calendar**. If neither
sharing option exists, your school may have disabled it; contact the Blackboard administrator.

Treat the URL like a password: anyone holding it may be able to read the calendar. Do not paste it
into source code, screenshots, issue reports, or logs.

## 2. Configure Semester Ops

1. Open Semester Ops **Settings** at `/settings`.
2. Paste the link into **Private ICS URL**.
3. Press **Save settings**.
4. Press **Sync now**.
5. Confirm the Blackboard connection shows a recent successful sync, then open **Assignments**.

Paste the tokenized `https://` subscription URL itself, not a `webcal://` link, a downloaded ICS
file, the Blackboard sign-in page, or the regular browser address for Calendar. The app validates
the URL when settings are saved. Changing or clearing it also clears conditional-request cache
values so the first request to the new feed cannot be mistaken for an unchanged old feed.

`SEMOPS_BLACKBOARD_ICS_URL` in `.env` is only an optional first-run seed for a new database. After
the app has created its settings record, make connection changes through **Settings**.

The feed client accepts an absolute HTTPS URL, follows redirects, uses a 15-second timeout, caps
the response at 5 MiB, and supports `ETag` and `Last-Modified` conditional requests. Error messages
never contain the private URL.

## 3. Refresh assignments

Press **Sync now** whenever you want to refresh. Blackboard refresh is an independent read-only
step:

- events are keyed by `UID` plus `RECURRENCE-ID`;
- `SEQUENCE`, `DTSTAMP`, and `LAST-MODIFIED` prevent old feed revisions from winning;
- a date-only deadline remains date-only and is treated as 11:59 PM Central only for planning;
- `STATUS:CANCELLED` marks the source assignment canceled;
- unexplained absence from a complete feed marks an assignment stale instead of deleting it;
- a partially invalid feed is reported and is not reconciled, preventing false stale records.

Assignments enter the local Inbox. They do not consume calendar time until a reviewed planning
draft creates study blocks. Local completion never writes back to Blackboard.

## Troubleshooting

- `Blackboard calendar URL must be an absolute HTTPS URL`: copy the full private subscription
  link, including `https://`, and paste it into **Private ICS URL**.
- Invalid ICS findings: download the feed once and verify it is a calendar payload rather than a
  sign-in HTML page. Do not attach the private URL to a bug report.
- Assignments are stale: Blackboard omitted them without an explicit cancellation. Review them
  locally before archiving; Semester Ops deliberately does not infer deletion.
- A course name is blank: some feeds omit course metadata. The assignment identity and deadline
  still import; course mapping can be corrected during review.

Blackboard student calendar reference:

- https://help.anthology.com/blackboard/student/en/getting-started/calendar.html
