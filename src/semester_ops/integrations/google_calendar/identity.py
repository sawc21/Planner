from __future__ import annotations

import re
import uuid

APP_ID = "semops"
SCHEMA_VERSION = "1"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"

APP_ID_KEY = "appId"
OCCURRENCE_ID_KEY = "occurrenceId"
SCHEMA_VERSION_KEY = "schemaVersion"
REVISION_KEY = "revision"

_EVENT_ID_PATTERN = re.compile(r"^[0-9a-v]{5,1024}$")
_EVENT_NAMESPACE = uuid.UUID("7292a9b8-8cc7-5f0a-aed2-68ad51e3f094")


def deterministic_event_id(occurrence_id: str) -> str:
    """Return a retry-safe Google ID using only the documented base32hex alphabet."""

    normalized = occurrence_id.strip()
    if not normalized:
        raise ValueError("occurrence_id cannot be blank")
    event_id = f"semops{uuid.uuid5(_EVENT_NAMESPACE, normalized).hex}"
    if not _EVENT_ID_PATTERN.fullmatch(event_id):
        raise AssertionError("Generated Google event ID violates the API contract")
    return event_id


def ownership_tags(occurrence_id: str, revision: int) -> dict[str, str]:
    if revision < 0:
        raise ValueError("revision cannot be negative")
    return {
        APP_ID_KEY: APP_ID,
        OCCURRENCE_ID_KEY: occurrence_id,
        SCHEMA_VERSION_KEY: SCHEMA_VERSION,
        REVISION_KEY: str(revision),
    }


def is_owned_tags(tags: dict[str, str] | None) -> bool:
    return bool(tags and tags.get(APP_ID_KEY) == APP_ID)
