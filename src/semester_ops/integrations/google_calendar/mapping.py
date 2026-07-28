from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from semester_ops.integrations.google_calendar.identity import (
    OCCURRENCE_ID_KEY,
    deterministic_event_id,
    ownership_tags,
)
from semester_ops.integrations.google_calendar.models import (
    LocalCalendarProjection,
    RemoteCalendarEvent,
    TimeRange,
    normalized_instant,
)


class InvalidGoogleEvent(ValueError):
    pass


def google_event_body(projection: LocalCalendarProjection) -> dict[str, Any]:
    """Map only the parent block; child tracking details remain local."""

    return {
        "summary": projection.summary,
        "description": projection.description,
        "start": {"dateTime": _rfc3339(projection.time_range.start)},
        "end": {"dateTime": _rfc3339(projection.time_range.end)},
        "extendedProperties": {
            "private": ownership_tags(projection.occurrence_id, projection.revision)
        },
    }


def remote_event_from_google(payload: Mapping[str, Any]) -> RemoteCalendarEvent:
    event_id = _required_text(payload.get("id"), "id")
    status = str(payload.get("status") or "confirmed")
    tags = _private_tags(payload)
    deleted = status == "cancelled"
    time_range: TimeRange | None = None
    if not deleted:
        start_value = _date_time(payload.get("start"))
        end_value = _date_time(payload.get("end"))
        if start_value is not None and end_value is not None:
            time_range = TimeRange(start_value, end_value)
        elif tags.get("appId") == "semops":
            raise InvalidGoogleEvent("App-owned event must have dateTime start and end")

    return RemoteCalendarEvent(
        event_id=event_id,
        occurrence_id=tags.get(OCCURRENCE_ID_KEY),
        time_range=time_range,
        summary=_optional_text(payload.get("summary")),
        description=_optional_text(payload.get("description")),
        tags=tags,
        deleted=deleted,
        etag=_optional_text(payload.get("etag")),
    )


def remote_matches_projection(
    remote: RemoteCalendarEvent,
    projection: LocalCalendarProjection,
) -> bool:
    if remote.deleted or remote.time_range is None:
        return False
    return (
        remote.event_id == deterministic_event_id(projection.occurrence_id)
        and remote.summary == projection.summary
        and (remote.description or "") == projection.description
        and remote.time_range == projection.time_range
        and dict(remote.tags) == ownership_tags(projection.occurrence_id, projection.revision)
    )


def _private_tags(payload: Mapping[str, Any]) -> dict[str, str]:
    extended = payload.get("extendedProperties")
    if not isinstance(extended, Mapping):
        return {}
    private = extended.get("private")
    if not isinstance(private, Mapping):
        return {}
    return {str(key): str(value) for key, value in private.items()}


def _date_time(value: object) -> datetime | None:
    if not isinstance(value, Mapping):
        return None
    raw = value.get("dateTime")
    if not isinstance(raw, str):
        return None
    try:
        return normalized_instant(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError as exc:
        raise InvalidGoogleEvent("Google event contains an invalid RFC3339 timestamp") from exc


def _rfc3339(value: datetime) -> str:
    return normalized_instant(value).isoformat().replace("+00:00", "Z")


def _required_text(value: object, field: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise InvalidGoogleEvent(f"Google event is missing {field}")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
