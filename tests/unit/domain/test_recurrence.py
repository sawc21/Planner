from datetime import UTC, date, time

import pytest

from semester_ops.domain.recurrence import WeeklyRecurrence, materialize_weekly
from semester_ops.domain.time import InvalidLocalTimeError, operational_day_bounds


def test_weekly_recurrence_preserves_central_wall_time_across_dst() -> None:
    occurrences = materialize_weekly(
        WeeklyRecurrence(
            effective_start=date(2026, 3, 1),
            effective_end=date(2026, 3, 15),
            weekdays=frozenset({6}),
            start_time=time(9),
            duration_minutes=60,
        )
    )

    assert [item.occurrence_date for item in occurrences] == [
        date(2026, 3, 1),
        date(2026, 3, 8),
        date(2026, 3, 15),
    ]
    assert [item.start_utc.hour for item in occurrences] == [15, 14, 14]
    assert all(item.start_utc.tzinfo is UTC for item in occurrences)


def test_nonexistent_wall_time_is_rejected_instead_of_shifted() -> None:
    rule = WeeklyRecurrence(
        effective_start=date(2026, 3, 8),
        effective_end=date(2026, 3, 8),
        weekdays=frozenset({6}),
        start_time=time(2, 30),
        duration_minutes=30,
    )

    with pytest.raises(InvalidLocalTimeError):
        materialize_weekly(rule)


def test_operational_day_uses_real_elapsed_time_during_dst_change() -> None:
    start, end = operational_day_bounds(date(2026, 3, 8), "America/Chicago", time(0))

    assert (end - start).total_seconds() == 23 * 60 * 60
