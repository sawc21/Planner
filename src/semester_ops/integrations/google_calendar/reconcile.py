from __future__ import annotations

from dataclasses import replace

from semester_ops.integrations.google_calendar.identity import deterministic_event_id
from semester_ops.integrations.google_calendar.mapping import remote_matches_projection
from semester_ops.integrations.google_calendar.models import (
    CalendarSyncConflict,
    CalendarSyncSnapshot,
    LocalCalendarProjection,
    LocalTimeMutation,
    ReconciliationPlan,
    RemoteCalendarEvent,
    RemoteMutation,
    RemoteMutationKind,
)


class CalendarReconciliationError(ValueError):
    pass


def reconcile_calendar(
    local_projections: tuple[LocalCalendarProjection, ...],
    remote_events: tuple[RemoteCalendarEvent, ...],
    snapshots: tuple[CalendarSyncSnapshot, ...],
) -> ReconciliationPlan:
    """Produce a deterministic three-way plan without performing any external writes."""

    local_by_id = _unique_local(local_projections)
    snapshot_by_id = _unique_snapshots(snapshots)
    snapshot_by_event = {snapshot.event_id: snapshot for snapshot in snapshots}
    remote_by_id: dict[str, RemoteCalendarEvent] = {}
    ignored_remote_ids: list[str] = []

    for remote_event in remote_events:
        occurrence_id = remote_event.occurrence_id if remote_event.owned else None
        if occurrence_id is None and remote_event.deleted:
            prior = snapshot_by_event.get(remote_event.event_id)
            occurrence_id = prior.occurrence_id if prior else None
        if occurrence_id is None:
            ignored_remote_ids.append(remote_event.event_id)
            continue
        if occurrence_id in remote_by_id:
            raise CalendarReconciliationError(
                f"Multiple owned Google events claim occurrence {occurrence_id}"
            )
        remote_by_id[occurrence_id] = remote_event

    remote_mutations: list[RemoteMutation] = []
    local_mutations: list[LocalTimeMutation] = []
    conflicts: list[CalendarSyncConflict] = []
    unchanged: list[str] = []

    for occurrence_id in sorted(local_by_id):
        local = local_by_id[occurrence_id]
        remote = remote_by_id.get(occurrence_id)
        snapshot = snapshot_by_id.get(occurrence_id)
        expected_event_id = deterministic_event_id(occurrence_id)

        if local.canceled or not local.projection_enabled:
            if remote is not None and not remote.deleted:
                remote_mutations.append(
                    RemoteMutation(
                        RemoteMutationKind.DELETE,
                        occurrence_id,
                        remote.event_id,
                        reason="local projection canceled or disabled",
                    )
                )
            else:
                unchanged.append(occurrence_id)
            continue

        if remote is not None and remote.event_id != expected_event_id:
            raise CalendarReconciliationError(
                f"Owned Google event for {occurrence_id} has a non-deterministic ID"
            )

        if remote is None or remote.deleted:
            remote_mutations.append(
                RemoteMutation(
                    RemoteMutationKind.UPSERT,
                    occurrence_id,
                    expected_event_id,
                    local,
                    "remote projection missing or deleted",
                )
            )
            continue

        if remote.time_range is None:
            raise CalendarReconciliationError(
                f"Owned Google event for {occurrence_id} has no timed range"
            )

        if snapshot is None:
            if remote_matches_projection(remote, local):
                unchanged.append(occurrence_id)
            else:
                remote_mutations.append(
                    RemoteMutation(
                        RemoteMutationKind.UPSERT,
                        occurrence_id,
                        expected_event_id,
                        local,
                        "first synchronization establishes the planner projection",
                    )
                )
            continue

        local_changed = local.time_range != snapshot.local_time_range
        remote_changed = remote.time_range != snapshot.remote_time_range
        if local_changed and remote_changed and local.time_range != remote.time_range:
            conflicts.append(
                CalendarSyncConflict(
                    occurrence_id,
                    snapshot.local_time_range,
                    local.time_range,
                    remote.time_range,
                    remote.event_id,
                )
            )
            continue

        if remote_changed and not local_changed:
            local_mutations.append(
                LocalTimeMutation(
                    occurrence_id,
                    remote.time_range,
                    remote.event_id,
                    remote.etag,
                )
            )
            pulled_projection = replace(local, time_range=remote.time_range)
            if not remote_matches_projection(remote, pulled_projection):
                remote_mutations.append(
                    RemoteMutation(
                        RemoteMutationKind.UPSERT,
                        occurrence_id,
                        expected_event_id,
                        pulled_projection,
                        "restore planner-owned metadata after pulling Google time",
                    )
                )
            continue

        if local_changed or not remote_matches_projection(remote, local):
            remote_mutations.append(
                RemoteMutation(
                    RemoteMutationKind.UPSERT,
                    occurrence_id,
                    expected_event_id,
                    local,
                    "push canonical planner time or metadata",
                )
            )
        else:
            unchanged.append(occurrence_id)

    for occurrence_id, remote_event in remote_by_id.items():
        if occurrence_id not in local_by_id:
            ignored_remote_ids.append(remote_event.event_id)

    return ReconciliationPlan(
        tuple(remote_mutations),
        tuple(local_mutations),
        tuple(conflicts),
        tuple(unchanged),
        tuple(sorted(set(ignored_remote_ids))),
    )


def _unique_local(
    values: tuple[LocalCalendarProjection, ...],
) -> dict[str, LocalCalendarProjection]:
    result: dict[str, LocalCalendarProjection] = {}
    for value in values:
        if value.occurrence_id in result:
            raise CalendarReconciliationError(f"Duplicate local occurrence {value.occurrence_id}")
        result[value.occurrence_id] = value
    return result


def _unique_snapshots(
    values: tuple[CalendarSyncSnapshot, ...],
) -> dict[str, CalendarSyncSnapshot]:
    result: dict[str, CalendarSyncSnapshot] = {}
    event_ids: set[str] = set()
    for value in values:
        if value.occurrence_id in result or value.event_id in event_ids:
            raise CalendarReconciliationError("Duplicate calendar synchronization snapshot")
        result[value.occurrence_id] = value
        event_ids.add(value.event_id)
    return result
