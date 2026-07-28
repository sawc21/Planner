from datetime import UTC, datetime

import pytest

from semester_ops.domain.enums import TrackingStatus
from semester_ops.domain.tracking import (
    InvalidTrackingTransition,
    effective_status,
    require_transition,
)


def test_missed_is_derived_after_grace_period() -> None:
    planned_end = datetime(2026, 8, 24, 15, tzinfo=UTC)

    assert (
        effective_status(
            TrackingStatus.PLANNED,
            planned_end_utc=planned_end,
            now_utc=datetime(2026, 8, 24, 15, 30, tzinfo=UTC),
            requires_completion=True,
        )
        is TrackingStatus.PLANNED
    )
    assert (
        effective_status(
            TrackingStatus.PLANNED,
            planned_end_utc=planned_end,
            now_utc=datetime(2026, 8, 24, 15, 30, 1, tzinfo=UTC),
            requires_completion=True,
        )
        is TrackingStatus.MISSED
    )


def test_non_trackable_blocks_never_become_missed() -> None:
    assert (
        effective_status(
            TrackingStatus.PLANNED,
            planned_end_utc=datetime(2026, 8, 24, 15, tzinfo=UTC),
            now_utc=datetime(2026, 8, 25, 15, tzinfo=UTC),
            requires_completion=False,
        )
        is TrackingStatus.PLANNED
    )


def test_invalid_tracking_transition_is_explicit() -> None:
    with pytest.raises(InvalidTrackingTransition):
        require_transition(TrackingStatus.SKIPPED, TrackingStatus.COMPLETED)
