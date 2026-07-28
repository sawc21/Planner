from datetime import datetime, timedelta

from semester_ops.domain.enums import TrackingStatus
from semester_ops.domain.time import as_utc


class InvalidTrackingTransition(ValueError):
    pass


def effective_status(
    persisted_status: TrackingStatus,
    *,
    planned_end_utc: datetime,
    now_utc: datetime,
    requires_completion: bool,
    grace_minutes: int = 30,
) -> TrackingStatus:
    if grace_minutes < 0:
        raise ValueError("grace_minutes cannot be negative")
    if (
        persisted_status is TrackingStatus.PLANNED
        and requires_completion
        and as_utc(now_utc, field="now_utc")
        > as_utc(planned_end_utc, field="planned_end_utc") + timedelta(minutes=grace_minutes)
    ):
        return TrackingStatus.MISSED
    return persisted_status


def require_transition(current: TrackingStatus, target: TrackingStatus) -> None:
    allowed: dict[TrackingStatus, frozenset[TrackingStatus]] = {
        TrackingStatus.PLANNED: frozenset(
            {TrackingStatus.IN_PROGRESS, TrackingStatus.COMPLETED, TrackingStatus.SKIPPED}
        ),
        TrackingStatus.IN_PROGRESS: frozenset(
            {TrackingStatus.COMPLETED, TrackingStatus.SKIPPED, TrackingStatus.PLANNED}
        ),
        TrackingStatus.COMPLETED: frozenset({TrackingStatus.PLANNED, TrackingStatus.IN_PROGRESS}),
        TrackingStatus.SKIPPED: frozenset({TrackingStatus.PLANNED}),
        TrackingStatus.MISSED: frozenset(
            {TrackingStatus.IN_PROGRESS, TrackingStatus.COMPLETED, TrackingStatus.SKIPPED}
        ),
    }
    if target not in allowed[current]:
        raise InvalidTrackingTransition(f"cannot move from {current.value} to {target.value}")
