from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType

from semester_ops.integrations.google_calendar.identity import is_owned_tags


def normalized_instant(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Calendar timestamps must include a UTC offset")
    return value.astimezone(UTC).replace(microsecond=0)


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start = normalized_instant(self.start)
        end = normalized_instant(self.end)
        if end <= start:
            raise ValueError("Calendar event end must be after start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class LocalCalendarProjection:
    occurrence_id: str
    summary: str
    description: str
    time_range: TimeRange
    revision: int
    canceled: bool = False
    projection_enabled: bool = True

    def __post_init__(self) -> None:
        if not self.occurrence_id.strip():
            raise ValueError("occurrence_id cannot be blank")
        if not self.summary.strip():
            raise ValueError("Calendar summary cannot be blank")
        if self.revision < 0:
            raise ValueError("revision cannot be negative")


@dataclass(frozen=True, slots=True)
class RemoteCalendarEvent:
    event_id: str
    occurrence_id: str | None
    time_range: TimeRange | None
    summary: str | None
    description: str | None
    tags: Mapping[str, str]
    deleted: bool = False
    etag: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("Remote event is missing its ID")
        object.__setattr__(self, "tags", MappingProxyType(dict(self.tags)))
        if self.owned and not self.deleted and self.time_range is None:
            raise ValueError("Active app-owned Google event must have timed start/end values")

    @property
    def owned(self) -> bool:
        return is_owned_tags(dict(self.tags))


@dataclass(frozen=True, slots=True)
class CalendarSyncSnapshot:
    occurrence_id: str
    event_id: str
    local_time_range: TimeRange
    remote_time_range: TimeRange
    local_revision: int
    remote_etag: str | None = None


class RemoteMutationKind(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class RemoteMutation:
    kind: RemoteMutationKind
    occurrence_id: str
    event_id: str
    projection: LocalCalendarProjection | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.kind is RemoteMutationKind.UPSERT and self.projection is None:
            raise ValueError("Upsert mutation requires a canonical projection")
        if self.kind is RemoteMutationKind.DELETE and self.projection is not None:
            raise ValueError("Delete mutation cannot include a projection")


@dataclass(frozen=True, slots=True)
class LocalTimeMutation:
    occurrence_id: str
    remote_time_range: TimeRange
    remote_event_id: str
    remote_etag: str | None


@dataclass(frozen=True, slots=True)
class CalendarSyncConflict:
    occurrence_id: str
    base_time_range: TimeRange
    planner_time_range: TimeRange
    google_time_range: TimeRange
    remote_event_id: str


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    remote_mutations: tuple[RemoteMutation, ...]
    local_time_mutations: tuple[LocalTimeMutation, ...]
    conflicts: tuple[CalendarSyncConflict, ...]
    unchanged_occurrence_ids: tuple[str, ...]
    ignored_remote_event_ids: tuple[str, ...]
