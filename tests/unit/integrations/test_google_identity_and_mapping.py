import re
from datetime import UTC, datetime

from semester_ops.integrations.google_calendar import (
    LocalCalendarProjection,
    TimeRange,
    deterministic_event_id,
    google_event_body,
    remote_event_from_google,
)


def test_deterministic_event_id_is_stable_and_google_safe() -> None:
    first = deterministic_event_id("f6eeec86-cf59-42cb-b99c-80b36a120183")
    second = deterministic_event_id("f6eeec86-cf59-42cb-b99c-80b36a120183")

    assert first == second
    assert re.fullmatch(r"[0-9a-v]{5,1024}", first)


def test_projection_round_trips_private_ownership_tags() -> None:
    projection = LocalCalendarProjection(
        occurrence_id="occurrence-1",
        summary="Study",
        description="Semester Ops block",
        time_range=TimeRange(
            datetime(2026, 8, 24, 15, tzinfo=UTC),
            datetime(2026, 8, 24, 16, tzinfo=UTC),
        ),
        revision=3,
    )
    payload = {
        "id": deterministic_event_id(projection.occurrence_id),
        "etag": '"etag-1"',
        "status": "confirmed",
        **google_event_body(projection),
    }

    remote = remote_event_from_google(payload)

    assert remote.owned
    assert remote.occurrence_id == projection.occurrence_id
    assert remote.time_range == projection.time_range
    assert remote.tags["revision"] == "3"
