from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from semester_ops.integrations.blackboard.feed import BlackboardFeedItem

AssignmentSourceState = Literal["active", "stale", "canceled"]
ExternalKey = tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class ExistingBlackboardAssignment:
    item: BlackboardFeedItem
    source_state: AssignmentSourceState = "active"

    @property
    def external_key(self) -> ExternalKey:
        return self.item.external_key


@dataclass(frozen=True, slots=True)
class BlackboardReconciliation:
    upserts: tuple[BlackboardFeedItem, ...]
    canceled: tuple[ExternalKey, ...]
    stale: tuple[ExternalKey, ...]
    unchanged: tuple[ExternalKey, ...]
    unknown_cancellations: tuple[ExternalKey, ...]


def reconcile_blackboard_feed(
    incoming: tuple[BlackboardFeedItem, ...],
    existing: tuple[ExistingBlackboardAssignment, ...],
) -> BlackboardReconciliation:
    """Reconcile a complete, already-validated feed without destructive absence handling."""

    current = {assignment.external_key: assignment for assignment in existing}
    newest_incoming = _collapse_revisions(incoming)
    upserts: list[BlackboardFeedItem] = []
    canceled: list[ExternalKey] = []
    stale: list[ExternalKey] = []
    unchanged: list[ExternalKey] = []
    unknown_cancellations: list[ExternalKey] = []

    for key, candidate in newest_incoming.items():
        prior = current.get(key)
        if candidate.status == "cancelled":
            if prior is None:
                unknown_cancellations.append(key)
            elif _source_revision(candidate) >= _source_revision(prior.item):
                if prior.source_state == "canceled":
                    unchanged.append(key)
                else:
                    canceled.append(key)
            else:
                unchanged.append(key)
            continue

        changed = prior is not None and _content_changed(candidate, prior.item)
        if prior is None or prior.source_state != "active" or changed:
            if prior is None or _source_revision(candidate) >= _source_revision(prior.item):
                upserts.append(candidate)
            else:
                unchanged.append(key)
        else:
            unchanged.append(key)

    present_keys = set(newest_incoming)
    for key, prior in current.items():
        if key in present_keys:
            continue
        if prior.source_state == "active":
            stale.append(key)
        else:
            unchanged.append(key)

    def key_sort(key: ExternalKey) -> tuple[str, str]:
        return (key[0], key[1] or "")

    return BlackboardReconciliation(
        upserts=tuple(sorted(upserts, key=lambda item: key_sort(item.external_key))),
        canceled=tuple(sorted(canceled, key=key_sort)),
        stale=tuple(sorted(stale, key=key_sort)),
        unchanged=tuple(sorted(set(unchanged), key=key_sort)),
        unknown_cancellations=tuple(sorted(unknown_cancellations, key=key_sort)),
    )


def planning_deadline(item: BlackboardFeedItem, *, timezone_name: str) -> datetime:
    """Interpret a date-only source deadline as 11:59 PM without rewriting the source."""

    if item.due is None:
        raise ValueError("Canceled Blackboard item has no planning deadline")
    zone = ZoneInfo(timezone_name)
    if isinstance(item.due, datetime):
        if item.due.tzinfo is None:
            return item.due.replace(tzinfo=zone)
        return item.due.astimezone(zone)
    return datetime.combine(item.due, time(23, 59), tzinfo=zone)


def _collapse_revisions(
    incoming: tuple[BlackboardFeedItem, ...],
) -> dict[ExternalKey, BlackboardFeedItem]:
    result: dict[ExternalKey, BlackboardFeedItem] = {}
    for item in incoming:
        prior = result.get(item.external_key)
        if prior is None or _source_revision(item) >= _source_revision(prior):
            result[item.external_key] = item
    return result


def _source_revision(item: BlackboardFeedItem) -> tuple[int, datetime, datetime]:
    minimum = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    return (
        item.sequence,
        item.last_modified or minimum,
        item.dtstamp or minimum,
    )


def _content_changed(left: BlackboardFeedItem, right: BlackboardFeedItem) -> bool:
    return (
        left.title,
        left.due,
        left.due_precision,
        left.course_name,
        left.description,
        left.url,
        left.status,
        left.sequence,
        left.dtstamp,
        left.last_modified,
    ) != (
        right.title,
        right.due,
        right.due_precision,
        right.course_name,
        right.description,
        right.url,
        right.status,
        right.sequence,
        right.dtstamp,
        right.last_modified,
    )
