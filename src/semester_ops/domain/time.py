from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


class InvalidLocalTimeError(ValueError):
    pass


def require_aware(value: datetime, *, field: str = "datetime") -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def as_utc(value: datetime, *, field: str = "datetime") -> datetime:
    return require_aware(value, field=field).astimezone(UTC)


def resolve_wall_time(
    local_date: date,
    local_time: time,
    timezone: str,
    *,
    fold: int = 0,
) -> datetime:
    """Resolve an IANA wall time and reject nonexistent daylight-saving times."""
    zone = ZoneInfo(timezone)
    naive = datetime.combine(local_date, local_time)
    candidate = naive.replace(tzinfo=zone, fold=fold)
    round_trip = candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if round_trip != naive:
        raise InvalidLocalTimeError(
            f"{naive.isoformat()} does not exist in {timezone} because of a clock change"
        )
    return candidate


def operational_day_bounds(
    day: date,
    timezone: str,
    boundary: time = time(hour=4),
) -> tuple[datetime, datetime]:
    start = resolve_wall_time(day, boundary, timezone)
    end = resolve_wall_time(day + timedelta(days=1), boundary, timezone)
    return start.astimezone(UTC), end.astimezone(UTC)
