from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from semester_ops.integrations.google_calendar import (
    CalendarSyncSnapshot,
    LocalCalendarProjection,
    RemoteCalendarEvent,
    RemoteMutationKind,
    TimeRange,
    deterministic_event_id,
    ownership_tags,
    reconcile_calendar,
)

BASE = TimeRange(
    datetime(2026, 8, 24, 15, tzinfo=UTC),
    datetime(2026, 8, 24, 16, tzinfo=UTC),
)
LATER = TimeRange(
    datetime(2026, 8, 24, 16, tzinfo=UTC),
    datetime(2026, 8, 24, 17, tzinfo=UTC),
)
LATEST = TimeRange(
    datetime(2026, 8, 24, 17, tzinfo=UTC),
    datetime(2026, 8, 24, 18, tzinfo=UTC),
)


def local(*, time_range: TimeRange = BASE, revision: int = 1, canceled: bool = False):
    return LocalCalendarProjection(
        "occurrence-1",
        "Class",
        "Semester Ops block",
        time_range,
        revision,
        canceled,
    )


def remote(
    *,
    time_range: TimeRange = BASE,
    summary: str = "Class",
    deleted: bool = False,
    tags: dict[str, str] | None = None,
):
    return RemoteCalendarEvent(
        deterministic_event_id("occurrence-1"),
        "occurrence-1" if tags != {} else None,
        None if deleted else time_range,
        summary,
        "Semester Ops block",
        ownership_tags("occurrence-1", 1) if tags is None else tags,
        deleted,
        '"etag"',
    )


def snapshot() -> CalendarSyncSnapshot:
    return CalendarSyncSnapshot(
        "occurrence-1",
        deterministic_event_id("occurrence-1"),
        BASE,
        BASE,
        1,
        '"base"',
    )


def test_local_only_move_pushes() -> None:
    plan = reconcile_calendar((local(time_range=LATER, revision=2),), (remote(),), (snapshot(),))

    assert [mutation.kind for mutation in plan.remote_mutations] == [RemoteMutationKind.UPSERT]
    assert not plan.local_time_mutations
    assert not plan.conflicts


def test_google_only_move_pulls() -> None:
    plan = reconcile_calendar((local(),), (remote(time_range=LATER),), (snapshot(),))

    assert plan.local_time_mutations[0].remote_time_range == LATER
    assert not plan.remote_mutations
    assert not plan.conflicts


def test_two_sided_divergent_move_creates_conflict_without_writes() -> None:
    plan = reconcile_calendar(
        (local(time_range=LATER, revision=2),),
        (remote(time_range=LATEST),),
        (snapshot(),),
    )

    assert plan.conflicts[0].planner_time_range == LATER
    assert plan.conflicts[0].google_time_range == LATEST
    assert not plan.local_time_mutations
    assert not plan.remote_mutations


def test_remote_text_change_is_corrected() -> None:
    plan = reconcile_calendar((local(),), (remote(summary="Changed in Google"),), (snapshot(),))

    assert plan.remote_mutations[0].kind is RemoteMutationKind.UPSERT


def test_remote_deletion_recreates_active_projection_even_when_tombstone_lost_tags() -> None:
    tombstone = replace(
        remote(deleted=True),
        occurrence_id=None,
        tags={},
    )
    plan = reconcile_calendar((local(),), (tombstone,), (snapshot(),))

    assert plan.remote_mutations[0].kind is RemoteMutationKind.UPSERT


def test_local_cancellation_deletes_owned_projection() -> None:
    plan = reconcile_calendar((local(canceled=True),), (remote(),), (snapshot(),))

    assert plan.remote_mutations[0].kind is RemoteMutationKind.DELETE


def test_unchanged_sync_has_zero_mutations_and_ignores_unowned_events() -> None:
    unowned = RemoteCalendarEvent(
        "unowned-event",
        None,
        BASE,
        "Personal",
        None,
        {},
    )
    plan = reconcile_calendar((local(),), (remote(), unowned), (snapshot(),))

    assert not plan.remote_mutations
    assert not plan.local_time_mutations
    assert not plan.conflicts
    assert plan.unchanged_occurrence_ids == ("occurrence-1",)
    assert plan.ignored_remote_event_ids == ("unowned-event",)


def test_time_ranges_require_offsets_and_positive_duration() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        TimeRange(datetime(2026, 1, 1), datetime(2026, 1, 1, 1))
    with pytest.raises(ValueError, match="after start"):
        TimeRange(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_google_move_normalizes_subsecond_precision() -> None:
    shifted = TimeRange(
        BASE.start + timedelta(microseconds=10),
        BASE.end + timedelta(microseconds=10),
    )
    assert shifted == BASE
