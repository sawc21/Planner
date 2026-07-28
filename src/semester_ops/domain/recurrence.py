from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from semester_ops.domain.time import resolve_wall_time


class RecurrenceValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WeeklyRecurrence:
    effective_start: date
    effective_end: date
    weekdays: frozenset[int]
    start_time: time
    duration_minutes: int
    timezone: str = "America/Chicago"
    excluded_dates: frozenset[date] = frozenset()

    def __post_init__(self) -> None:
        if self.effective_end < self.effective_start:
            raise RecurrenceValidationError("effective_end must be on or after effective_start")
        if not self.weekdays:
            raise RecurrenceValidationError("at least one weekday is required")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise RecurrenceValidationError("weekdays use Monday=0 through Sunday=6")
        if self.duration_minutes < 1:
            raise RecurrenceValidationError("duration_minutes must be positive")


@dataclass(frozen=True, slots=True)
class MaterializedTime:
    occurrence_date: date
    start_utc: datetime
    end_utc: datetime


def materialize_weekly(
    rule: WeeklyRecurrence,
    *,
    scope_start: date | None = None,
    scope_end: date | None = None,
) -> list[MaterializedTime]:
    start = max(rule.effective_start, scope_start or rule.effective_start)
    end = min(rule.effective_end, scope_end or rule.effective_end)
    if end < start:
        return []

    occurrences: list[MaterializedTime] = []
    current = start
    while current <= end:
        if current.weekday() in rule.weekdays and current not in rule.excluded_dates:
            start_local = resolve_wall_time(current, rule.start_time, rule.timezone)
            end_naive = datetime.combine(current, rule.start_time) + timedelta(
                minutes=rule.duration_minutes
            )
            end_local = resolve_wall_time(end_naive.date(), end_naive.time(), rule.timezone)
            occurrences.append(
                MaterializedTime(
                    occurrence_date=current,
                    start_utc=start_local.astimezone(UTC),
                    end_utc=end_local.astimezone(UTC),
                )
            )
        current += timedelta(days=1)
    return occurrences
