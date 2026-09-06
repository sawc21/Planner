from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from semester_ops.application.common import add_audit_event, get_or_create_settings
from semester_ops.application.schedule import ScheduleService
from semester_ops.db.models import (
    Assignment,
    BlockOccurrence,
    CalendarEventLink,
    Course,
    ExternalSourceState,
    SyncConflict,
    SyncRun,
    utc_now,
)
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    DuePrecision,
    ExternalRecordState,
    SyncConflictStatus,
    SyncConnector,
    SyncStatus,
)
from semester_ops.integrations.blackboard import (
    BlackboardFeedClient,
    BlackboardFeedItem,
    ExistingBlackboardAssignment,
    parse_blackboard_ics,
    reconcile_blackboard_feed,
)
from semester_ops.integrations.google_calendar import (
    CalendarGateway,
    CalendarSyncSnapshot,
    GoogleCalendarAccessError,
    GoogleCalendarConfigurationError,
    LocalCalendarProjection,
    RemoteCalendarEvent,
    RemoteMutation,
    RemoteMutationKind,
    TimeRange,
    deterministic_event_id,
    ownership_tags,
    read_incremental_changes,
    reconcile_calendar,
)

SessionFactory = Callable[[], Session]


class ConnectorSyncError(RuntimeError):
    """A connector failure with a deliberately non-secret user-facing message."""

    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        category: str = "unexpected",
        recovery: str = "Try synchronization again.",
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.category = category
        self.recovery = recovery


@dataclass(frozen=True, slots=True)
class ConnectorSyncOutcome:
    status: SyncStatus = SyncStatus.SUCCEEDED
    created_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    conflict_count: int = 0
    error_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {SyncStatus.SUCCEEDED, SyncStatus.PARTIAL}:
            raise ValueError("A connector outcome must be succeeded or partial")
        counts = (
            self.created_count,
            self.updated_count,
            self.deleted_count,
            self.conflict_count,
            self.error_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Connector outcome counts cannot be negative")


class ConnectorSynchronizer(Protocol):
    connector: SyncConnector

    def synchronize(self, session: Session, *, run_id: str) -> ConnectorSyncOutcome: ...


@dataclass(frozen=True, slots=True)
class PersistedSyncResult:
    run_id: str
    connector: SyncConnector
    status: SyncStatus
    created_count: int
    updated_count: int
    deleted_count: int
    conflict_count: int
    error_count: int
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SyncBatchResult:
    runs: tuple[PersistedSyncResult, ...]

    @property
    def succeeded(self) -> bool:
        return bool(self.runs) and all(run.status is SyncStatus.SUCCEEDED for run in self.runs)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "succeeded" if self.succeeded else "attention",
            "runs": [
                {
                    "run_id": run.run_id,
                    "connector": run.connector.value,
                    "status": run.status.value,
                    "created": run.created_count,
                    "updated": run.updated_count,
                    "deleted": run.deleted_count,
                    "conflicts": run.conflict_count,
                    "errors": run.error_count,
                    "details": dict(run.details),
                }
                for run in self.runs
            ],
        }


class SyncService:
    """Run each connector in independent transactions and persist every outcome."""

    def __init__(
        self,
        session_factory: SessionFactory,
        synchronizers: Iterable[ConnectorSynchronizer],
    ) -> None:
        self._session_factory = session_factory
        self._synchronizers = tuple(synchronizers)
        connector_names = [synchronizer.connector for synchronizer in self._synchronizers]
        if len(set(connector_names)) != len(connector_names):
            raise ValueError("Only one synchronizer per connector may be registered")

    def sync_now(self) -> SyncBatchResult:
        results = tuple(self._run_one(synchronizer) for synchronizer in self._synchronizers)
        return SyncBatchResult(results)

    def _run_one(self, synchronizer: ConnectorSynchronizer) -> PersistedSyncResult:
        run_id = self._start_run(synchronizer.connector)
        try:
            with self._session_factory() as work_session:
                outcome = synchronizer.synchronize(work_session, run_id=run_id)
                work_session.commit()
        except Exception as exc:
            return self._finish_failed(run_id, synchronizer.connector, exc)
        return self._finish_succeeded(run_id, synchronizer.connector, outcome)

    def _start_run(self, connector: SyncConnector) -> str:
        with self._session_factory() as session:
            run = SyncRun(connector=connector, status=SyncStatus.RUNNING, started_at=utc_now())
            session.add(run)
            session.commit()
            return run.id

    def _finish_succeeded(
        self,
        run_id: str,
        connector: SyncConnector,
        outcome: ConnectorSyncOutcome,
    ) -> PersistedSyncResult:
        with self._session_factory() as session:
            run = _required_run(session, run_id)
            run.status = outcome.status
            run.finished_at = utc_now()
            run.created_count = outcome.created_count
            run.updated_count = outcome.updated_count
            run.deleted_count = outcome.deleted_count
            run.conflict_count = outcome.conflict_count
            run.error_count = outcome.error_count
            run.details_json = dict(outcome.details)
            session.commit()
        return PersistedSyncResult(
            run_id,
            connector,
            outcome.status,
            outcome.created_count,
            outcome.updated_count,
            outcome.deleted_count,
            outcome.conflict_count,
            outcome.error_count,
            dict(outcome.details),
        )

    def _finish_failed(
        self,
        run_id: str,
        connector: SyncConnector,
        error: Exception,
    ) -> PersistedSyncResult:
        details = _safe_error_details(connector, error)
        with self._session_factory() as session:
            run = _required_run(session, run_id)
            run.status = SyncStatus.FAILED
            run.finished_at = utc_now()
            run.error_count = 1
            run.details_json = details
            session.commit()
        return PersistedSyncResult(
            run_id,
            connector,
            SyncStatus.FAILED,
            0,
            0,
            0,
            0,
            1,
            details,
        )


class BlackboardAssignmentSync:
    connector = SyncConnector.BLACKBOARD

    def __init__(self, client: BlackboardFeedClient) -> None:
        self._client = client

    def synchronize(self, session: Session, *, run_id: str) -> ConnectorSyncOutcome:
        del run_id
        settings = get_or_create_settings(session)
        if not settings.blackboard_ics_url:
            raise ConnectorSyncError("not_configured", "Blackboard is not configured")

        state = _get_or_create_source_state(session, self.connector, "default")
        state.last_attempt_at = utc_now()
        try:
            fetched = self._client.fetch(
                settings.blackboard_ics_url,
                etag=state.etag,
                last_modified=state.last_modified,
            )
        except Exception as exc:
            raise ConnectorSyncError(
                "fetch_failed",
                "Blackboard calendar refresh failed",
            ) from exc

        if fetched.not_modified:
            state.last_success_at = utc_now()
            return ConnectorSyncOutcome(details={"not_modified": True})
        if fetched.content is None:
            raise ConnectorSyncError(
                "empty_response",
                "Blackboard returned an empty calendar response",
            )

        try:
            items = parse_blackboard_ics(
                fetched.content,
                default_timezone=settings.timezone,
            ).require_valid()
        except Exception as exc:
            raise ConnectorSyncError(
                "invalid_feed",
                "Blackboard returned a calendar that could not be imported",
            ) from exc

        records = tuple(
            session.scalars(select(Assignment).where(Assignment.external_source == "blackboard"))
        )
        current = {_assignment_key(record): record for record in records}
        existing = tuple(_existing_blackboard_assignment(record) for record in records)
        reconciliation = reconcile_blackboard_feed(items, existing)

        created_count = 0
        updated_count = 0
        now = utc_now()
        for item in reconciliation.upserts:
            record = current.get(item.external_key)
            due_changed = record is not None and _blackboard_due_changed(record, item)
            if record is None:
                record = Assignment(
                    external_source="blackboard",
                    external_uid=item.uid,
                    recurrence_id=item.recurrence_id or "",
                    title=item.title,
                    due_precision=DuePrecision.DATE,
                )
                session.add(record)
                current[item.external_key] = record
                created_count += 1
            else:
                updated_count += 1
            _apply_blackboard_item(record, item, now)
            _assign_blackboard_course(
                session,
                record,
                semester_id=settings.active_semester_id,
                course_name=item.course_name,
            )
            if due_changed:
                _mark_assignment_for_replanning(session, record, item)

        incoming_by_key = {item.external_key: item for item in items}
        for key in reconciliation.canceled:
            record = current[key]
            cancellation = incoming_by_key[key]
            record.source_state = ExternalRecordState.CANCELED
            record.inbox_status = AssignmentInboxStatus.CANCELED
            _apply_blackboard_source_revision(record, cancellation)
            record.last_seen_at = now
            updated_count += 1

        for key in reconciliation.stale:
            record = current[key]
            record.source_state = ExternalRecordState.STALE
            if record.inbox_status is AssignmentInboxStatus.INBOX:
                record.inbox_status = AssignmentInboxStatus.STALE
            updated_count += 1

        incoming_keys = {item.external_key for item in items}
        for key in reconciliation.unchanged:
            if key in incoming_keys and key in current:
                record = current[key]
                record.last_seen_at = now
                item = incoming_by_key[key]
                if item.status == "active" and _assign_blackboard_course(
                    session,
                    record,
                    semester_id=settings.active_semester_id,
                    course_name=item.course_name,
                ):
                    updated_count += 1

        state.etag = fetched.etag
        state.last_modified = fetched.last_modified
        state.last_success_at = now
        state.metadata_json = {"last_item_count": len(items)}
        return ConnectorSyncOutcome(
            created_count=created_count,
            updated_count=updated_count,
            deleted_count=len(reconciliation.canceled),
            details={
                "not_modified": False,
                "feed_items": len(items),
                "stale": len(reconciliation.stale),
                "unknown_cancellations": len(reconciliation.unknown_cancellations),
            },
        )


class GoogleCalendarProjectionSync:
    connector = SyncConnector.GOOGLE

    def __init__(
        self,
        gateway_factory: Callable[[], CalendarGateway],
        *,
        remote_mutation_limit: int = 50,
        initial_remote_mutation_limit: int | None = None,
    ) -> None:
        if not 1 <= remote_mutation_limit <= 250:
            raise ValueError("remote_mutation_limit must be between 1 and 250")
        if initial_remote_mutation_limit is not None and not (
            1 <= initial_remote_mutation_limit <= remote_mutation_limit
        ):
            raise ValueError(
                "initial_remote_mutation_limit must be between 1 and remote_mutation_limit"
            )
        self._gateway_factory = gateway_factory
        self._remote_mutation_limit = remote_mutation_limit
        self._initial_remote_mutation_limit = initial_remote_mutation_limit

    def synchronize(self, session: Session, *, run_id: str) -> ConnectorSyncOutcome:
        settings = get_or_create_settings(session)
        calendar_id = settings.google_calendar_id
        if not calendar_id:
            raise ConnectorSyncError(
                "not_configured",
                "Google Calendar is not configured.",
                category="setup",
                recovery="Run the Google setup command.",
            )

        state = _get_or_create_source_state(session, self.connector, calendar_id)
        previous_sync_token = state.sync_token
        state.last_attempt_at = utc_now()
        try:
            gateway = self._gateway_factory()
            incremental = read_incremental_changes(
                gateway,
                calendar_id,
                sync_token=state.sync_token,
            )
        except GoogleCalendarAccessError as exc:
            raise _google_connector_error(exc) from exc
        except GoogleCalendarConfigurationError as exc:
            raise ConnectorSyncError(
                "oauth_required",
                "Google Calendar authorization is not configured.",
                category="setup",
                recovery="Run the Google setup command.",
            ) from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise ConnectorSyncError(
                "calendar_temporarily_unavailable",
                "Google Calendar could not be reached.",
                category="network",
                recovery="Check the network connection, then press Sync now again.",
            ) from exc
        except Exception as exc:
            raise ConnectorSyncError(
                "calendar_read_failed",
                "Google Calendar could not be read.",
                category="unexpected",
                recovery=("Run Google setup with --reauthorize, then press Sync now again."),
            ) from exc

        occurrences = tuple(session.scalars(select(BlockOccurrence)))
        open_conflicts = tuple(
            session.scalars(
                select(SyncConflict)
                .where(SyncConflict.status == SyncConflictStatus.OPEN)
                .order_by(SyncConflict.created_at)
            )
        )
        open_conflicts_by_occurrence = {
            conflict.occurrence_id: conflict for conflict in open_conflicts
        }
        quarantined_occurrence_ids = set(open_conflicts_by_occurrence)
        for remote in incremental.events:
            remote_conflict = open_conflicts_by_occurrence.get(remote.occurrence_id or "")
            if remote_conflict is None or remote.deleted or remote.time_range is None:
                continue
            remote_conflict.remote_start_utc = remote.time_range.start
            remote_conflict.remote_end_utc = remote.time_range.end

        projections = tuple(
            _calendar_projection(occurrence)
            for occurrence in occurrences
            if occurrence.id not in quarantined_occurrence_ids
        )
        projections_by_id = {projection.occurrence_id: projection for projection in projections}
        links = tuple(
            session.scalars(
                select(CalendarEventLink).where(CalendarEventLink.calendar_id == calendar_id)
            )
        )
        links_by_occurrence = {link.occurrence_id: link for link in links}
        snapshots = tuple(
            snapshot for link in links if (snapshot := _calendar_snapshot(link)) is not None
        )
        remote_events = _complete_remote_view(
            incremental.events,
            projections_by_id,
            links,
            # A 410 recovery is a complete authoritative view. Synthesizing an
            # absent event from an old link would hide aged-out deletions forever.
            use_snapshots=(
                previous_sync_token is not None and not incremental.reset_from_full_scan
            ),
        )
        plan = reconcile_calendar(projections, remote_events, snapshots)

        remote_by_event_id = {event.event_id: event for event in remote_events}
        mutation_failures: list[dict[str, Any]] = []
        pulled_ids: set[str] = set()
        failed_pull_ids: set[str] = set()
        schedule = ScheduleService(session)
        for local_move in plan.local_time_mutations:
            try:
                with session.begin_nested():
                    occurrence = schedule.move_occurrence(
                        local_move.occurrence_id,
                        local_move.remote_time_range.start,
                        local_move.remote_time_range.end,
                        actor="google-calendar-sync",
                    )
                    occurrence.override_reason = "Moved in Google Calendar"
                    session.flush()
                projections_by_id[occurrence.id] = _calendar_projection(occurrence)
                pulled_ids.add(occurrence.id)
            except Exception as exc:
                failed_pull_ids.add(local_move.occurrence_id)
                mutation_failures.append(
                    _safe_mutation_failure(
                        operation="pull",
                        occurrence_id=local_move.occurrence_id,
                        event_id=local_move.remote_event_id,
                        stage="local_schedule",
                        error=exc,
                    )
                )

        for calendar_conflict in plan.conflicts:
            session.add(
                SyncConflict(
                    sync_run_id=run_id,
                    occurrence_id=calendar_conflict.occurrence_id,
                    planner_start_utc=calendar_conflict.planner_time_range.start,
                    planner_end_utc=calendar_conflict.planner_time_range.end,
                    remote_start_utc=calendar_conflict.google_time_range.start,
                    remote_end_utc=calendar_conflict.google_time_range.end,
                    base_start_utc=calendar_conflict.base_time_range.start,
                    base_end_utc=calendar_conflict.base_time_range.end,
                )
            )

        remote_mutations = list(plan.remote_mutations)
        mutation_indexes = {
            mutation.occurrence_id: index
            for index, mutation in enumerate(remote_mutations)
            if mutation.kind is RemoteMutationKind.UPSERT
        }
        # A pulled move increments the canonical occurrence revision. Push the
        # fresh ownership revision now, even when Google's original event metadata
        # was otherwise canonical.
        for occurrence_id in sorted(pulled_ids):
            projection = projections_by_id[occurrence_id]
            index = mutation_indexes.get(occurrence_id)
            if index is None:
                remote_mutations.append(
                    RemoteMutation(
                        RemoteMutationKind.UPSERT,
                        occurrence_id,
                        deterministic_event_id(occurrence_id),
                        projection,
                        "publish planner revision after pulling Google time",
                    )
                )
            else:
                remote_mutations[index] = replace(
                    remote_mutations[index],
                    projection=projection,
                )

        previous_metadata = dict(state.metadata_json or {})
        previous_cursor = previous_metadata.get("remote_mutation_cursor")
        if not isinstance(previous_cursor, str):
            previous_cursor = None
        eligible_remote_mutations = [
            mutation
            for mutation in remote_mutations
            if mutation.occurrence_id not in failed_pull_ids
        ]
        ordered_remote_mutations = _rotate_remote_mutations(
            eligible_remote_mutations,
            cursor=previous_cursor,
        )
        initial_smoke_batch = (
            self._initial_remote_mutation_limit is not None
            and not bool(previous_metadata.get("initial_smoke_attempted"))
            and bool(ordered_remote_mutations)
        )
        active_mutation_limit = (
            self._initial_remote_mutation_limit
            if initial_smoke_batch
            else self._remote_mutation_limit
        )
        if active_mutation_limit is None:  # Narrowed by initial_smoke_batch above.
            active_mutation_limit = self._remote_mutation_limit
        planned_mutation_count = len(ordered_remote_mutations)
        selected_remote_mutations = ordered_remote_mutations[:active_mutation_limit]

        created_ids: set[str] = set()
        updated_ids: set[str] = set(pulled_ids)
        deleted_count = 0
        external_writes_succeeded = 0
        remotely_written_ids: set[str] = set()
        attempted_mutation_count = 0
        last_attempted_cursor: str | None = None
        connector_write_error: ConnectorSyncError | None = None
        for remote_mutation in selected_remote_mutations:
            attempted_mutation_count += 1
            last_attempted_cursor = _remote_mutation_cursor(remote_mutation)
            link = links_by_occurrence.get(remote_mutation.occurrence_id)
            if remote_mutation.kind is RemoteMutationKind.DELETE:
                try:
                    deleted = gateway.delete_owned_event(
                        calendar_id,
                        event_id=remote_mutation.event_id,
                        occurrence_id=remote_mutation.occurrence_id,
                    )
                    if deleted:
                        deleted_count += 1
                        external_writes_succeeded += 1
                except Exception as exc:
                    mutation_failures.append(
                        _safe_mutation_failure(
                            operation=remote_mutation.kind.value,
                            occurrence_id=remote_mutation.occurrence_id,
                            event_id=remote_mutation.event_id,
                            stage="remote_write",
                            error=exc,
                        )
                    )
                    connector_write_error = _connector_wide_google_write_error(exc)
                    if connector_write_error is not None:
                        break
                    continue
                try:
                    with session.begin_nested():
                        if link is not None:
                            session.delete(link)
                        session.flush()
                    if link is not None:
                        links_by_occurrence.pop(remote_mutation.occurrence_id, None)
                except Exception as exc:
                    mutation_failures.append(
                        _safe_mutation_failure(
                            operation=remote_mutation.kind.value,
                            occurrence_id=remote_mutation.occurrence_id,
                            event_id=remote_mutation.event_id,
                            stage="local_persistence",
                            error=exc,
                            external_write_succeeded=deleted,
                        )
                    )
                continue

            if remote_mutation.projection is None:
                mutation_failures.append(
                    _safe_mutation_failure(
                        operation=remote_mutation.kind.value,
                        occurrence_id=remote_mutation.occurrence_id,
                        event_id=remote_mutation.event_id,
                        stage="planning",
                        error=RuntimeError("missing projection"),
                    )
                )
                continue
            try:
                written_remote = gateway.upsert_projection(
                    calendar_id,
                    event_id=remote_mutation.event_id,
                    projection=remote_mutation.projection,
                )
                external_writes_succeeded += 1
            except Exception as exc:
                mutation_failures.append(
                    _safe_mutation_failure(
                        operation=remote_mutation.kind.value,
                        occurrence_id=remote_mutation.occurrence_id,
                        event_id=remote_mutation.event_id,
                        stage="remote_write",
                        error=exc,
                    )
                )
                connector_write_error = _connector_wide_google_write_error(exc)
                if connector_write_error is not None:
                    break
                continue

            creating_link = link is None
            try:
                with session.begin_nested():
                    if link is None:
                        candidate_link = CalendarEventLink(
                            occurrence_id=remote_mutation.occurrence_id,
                            calendar_id=calendar_id,
                            event_id=written_remote.event_id,
                        )
                        session.add(candidate_link)
                        _update_calendar_link(
                            candidate_link,
                            remote_mutation.projection,
                            written_remote,
                        )
                        session.flush()
                    else:
                        candidate_link = link
                        _update_calendar_link(
                            candidate_link,
                            remote_mutation.projection,
                            written_remote,
                        )
                        session.flush()
                if creating_link:
                    links_by_occurrence[remote_mutation.occurrence_id] = candidate_link
                    created_ids.add(remote_mutation.occurrence_id)
                else:
                    updated_ids.add(remote_mutation.occurrence_id)
                remotely_written_ids.add(remote_mutation.occurrence_id)
            except Exception as exc:
                # The external write already happened. Keep the connector partial,
                # continue later items, and retry from the same source token.
                if creating_link:
                    created_ids.add(remote_mutation.occurrence_id)
                else:
                    updated_ids.add(remote_mutation.occurrence_id)
                mutation_failures.append(
                    _safe_mutation_failure(
                        operation=remote_mutation.kind.value,
                        occurrence_id=remote_mutation.occurrence_id,
                        event_id=written_remote.event_id,
                        stage="local_persistence",
                        error=exc,
                        external_write_succeeded=True,
                    )
                )

        deferred_mutation_count = max(
            planned_mutation_count - attempted_mutation_count,
            0,
        )
        continuation_required = deferred_mutation_count > 0

        for local_mutation in plan.local_time_mutations:
            if local_mutation.occurrence_id not in pulled_ids:
                continue
            if local_mutation.occurrence_id in remotely_written_ids:
                continue
            link = links_by_occurrence.get(local_mutation.occurrence_id)
            projection = projections_by_id[local_mutation.occurrence_id]
            pulled_remote = remote_by_event_id.get(local_mutation.remote_event_id)
            if link is not None and pulled_remote is not None:
                try:
                    with session.begin_nested():
                        _update_calendar_link(link, projection, pulled_remote)
                        session.flush()
                except Exception as exc:
                    mutation_failures.append(
                        _safe_mutation_failure(
                            operation="pull",
                            occurrence_id=local_mutation.occurrence_id,
                            event_id=local_mutation.remote_event_id,
                            stage="snapshot_persistence",
                            error=exc,
                        )
                    )

        for occurrence_id in plan.unchanged_occurrence_ids:
            if occurrence_id in remotely_written_ids:
                continue
            projection = projections_by_id[occurrence_id]
            unchanged_remote = remote_by_event_id.get(deterministic_event_id(occurrence_id))
            if (
                unchanged_remote is None
                or unchanged_remote.deleted
                or unchanged_remote.time_range is None
            ):
                continue
            link = links_by_occurrence.get(occurrence_id)
            try:
                with session.begin_nested():
                    if link is None:
                        candidate_link = CalendarEventLink(
                            occurrence_id=occurrence_id,
                            calendar_id=calendar_id,
                            event_id=unchanged_remote.event_id,
                        )
                        session.add(candidate_link)
                    else:
                        candidate_link = link
                    _update_calendar_link(candidate_link, projection, unchanged_remote)
                    session.flush()
                if link is None:
                    links_by_occurrence[occurrence_id] = candidate_link
            except Exception as exc:
                mutation_failures.append(
                    _safe_mutation_failure(
                        operation="snapshot",
                        occurrence_id=occurrence_id,
                        event_id=unchanged_remote.event_id,
                        stage="local_persistence",
                        error=exc,
                    )
                )

        finished_at = utc_now()
        retry_required = bool(mutation_failures or continuation_required)
        if retry_required:
            # Retain a usable token so failed item changes are replayed. An expired
            # token cannot be retained; force another full scan instead. Deferred
            # mutations deliberately replay the same source window until drained.
            state.sync_token = None if incremental.reset_from_full_scan else previous_sync_token
        else:
            state.sync_token = incremental.next_sync_token
        status = (
            SyncStatus.PARTIAL
            if (
                plan.conflicts
                or quarantined_occurrence_ids
                or mutation_failures
                or continuation_required
            )
            else SyncStatus.SUCCEEDED
        )
        if status is SyncStatus.SUCCEEDED:
            state.last_success_at = finished_at

        next_metadata = {
            **previous_metadata,
            "full_scan": incremental.reset_from_full_scan,
            "ignored_remote_events": len(plan.ignored_remote_event_ids),
            "remote_mutation_limit": active_mutation_limit,
            "remote_mutations_planned": planned_mutation_count,
            "remote_mutations_attempted": attempted_mutation_count,
            "remote_mutations_deferred": deferred_mutation_count,
            "continuation_required": continuation_required,
            "retry_required": retry_required,
        }
        if self._initial_remote_mutation_limit is not None:
            next_metadata["initial_smoke_attempted"] = bool(
                previous_metadata.get("initial_smoke_attempted")
                or (initial_smoke_batch and attempted_mutation_count)
            )
        if retry_required and last_attempted_cursor is not None:
            next_metadata["remote_mutation_cursor"] = last_attempted_cursor
        elif not retry_required:
            next_metadata.pop("remote_mutation_cursor", None)
        state.metadata_json = next_metadata
        session.flush()
        connector_error_details = (
            _safe_error_details(self.connector, connector_write_error)
            if connector_write_error is not None
            else {}
        )
        return ConnectorSyncOutcome(
            status=status,
            created_count=len(created_ids),
            updated_count=len(updated_ids),
            deleted_count=deleted_count,
            conflict_count=len(plan.conflicts) + len(quarantined_occurrence_ids),
            error_count=len(mutation_failures),
            details={
                "full_scan": incremental.reset_from_full_scan,
                "pulled_moves": len(pulled_ids),
                "ignored_remote_events": len(plan.ignored_remote_event_ids),
                "quarantined_conflicts": len(quarantined_occurrence_ids),
                "external_writes_succeeded": external_writes_succeeded,
                "failed_mutations": mutation_failures,
                "remote_mutation_limit": active_mutation_limit,
                "remote_mutations_planned": planned_mutation_count,
                "remote_mutations_attempted": attempted_mutation_count,
                "remote_mutations_deferred": deferred_mutation_count,
                "continuation_required": continuation_required,
                "retry_required": retry_required,
                **connector_error_details,
            },
        )


def _required_run(session: Session, run_id: str) -> SyncRun:
    run = session.get(SyncRun, run_id)
    if run is None:
        raise RuntimeError(f"Sync run {run_id} disappeared")
    return run


def _safe_error_details(connector: SyncConnector, error: Exception) -> dict[str, Any]:
    if isinstance(error, ConnectorSyncError):
        return {
            "error_code": error.code,
            "message": error.public_message,
            "category": error.category,
            "recovery": error.recovery,
        }
    return {
        "error_code": type(error).__name__,
        "message": f"{connector.value.title()} synchronization failed",
    }


def _safe_mutation_failure(
    *,
    operation: str,
    occurrence_id: str,
    event_id: str,
    stage: str,
    error: Exception,
    external_write_succeeded: bool = False,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "operation": operation,
        "occurrence_id": _safe_sync_identity(occurrence_id),
        "event_id": _safe_sync_identity(event_id),
        "stage": stage,
        "error_code": (
            error.code
            if isinstance(error, GoogleCalendarAccessError)
            else (
                "integrity_collision" if isinstance(error, IntegrityError) else type(error).__name__
            )
        ),
        "external_write_succeeded": external_write_succeeded,
    }
    if isinstance(error, GoogleCalendarAccessError):
        connector_error = _google_connector_error(error)
        details["category"] = connector_error.category
        details["recovery"] = connector_error.recovery
    return details


def _google_connector_error(error: GoogleCalendarAccessError) -> ConnectorSyncError:
    if error.code in {"oauth_required", "oauth_refresh_failed"}:
        return ConnectorSyncError(
            error.code,
            error.public_message,
            category="authorization",
            recovery=(
                "Run .\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize, "
                "then press Sync now again."
            ),
        )
    if error.code == "calendar_permission_denied":
        return ConnectorSyncError(
            error.code,
            error.public_message,
            category="calendar_access",
            recovery=(
                "Run .\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize, "
                "then press Sync now again."
            ),
        )
    if error.code == "calendar_not_found":
        return ConnectorSyncError(
            error.code,
            error.public_message,
            category="calendar_access",
            recovery=(
                "Restore the saved development calendar or repair its local calendar "
                "binding before syncing again."
            ),
        )
    if error.code == "calendar_rate_limited":
        return ConnectorSyncError(
            error.code,
            error.public_message,
            category="rate_limit",
            recovery="Wait briefly, then press Sync now again.",
        )
    if error.code == "calendar_temporarily_unavailable":
        return ConnectorSyncError(
            error.code,
            error.public_message,
            category="network",
            recovery="Check the network connection, then press Sync now again.",
        )
    return ConnectorSyncError(
        error.code,
        error.public_message,
        category="unexpected",
        recovery="Press Sync now again. Reauthorize Google if the failure repeats.",
    )


def _connector_wide_google_write_error(error: Exception) -> ConnectorSyncError | None:
    if isinstance(error, GoogleCalendarAccessError):
        return _google_connector_error(error)
    if isinstance(error, GoogleCalendarConfigurationError):
        return ConnectorSyncError(
            "oauth_required",
            "Google Calendar authorization is not configured.",
            category="setup",
            recovery="Run the Google setup command, then press Sync now again.",
        )
    if isinstance(error, (ConnectionError, OSError, TimeoutError)):
        return ConnectorSyncError(
            "calendar_temporarily_unavailable",
            "Google Calendar could not be reached.",
            category="network",
            recovery="Check the network connection, then press Sync now again.",
        )
    return None


def _remote_mutation_cursor(mutation: RemoteMutation) -> str:
    priority = "0" if mutation.kind is RemoteMutationKind.DELETE else "1"
    return f"{priority}:{mutation.occurrence_id}"


def _rotate_remote_mutations(
    mutations: Iterable[RemoteMutation],
    *,
    cursor: str | None,
) -> list[RemoteMutation]:
    values = tuple(mutations)
    delete_cursor = cursor if cursor is not None and cursor.startswith("0:") else None
    upsert_cursor = cursor if cursor is not None and cursor.startswith("1:") else None
    deletes = _rotate_remote_mutation_group(
        (mutation for mutation in values if mutation.kind is RemoteMutationKind.DELETE),
        cursor=delete_cursor,
    )
    upserts = _rotate_remote_mutation_group(
        (mutation for mutation in values if mutation.kind is RemoteMutationKind.UPSERT),
        cursor=upsert_cursor,
    )
    return [*deletes, *upserts]


def _rotate_remote_mutation_group(
    mutations: Iterable[RemoteMutation],
    *,
    cursor: str | None,
) -> list[RemoteMutation]:
    ordered = sorted(mutations, key=_remote_mutation_cursor)
    if not ordered or cursor is None:
        return ordered
    keys = [_remote_mutation_cursor(mutation) for mutation in ordered]
    try:
        start = keys.index(cursor) + 1
    except ValueError:
        start = next(
            (index for index, key in enumerate(keys) if key > cursor),
            0,
        )
    if start >= len(ordered):
        start = 0
    return [*ordered[start:], *ordered[:start]]


def _safe_sync_identity(value: str) -> str:
    if len(value) <= 200 and all(character.isalnum() or character in "-_" for character in value):
        return value
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{digest[:20]}"


def _get_or_create_source_state(
    session: Session,
    connector: SyncConnector,
    source_key: str,
) -> ExternalSourceState:
    state = session.scalar(
        select(ExternalSourceState).where(
            ExternalSourceState.connector == connector,
            ExternalSourceState.source_key == source_key,
        )
    )
    if state is None:
        state = ExternalSourceState(connector=connector, source_key=source_key)
        session.add(state)
        session.flush()
    return state


def _assignment_key(record: Assignment) -> tuple[str, str | None]:
    return (record.external_uid, record.recurrence_id or None)


def _existing_blackboard_assignment(record: Assignment) -> ExistingBlackboardAssignment:
    due = record.due_date if record.due_precision is DuePrecision.DATE else record.due_at_utc
    item = BlackboardFeedItem(
        uid=record.external_uid,
        recurrence_id=record.recurrence_id or None,
        title=record.title,
        due=due,
        due_precision=record.due_precision.value,
        course_name=record.course.name if record.course is not None else None,
        description=record.description,
        url=record.url,
        status="cancelled" if record.source_state is ExternalRecordState.CANCELED else "active",
        sequence=record.sequence or 0,
        dtstamp=record.source_dtstamp,
        last_modified=record.source_last_modified,
    )
    return ExistingBlackboardAssignment(item, record.source_state.value)


def _apply_blackboard_item(
    record: Assignment,
    item: BlackboardFeedItem,
    seen_at: datetime,
) -> None:
    if item.due is None or item.due_precision is None:
        raise ValueError("An active Blackboard assignment requires a due value")
    record.title = item.title
    record.description = item.description
    record.url = item.url
    record.due_precision = DuePrecision(item.due_precision)
    if item.due_precision == "date":
        if isinstance(item.due, datetime):
            raise ValueError("Date-precision Blackboard item contains a datetime")
        record.due_date = item.due
        record.due_at_utc = None
    else:
        if not isinstance(item.due, datetime):
            raise ValueError("Datetime-precision Blackboard item contains a date")
        record.due_date = None
        record.due_at_utc = item.due.astimezone(UTC)
    record.source_state = ExternalRecordState.ACTIVE
    if record.inbox_status in {
        AssignmentInboxStatus.CANCELED,
        AssignmentInboxStatus.STALE,
    }:
        record.inbox_status = AssignmentInboxStatus.INBOX
    record.sequence = item.sequence
    record.source_dtstamp = item.dtstamp
    record.source_last_modified = item.last_modified
    record.last_seen_at = seen_at


def _apply_blackboard_source_revision(
    record: Assignment,
    item: BlackboardFeedItem,
) -> None:
    """Persist tombstone ordering fields so an older active record cannot revive it."""

    record.sequence = item.sequence
    record.source_dtstamp = item.dtstamp
    record.source_last_modified = item.last_modified


def _blackboard_due_changed(record: Assignment, item: BlackboardFeedItem) -> bool:
    if item.due is None or item.due_precision is None:
        return False
    if item.due_precision == "date":
        incoming_date = item.due.date() if isinstance(item.due, datetime) else item.due
        return record.due_precision is not DuePrecision.DATE or record.due_date != incoming_date
    if not isinstance(item.due, datetime):
        return True
    return (
        record.due_precision is not DuePrecision.DATETIME
        or record.due_at_utc != item.due.astimezone(UTC)
    )


def _mark_assignment_for_replanning(
    session: Session,
    record: Assignment,
    item: BlackboardFeedItem,
) -> None:
    record.source_changed = True
    linked_study_ids: list[str] = []
    for link in record.block_links:
        if link.occurrence.category is not BlockCategory.STUDY:
            continue
        link.needs_replanning = True
        linked_study_ids.append(link.occurrence_id)
    add_audit_event(
        session,
        event_type="assignment.due_changed",
        entity_type="assignment",
        entity_id=record.id,
        actor="blackboard-sync",
        data={
            "source_sequence": item.sequence,
            "linked_study_occurrence_ids": linked_study_ids,
        },
    )


def _assign_blackboard_course(
    session: Session,
    assignment: Assignment,
    *,
    semester_id: str | None,
    course_name: str | None,
) -> bool:
    if semester_id is None or course_name is None:
        return False
    normalized_name = " ".join(course_name.casefold().split())
    external_id = "course-name:" + hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()
    course = session.scalar(
        select(Course).where(
            Course.semester_id == semester_id,
            Course.external_source == "blackboard",
            Course.external_id == external_id,
        )
    )
    changed = False
    if course is None:
        course = Course(
            semester_id=semester_id,
            name=course_name,
            external_source="blackboard",
            external_id=external_id,
        )
        session.add(course)
        changed = True
    elif course.name != course_name:
        course.name = course_name
        changed = True
    if assignment.course is not course:
        assignment.course = course
        changed = True
    return changed


def _calendar_projection(occurrence: BlockOccurrence) -> LocalCalendarProjection:
    return LocalCalendarProjection(
        occurrence_id=occurrence.id,
        summary=occurrence.title,
        description="Managed by the local Semester Ops tracker.",
        time_range=TimeRange(occurrence.planned_start_utc, occurrence.planned_end_utc),
        revision=occurrence.revision,
        canceled=occurrence.cancelled_at is not None,
        projection_enabled=occurrence.calendar_projection,
    )


def _calendar_snapshot(link: CalendarEventLink) -> CalendarSyncSnapshot | None:
    values = (
        link.last_synced_start_utc,
        link.last_synced_end_utc,
    )
    if any(value is None for value in values):
        return None
    start, end = cast(tuple[datetime, datetime], values)
    synced_range = TimeRange(start, end)
    return CalendarSyncSnapshot(
        occurrence_id=link.occurrence_id,
        event_id=link.event_id,
        local_time_range=synced_range,
        remote_time_range=synced_range,
        local_revision=link.last_synced_local_revision,
        remote_etag=link.etag,
    )


def _complete_remote_view(
    changed_events: tuple[RemoteCalendarEvent, ...],
    projections: dict[str, LocalCalendarProjection],
    links: tuple[CalendarEventLink, ...],
    *,
    use_snapshots: bool,
) -> tuple[RemoteCalendarEvent, ...]:
    by_event_id: dict[str, RemoteCalendarEvent] = {}
    if use_snapshots:
        for link in links:
            projection = projections.get(link.occurrence_id)
            snapshot = _calendar_snapshot(link)
            if projection is None or snapshot is None:
                continue
            by_event_id[link.event_id] = RemoteCalendarEvent(
                event_id=link.event_id,
                occurrence_id=link.occurrence_id,
                time_range=snapshot.remote_time_range,
                summary=projection.summary,
                description=projection.description,
                tags=ownership_tags(
                    link.occurrence_id,
                    link.last_synced_local_revision,
                ),
                etag=link.etag,
            )
    by_event_id.update((event.event_id, event) for event in changed_events)
    return tuple(by_event_id[event_id] for event_id in sorted(by_event_id))


def _update_calendar_link(
    link: CalendarEventLink,
    projection: LocalCalendarProjection,
    remote: RemoteCalendarEvent,
) -> None:
    if remote.time_range is None:
        raise ValueError("Cannot snapshot a deleted or untimed Google event")
    link.event_id = remote.event_id
    link.etag = remote.etag
    link.last_synced_local_revision = projection.revision
    link.last_synced_start_utc = projection.time_range.start
    link.last_synced_end_utc = projection.time_range.end
    link.last_synced_at = utc_now()
