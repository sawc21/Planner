from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from icalendar import Calendar

DuePrecision = Literal["date", "datetime"]
SourceStatus = Literal["active", "cancelled"]


@dataclass(frozen=True, slots=True)
class BlackboardFeedItem:
    """Normalized, read-only assignment-like event from Blackboard ICS."""

    uid: str
    recurrence_id: str | None
    title: str
    due: date | datetime | None
    due_precision: DuePrecision | None
    course_name: str | None
    description: str | None
    url: str | None
    status: SourceStatus
    sequence: int
    dtstamp: datetime | None
    last_modified: datetime | None

    @property
    def external_key(self) -> tuple[str, str | None]:
        return (self.uid, self.recurrence_id)


@dataclass(frozen=True, slots=True)
class BlackboardFeedIssue:
    component_index: int
    message: str
    uid: str | None = None


class BlackboardFeedParseError(ValueError):
    def __init__(self, issues: tuple[BlackboardFeedIssue, ...]) -> None:
        self.issues = issues
        details = "; ".join(issue.message for issue in issues)
        super().__init__(f"Blackboard calendar contains invalid events: {details}")


@dataclass(frozen=True, slots=True)
class ParsedBlackboardFeed:
    items: tuple[BlackboardFeedItem, ...]
    issues: tuple[BlackboardFeedIssue, ...]

    def require_valid(self) -> tuple[BlackboardFeedItem, ...]:
        """Return all items only when a partial feed cannot cause false staleness."""

        if self.issues:
            raise BlackboardFeedParseError(self.issues)
        return self.items


def parse_blackboard_ics(
    content: bytes,
    *,
    default_timezone: str = "America/Chicago",
) -> ParsedBlackboardFeed:
    """Parse VEVENT records without guessing missing identifiers or deadlines."""

    local_zone = ZoneInfo(default_timezone)
    try:
        calendar = Calendar.from_ical(content)
    except (ValueError, TypeError) as exc:
        issue = BlackboardFeedIssue(0, f"Calendar payload is not valid ICS: {exc}")
        return ParsedBlackboardFeed((), (issue,))

    items: list[BlackboardFeedItem] = []
    issues: list[BlackboardFeedIssue] = []
    for index, component in enumerate(calendar.walk("VEVENT"), start=1):
        uid = _text(component.get("UID"))
        status_text = (_text(component.get("STATUS")) or "CONFIRMED").upper()
        status: SourceStatus = "cancelled" if status_text == "CANCELLED" else "active"

        if not uid:
            issues.append(BlackboardFeedIssue(index, "VEVENT is missing UID"))
            continue

        title = _text(component.get("SUMMARY"))
        if not title:
            issues.append(BlackboardFeedIssue(index, "VEVENT is missing SUMMARY", uid))
            continue

        due, due_precision = _due_value(component.get("DTSTART"), local_zone)
        if due is None and status == "active":
            issues.append(BlackboardFeedIssue(index, "Active VEVENT is missing DTSTART", uid))
            continue

        sequence = _integer(component.get("SEQUENCE"), default=0)
        if sequence < 0:
            issues.append(BlackboardFeedIssue(index, "VEVENT SEQUENCE cannot be negative", uid))
            continue

        items.append(
            BlackboardFeedItem(
                uid=uid,
                recurrence_id=_recurrence_id(component.get("RECURRENCE-ID"), local_zone),
                title=title,
                due=due,
                due_precision=due_precision,
                course_name=_course_name(component),
                description=_text(component.get("DESCRIPTION")),
                url=_text(component.get("URL")),
                status=status,
                sequence=sequence,
                dtstamp=_timestamp(component.get("DTSTAMP"), local_zone),
                last_modified=_timestamp(component.get("LAST-MODIFIED"), local_zone),
            )
        )

    return ParsedBlackboardFeed(tuple(items), tuple(issues))


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer(value: object | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value))
    except ValueError:
        return -1


def _decoded(value: object | None) -> object | None:
    if value is None:
        return None
    decoded = getattr(value, "dt", None)
    return decoded if decoded is not None else value


def _due_value(
    value: object | None,
    local_zone: ZoneInfo,
) -> tuple[date | datetime | None, DuePrecision | None]:
    decoded = _decoded(value)
    if isinstance(decoded, datetime):
        return (_aware(decoded, local_zone), "datetime")
    if isinstance(decoded, date):
        return (decoded, "date")
    return (None, None)


def _timestamp(value: object | None, local_zone: ZoneInfo) -> datetime | None:
    decoded = _decoded(value)
    if not isinstance(decoded, datetime):
        return None
    return _aware(decoded, local_zone).astimezone(UTC)


def _recurrence_id(value: object | None, local_zone: ZoneInfo) -> str | None:
    decoded = _decoded(value)
    if isinstance(decoded, datetime):
        return _aware(decoded, local_zone).astimezone(UTC).isoformat()
    if isinstance(decoded, date):
        return decoded.isoformat()
    return _text(decoded)


def _aware(value: datetime, local_zone: ZoneInfo) -> datetime:
    return value.replace(tzinfo=local_zone) if value.tzinfo is None else value


def _course_name(component: object) -> str | None:
    for property_name in (
        "X-BLACKBOARD-COURSE-NAME",
        "X-BB-COURSE-NAME",
        "X-WR-CALNAME",
    ):
        value = component.get(property_name)  # type: ignore[attr-defined]
        if text := _text(value):
            return text

    categories = component.get("CATEGORIES")  # type: ignore[attr-defined]
    decoded = getattr(categories, "cats", None)
    if decoded:
        return _text(decoded[0])
    return None
