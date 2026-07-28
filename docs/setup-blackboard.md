# Blackboard read-only calendar setup

V1 reads Blackboard's private ICS calendar subscription. It does not use the Blackboard REST API,
scrape pages, submit work, change due dates, or mark assignments complete in Blackboard.

## 1. Copy the private calendar URL

In Blackboard, open **Calendar**, choose the calendar-sharing or external-calendar option, and copy
the generated iCalendar/ICS subscription URL. The exact labels vary by Blackboard Learn version
and school configuration.

Treat the URL like a password: anyone holding it may be able to read the calendar. Do not paste it
into source code, screenshots, issue reports, or logs.

## 2. Configure Semester Ops

Copy `.env.example` to `.env` and set:

```dotenv
SEMOPS_BLACKBOARD_ICS_URL=https://your-school.example/private-calendar-token.ics
```

The feed client accepts an absolute HTTPS URL, follows redirects, uses a 15-second timeout, caps
the response at 5 MiB, and supports `ETag` and `Last-Modified` conditional requests. Error messages
never contain the private URL.

## 3. Refresh assignments

Press **Sync now**. Blackboard refresh is an independent read-only step:

- events are keyed by `UID` plus `RECURRENCE-ID`;
- `SEQUENCE`, `DTSTAMP`, and `LAST-MODIFIED` prevent old feed revisions from winning;
- a date-only deadline remains date-only and is treated as 11:59 PM Central only for planning;
- `STATUS:CANCELLED` marks the source assignment canceled;
- unexplained absence from a complete feed marks an assignment stale instead of deleting it;
- a partially invalid feed is reported and is not reconciled, preventing false stale records.

Assignments enter the local Inbox. They do not consume calendar time until a reviewed planning
draft creates study blocks. Local completion never writes back to Blackboard.

## Troubleshooting

- `URL must be an absolute HTTPS URL`: copy the full private subscription link, including `https`.
- Invalid ICS findings: download the feed once and verify it is a calendar payload rather than a
  sign-in HTML page. Do not attach the private URL to a bug report.
- Assignments are stale: Blackboard omitted them without an explicit cancellation. Review them
  locally before archiving; Semester Ops deliberately does not infer deletion.
- A course name is blank: some feeds omit course metadata. The assignment identity and deadline
  still import; course mapping can be corrected during review.

Blackboard student calendar reference:

- https://help.blackboard.com/Learn/Student/Ultra/Stay_in_the_Loop/Calendar
