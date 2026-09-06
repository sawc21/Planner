import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from semester_ops.application.common import (
    add_audit_event,
    get_or_create_settings,
    increment_schedule_revision,
)
from semester_ops.application.errors import (
    DraftBlockedError,
    IdempotencyConflictError,
    NotFoundError,
    StaleRevisionError,
    ValidationError,
)
from semester_ops.application.recurrence import RecurrenceService
from semester_ops.db.models import (
    Assignment,
    AssignmentBlockLink,
    BlockOccurrence,
    BlockTemplate,
    ChecklistItem,
    ImportChange,
    ImportDraft,
    ImportIssue,
    MealItem,
    Semester,
    utc_now,
)
from semester_ops.domain.enums import (
    BlockCategory,
    ChangeOperation,
    DraftStatus,
    DuePrecision,
    Flexibility,
    ImportEntityType,
    ImportMode,
    IssueSeverity,
    TrackingStatus,
)
from semester_ops.domain.import_contract import (
    ImportPayload,
    OccurrenceInput,
    PatchOperation,
    TemplateInput,
)
from semester_ops.domain.recurrence import WeeklyRecurrence, materialize_weekly
from semester_ops.domain.time import resolve_wall_time


def _stable_id(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(("semops", *parts))))


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ImportService:
    """Create reviewable diffs and apply them atomically to the canonical schedule."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_draft(self, draft_id: str) -> ImportDraft:
        draft = self.session.scalar(
            select(ImportDraft)
            .options(selectinload(ImportDraft.changes), selectinload(ImportDraft.issues))
            .where(ImportDraft.id == draft_id)
        )
        if draft is None:
            raise NotFoundError(f"import draft {draft_id} was not found")
        return draft

    def create_draft(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        base_revision: int | None = None,
    ) -> ImportDraft:
        raw = dict(payload)
        if idempotency_key is not None:
            provided = raw.get("idempotency_key")
            if provided is not None and provided != idempotency_key:
                raise ValidationError("idempotency key argument does not match payload")
            raw["idempotency_key"] = idempotency_key
        if base_revision is not None:
            provided_revision = raw.get("base_revision")
            if provided_revision is not None and provided_revision != base_revision:
                raise ValidationError("base revision argument does not match payload")
            raw["base_revision"] = base_revision
        try:
            contract = ImportPayload.model_validate(raw)
        except PydanticValidationError as error:
            raise ValidationError(str(error)) from error

        normalized = contract.model_dump(mode="json")
        digest = _payload_hash(normalized)
        existing = self.session.scalar(
            select(ImportDraft).where(ImportDraft.idempotency_key == contract.idempotency_key)
        )
        if existing is not None:
            if existing.payload_hash != digest:
                raise IdempotencyConflictError(
                    "the idempotency key already belongs to a different payload"
                )
            return self.get_draft(existing.id)

        semester, semester_id, semester_is_new = self._resolve_semester(contract)
        draft = ImportDraft(
            schema_version=contract.schema_version,
            mode=contract.mode,
            managed_dataset=contract.managed_dataset,
            semester_id=semester.id if semester else None,
            scope_start_date=contract.scope.start_date,
            scope_end_date=contract.scope.end_date,
            idempotency_key=contract.idempotency_key,
            payload_hash=digest,
            payload_json=normalized,
            source_filename=contract.source.filename,
            source_media_type=contract.source.media_type,
            source_sha256=contract.source.sha256,
            assumptions=list(contract.assumptions),
            base_revision=contract.base_revision,
        )
        self.session.add(draft)
        self.session.flush()

        settings = get_or_create_settings(self.session)
        if contract.base_revision != settings.schedule_revision:
            self._issue(
                draft,
                IssueSeverity.ERROR,
                "stale_base_revision",
                f"draft is based on revision {contract.base_revision}; current revision is "
                f"{settings.schedule_revision}",
                path="base_revision",
                blocking=True,
            )
        for unresolved in contract.unresolved_fields:
            self._issue(
                draft,
                IssueSeverity.ERROR,
                "unresolved_field",
                unresolved.reason,
                path=unresolved.path,
                blocking=True,
            )
        if semester_is_new:
            assert contract.semester is not None
            self._change(
                draft,
                ChangeOperation.ADD,
                ImportEntityType.SEMESTER,
                semester_id,
                None,
                {
                    "id": semester_id,
                    **contract.semester.model_dump(mode="json", exclude={"id"}),
                },
            )

        if semester is not None and (
            contract.scope.start_date < semester.start_date
            or contract.scope.end_date > semester.end_date
        ):
            self._issue(
                draft,
                IssueSeverity.ERROR,
                "scope_outside_semester",
                "import scope must stay inside the selected semester",
                path="scope",
                blocking=True,
            )

        proposed: list[dict[str, Any]] = []
        if contract.mode is ImportMode.REPLACE_SCOPE:
            proposed = self._build_replacement(draft, contract, semester_id)
        else:
            proposed = self._build_patch(draft, contract, semester_id)
        self._detect_overlaps(
            draft,
            proposed,
            semester_id=semester_id,
            managed_dataset=contract.managed_dataset,
            scope_start=contract.scope.start_date,
            scope_end=contract.scope.end_date,
        )
        self._detect_assignment_deadlines(draft, proposed)
        draft.status = (
            DraftStatus.BLOCKED
            if any(issue.blocking for issue in draft.issues)
            else DraftStatus.READY
        )
        self.session.flush()
        return self.get_draft(draft.id)

    def apply_draft(self, draft_id: str, *, allow_warnings: bool = False) -> ImportDraft:
        draft = self.get_draft(draft_id)
        if draft.status is DraftStatus.APPLIED:
            return draft
        if draft.status is DraftStatus.REJECTED:
            raise DraftBlockedError("a rejected draft cannot be applied")
        if any(issue.blocking for issue in draft.issues):
            raise DraftBlockedError("resolve all blocking import issues before applying")
        if (
            any(issue.severity is IssueSeverity.WARNING for issue in draft.issues)
            and not allow_warnings
        ):
            raise DraftBlockedError("explicit warning approval is required")
        settings = get_or_create_settings(self.session)
        if settings.schedule_revision != draft.base_revision:
            raise StaleRevisionError(
                f"draft revision {draft.base_revision} is stale; current revision is "
                f"{settings.schedule_revision}"
            )

        now = utc_now()
        try:
            with self.session.begin_nested():
                for change in draft.changes:
                    self._apply_change(change, now)
                draft.warnings_accepted = allow_warnings
                draft.status = DraftStatus.APPLIED
                draft.applied_at = now
                if draft.semester_id is None:
                    semester_change = next(
                        (
                            change
                            for change in draft.changes
                            if change.entity_type is ImportEntityType.SEMESTER
                        ),
                        None,
                    )
                    if semester_change:
                        draft.semester_id = semester_change.target_id
                revision = increment_schedule_revision(self.session)
                add_audit_event(
                    self.session,
                    event_type="import.applied",
                    entity_type="import_draft",
                    entity_id=draft.id,
                    data={
                        "managed_dataset": draft.managed_dataset,
                        "change_count": len(draft.changes),
                        "schedule_revision": revision,
                    },
                )
                self.session.flush()
        except Exception:
            self.session.expire_all()
            raise
        return self.get_draft(draft.id)

    def reject_draft(self, draft_id: str) -> ImportDraft:
        draft = self.get_draft(draft_id)
        if draft.status is DraftStatus.APPLIED:
            raise DraftBlockedError("an applied draft cannot be rejected")
        draft.status = DraftStatus.REJECTED
        draft.rejected_at = utc_now()
        self.session.flush()
        return draft

    def _resolve_semester(self, contract: ImportPayload) -> tuple[Semester | None, str, bool]:
        semester_id = contract.scope.semester_id or (
            contract.semester.id if contract.semester else None
        )
        if semester_id:
            semester = self.session.get(Semester, semester_id)
            if semester is not None:
                return semester, semester.id, False
            if contract.semester is None:
                raise ValidationError(f"semester {semester_id} does not exist")
            return None, semester_id, True
        if contract.semester is None:
            raise ValidationError("semester details are required for a new semester")
        return None, str(uuid4()), True

    def _build_replacement(
        self,
        draft: ImportDraft,
        contract: ImportPayload,
        semester_id: str,
    ) -> list[dict[str, Any]]:
        proposed: list[dict[str, Any]] = []
        desired_template_keys: set[str] = set()
        desired_occurrence_keys: set[str] = set()
        for template in contract.templates:
            desired_template_keys.add(template.source_key)
            template_record = self._template_record(template, contract.managed_dataset, semester_id)
            existing_template = self._template_by_source(
                semester_id, contract.managed_dataset, template.source_key
            )
            if existing_template is not None:
                template_record["id"] = existing_template.id
            self._upsert_change(
                draft,
                ImportEntityType.TEMPLATE,
                existing_template,
                template_record,
                self._serialize_template,
            )
            for occurrence_record in self._materialize_record(
                template,
                template_record,
                contract.managed_dataset,
                semester_id,
                contract.scope.start_date,
                contract.scope.end_date,
            ):
                desired_occurrence_keys.add(occurrence_record["source_key"])
                existing_occurrence = self._occurrence_by_source(
                    semester_id,
                    contract.managed_dataset,
                    occurrence_record["source_key"],
                )
                if existing_occurrence is not None:
                    self._preserve_assignment_links(occurrence_record, existing_occurrence)
                if existing_occurrence and not self._safe_to_replace(existing_occurrence):
                    self._fixed_move_issue(draft, existing_occurrence, occurrence_record)
                    self._preserved_history_issue(draft, existing_occurrence)
                    continue
                self._upsert_change(
                    draft,
                    ImportEntityType.OCCURRENCE,
                    existing_occurrence,
                    occurrence_record,
                    self._serialize_occurrence,
                )
                proposed.append(occurrence_record)
        for occurrence_input in contract.occurrences:
            record = self._occurrence_record(
                occurrence_input,
                contract.managed_dataset,
                semester_id,
            )
            desired_occurrence_keys.add(record["source_key"])
            existing_direct_occurrence = self._occurrence_by_source(
                semester_id, contract.managed_dataset, occurrence_input.source_key
            )
            if (
                existing_direct_occurrence is not None
                and "assignment_ids" not in occurrence_input.model_fields_set
            ):
                self._preserve_assignment_links(record, existing_direct_occurrence)
            if existing_direct_occurrence and not self._safe_to_replace(existing_direct_occurrence):
                self._fixed_move_issue(draft, existing_direct_occurrence, record)
                self._preserved_history_issue(draft, existing_direct_occurrence)
                continue
            self._upsert_change(
                draft,
                ImportEntityType.OCCURRENCE,
                existing_direct_occurrence,
                record,
                self._serialize_occurrence,
            )
            proposed.append(record)

        existing_occurrences = self.session.scalars(
            select(BlockOccurrence).where(
                BlockOccurrence.semester_id == semester_id,
                BlockOccurrence.managed_dataset == contract.managed_dataset,
                BlockOccurrence.occurrence_date >= contract.scope.start_date,
                BlockOccurrence.occurrence_date <= contract.scope.end_date,
                BlockOccurrence.cancelled_at.is_(None),
            )
        )
        for stored_occurrence in existing_occurrences:
            if stored_occurrence.source_key not in desired_occurrence_keys:
                if self._safe_to_replace(stored_occurrence):
                    self._change(
                        draft,
                        ChangeOperation.CANCEL,
                        ImportEntityType.OCCURRENCE,
                        stored_occurrence.id,
                        self._serialize_occurrence(stored_occurrence),
                        None,
                    )
                else:
                    self._preserved_history_issue(draft, stored_occurrence)

        existing_templates = self.session.scalars(
            select(BlockTemplate).where(
                BlockTemplate.semester_id == semester_id,
                BlockTemplate.managed_dataset == contract.managed_dataset,
                BlockTemplate.cancelled_at.is_(None),
            )
        )
        for stored_template in existing_templates:
            if stored_template.source_key in desired_template_keys:
                continue
            if (
                stored_template.effective_start_date >= contract.scope.start_date
                and stored_template.effective_end_date <= contract.scope.end_date
            ):
                self._change(
                    draft,
                    ChangeOperation.CANCEL,
                    ImportEntityType.TEMPLATE,
                    stored_template.id,
                    self._serialize_template(stored_template),
                    None,
                )
            else:
                before = self._serialize_template(stored_template)
                after = dict(before)
                exclusions = set(after.get("excluded_dates", []))
                current = contract.scope.start_date
                while current <= contract.scope.end_date:
                    if current.weekday() in stored_template.weekdays:
                        exclusions.add(current.isoformat())
                    current += timedelta(days=1)
                after["excluded_dates"] = sorted(exclusions)
                self._change(
                    draft,
                    ChangeOperation.UPDATE,
                    ImportEntityType.TEMPLATE,
                    stored_template.id,
                    before,
                    after,
                )
        return proposed

    def _build_patch(
        self,
        draft: ImportDraft,
        contract: ImportPayload,
        semester_id: str,
    ) -> list[dict[str, Any]]:
        proposed: list[dict[str, Any]] = []
        for index, operation in enumerate(contract.operations):
            patch_target = self._resolve_patch_target(
                operation, semester_id, contract.managed_dataset
            )
            if operation.operation is not ChangeOperation.ADD and patch_target is None:
                self._issue(
                    draft,
                    IssueSeverity.ERROR,
                    "unknown_patch_target",
                    "patch target does not exist in the declared managed dataset",
                    path=f"operations[{index}]",
                    blocking=True,
                )
                continue
            if operation.operation is ChangeOperation.CANCEL:
                assert patch_target is not None
                before = (
                    self._serialize_template(patch_target)
                    if isinstance(patch_target, BlockTemplate)
                    else self._serialize_occurrence(patch_target)
                )
                if isinstance(patch_target, BlockOccurrence) and patch_target.template_id:
                    before["mark_as_override"] = True
                    before["override_reason"] = "cancelled by reviewed occurrence patch"
                self._change(
                    draft,
                    ChangeOperation.CANCEL,
                    operation.entity_type,
                    patch_target.id,
                    before,
                    None,
                )
                if isinstance(patch_target, BlockTemplate):
                    self._cancel_materialized_occurrences(
                        draft,
                        patch_target,
                        contract.scope.start_date,
                        contract.scope.end_date,
                    )
                continue
            try:
                if operation.entity_type is ImportEntityType.TEMPLATE:
                    template_value = TemplateInput.model_validate(operation.value)
                    template_patch_record = self._template_record(
                        template_value, contract.managed_dataset, semester_id
                    )
                    existing_template_target = (
                        patch_target if isinstance(patch_target, BlockTemplate) else None
                    )
                    if existing_template_target is not None:
                        template_patch_record["id"] = existing_template_target.id
                    self._upsert_change(
                        draft,
                        ImportEntityType.TEMPLATE,
                        existing_template_target,
                        template_patch_record,
                        self._serialize_template,
                    )
                    desired_occurrence_dates: set[date] = set()
                    for occurrence in self._materialize_record(
                        template_value,
                        template_patch_record,
                        contract.managed_dataset,
                        semester_id,
                        contract.scope.start_date,
                        contract.scope.end_date,
                    ):
                        occurrence_date = date.fromisoformat(occurrence["occurrence_date"])
                        desired_occurrence_dates.add(occurrence_date)
                        current = self._occurrence_by_source(
                            semester_id,
                            contract.managed_dataset,
                            occurrence["source_key"],
                        )
                        if current is None and existing_template_target is not None:
                            current = self._occurrence_for_template_date(
                                existing_template_target.id,
                                occurrence_date,
                            )
                        if current is not None:
                            occurrence["id"] = current.id
                            occurrence["template_id"] = template_patch_record["id"]
                            self._preserve_assignment_links(occurrence, current)
                            if self._serialize_occurrence(current) != occurrence and not (
                                self._safe_to_replace(current)
                            ):
                                self._fixed_move_issue(draft, current, occurrence)
                                self._preserved_history_issue(draft, current)
                                continue
                        self._upsert_change(
                            draft,
                            ImportEntityType.OCCURRENCE,
                            current,
                            occurrence,
                            self._serialize_occurrence,
                        )
                        proposed.append(occurrence)
                    if existing_template_target is not None:
                        self._cancel_removed_template_dates(
                            draft,
                            existing_template_target,
                            desired_occurrence_dates,
                            contract.scope.start_date,
                            contract.scope.end_date,
                        )
                else:
                    occurrence_value = OccurrenceInput.model_validate(operation.value)
                    occurrence_patch_record = self._occurrence_record(
                        occurrence_value, contract.managed_dataset, semester_id
                    )
                    existing_occurrence_target = (
                        patch_target if isinstance(patch_target, BlockOccurrence) else None
                    )
                    if existing_occurrence_target is not None:
                        occurrence_patch_record["id"] = existing_occurrence_target.id
                        occurrence_patch_record["template_id"] = (
                            existing_occurrence_target.template_id
                        )
                        if existing_occurrence_target.template_id:
                            # A generated occurrence's date is its recurrence identity. A
                            # cross-midnight move changes the planned instant, not that identity.
                            occurrence_patch_record["occurrence_date"] = (
                                existing_occurrence_target.occurrence_date.isoformat()
                            )
                            occurrence_patch_record["mark_as_override"] = True
                            occurrence_patch_record["override_reason"] = (
                                "updated by reviewed occurrence patch"
                            )
                        if "assignment_ids" not in occurrence_value.model_fields_set:
                            self._preserve_assignment_links(
                                occurrence_patch_record, existing_occurrence_target
                            )
                        if self._serialize_occurrence(
                            existing_occurrence_target
                        ) != occurrence_patch_record and not self._safe_to_replace(
                            existing_occurrence_target
                        ):
                            self._fixed_move_issue(
                                draft,
                                existing_occurrence_target,
                                occurrence_patch_record,
                            )
                            self._preserved_history_issue(draft, existing_occurrence_target)
                            continue
                    self._upsert_change(
                        draft,
                        ImportEntityType.OCCURRENCE,
                        existing_occurrence_target,
                        occurrence_patch_record,
                        self._serialize_occurrence,
                    )
                    proposed.append(occurrence_patch_record)
            except PydanticValidationError as error:
                self._issue(
                    draft,
                    IssueSeverity.ERROR,
                    "invalid_patch_value",
                    str(error),
                    path=f"operations[{index}].value",
                    blocking=True,
                )
        return proposed

    def _template_record(
        self, value: TemplateInput, managed_dataset: str, semester_id: str
    ) -> dict[str, Any]:
        record = value.model_dump(mode="json")
        return {
            "id": _stable_id(semester_id, managed_dataset, "template", value.source_key),
            "semester_id": semester_id,
            "managed_dataset": managed_dataset,
            **record,
        }

    def _occurrence_record(
        self,
        value: OccurrenceInput,
        managed_dataset: str,
        semester_id: str,
        *,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        start = resolve_wall_time(value.occurrence_date, value.start_time, "America/Chicago")
        end = start + timedelta(minutes=value.duration_minutes)
        earliest = (
            resolve_wall_time(
                value.occurrence_date, value.earliest_start_time, "America/Chicago"
            ).astimezone(UTC)
            if value.earliest_start_time
            else None
        )
        latest = (
            resolve_wall_time(
                value.occurrence_date, value.latest_end_time, "America/Chicago"
            ).astimezone(UTC)
            if value.latest_end_time
            else None
        )
        data = value.model_dump(mode="json")
        for key in (
            "occurrence_date",
            "start_time",
            "duration_minutes",
            "earliest_start_time",
            "latest_end_time",
            "template_source_key",
        ):
            data.pop(key, None)
        return {
            "id": _stable_id(semester_id, managed_dataset, "occurrence", value.source_key),
            "semester_id": semester_id,
            "template_id": template_id,
            "managed_dataset": managed_dataset,
            "occurrence_date": value.occurrence_date.isoformat(),
            "planned_start_utc": start.astimezone(UTC).isoformat(),
            "planned_end_utc": end.astimezone(UTC).isoformat(),
            "earliest_start_utc": earliest.isoformat() if earliest else None,
            "latest_end_utc": latest.isoformat() if latest else None,
            **data,
        }

    def _materialize_record(
        self,
        value: TemplateInput,
        template_record: dict[str, Any],
        managed_dataset: str,
        semester_id: str,
        scope_start: date,
        scope_end: date,
    ) -> list[dict[str, Any]]:
        rule = WeeklyRecurrence(
            effective_start=value.effective_start_date,
            effective_end=value.effective_end_date,
            weekdays=frozenset(value.weekdays),
            start_time=value.start_time,
            duration_minutes=value.duration_minutes,
            excluded_dates=frozenset(value.excluded_dates),
        )
        result: list[dict[str, Any]] = []
        for materialized in materialize_weekly(rule, scope_start=scope_start, scope_end=scope_end):
            source_key = f"template:{value.source_key}:{materialized.occurrence_date.isoformat()}"
            occurrence = OccurrenceInput(
                source_key=source_key,
                template_source_key=value.source_key,
                occurrence_date=materialized.occurrence_date,
                start_time=value.start_time,
                duration_minutes=value.duration_minutes,
                title=value.title,
                category=value.category,
                flexibility=value.flexibility,
                description=value.description,
                location=value.location,
                priority=value.priority,
                preferred_duration_minutes=value.preferred_duration_minutes,
                minimum_duration_minutes=value.minimum_duration_minutes,
                earliest_start_time=value.earliest_start_time,
                latest_end_time=value.latest_end_time,
                may_split=value.may_split,
                requires_completion=value.requires_completion,
                calendar_projection=value.calendar_projection,
                checklist_items=value.checklist_items,
                meal_items=value.meal_items,
                workout_exercises=value.workout_exercises,
            )
            record = self._occurrence_record(
                occurrence,
                managed_dataset,
                semester_id,
                template_id=template_record["id"],
            )
            record["id"] = _stable_id(
                template_record["id"], materialized.occurrence_date.isoformat()
            )
            result.append(record)
        return result

    def _upsert_change(
        self,
        draft: ImportDraft,
        entity_type: ImportEntityType,
        existing: Any,
        after: dict[str, Any],
        serializer: Any,
    ) -> None:
        before = serializer(existing) if existing is not None else None
        if before == after:
            return
        if entity_type is ImportEntityType.OCCURRENCE and isinstance(existing, BlockOccurrence):
            self._fixed_move_issue(draft, existing, after)
        self._change(
            draft,
            ChangeOperation.UPDATE if existing is not None else ChangeOperation.ADD,
            entity_type,
            existing.id if existing is not None else after["id"],
            before,
            after,
        )

    def _change(
        self,
        draft: ImportDraft,
        operation: ChangeOperation,
        entity_type: ImportEntityType,
        target_id: str | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        draft.changes.append(
            ImportChange(
                position=len(draft.changes),
                operation=operation,
                entity_type=entity_type,
                target_id=target_id,
                before_json=before,
                after_json=after,
            )
        )

    def _issue(
        self,
        draft: ImportDraft,
        severity: IssueSeverity,
        code: str,
        message: str,
        *,
        path: str | None = None,
        blocking: bool = False,
    ) -> None:
        draft.issues.append(
            ImportIssue(
                position=len(draft.issues),
                severity=severity,
                code=code,
                message=message,
                path=path,
                blocking=blocking,
            )
        )

    def _detect_overlaps(
        self,
        draft: ImportDraft,
        proposed: list[dict[str, Any]],
        *,
        semester_id: str,
        managed_dataset: str,
        scope_start: date,
        scope_end: date,
    ) -> None:
        ordered = sorted(proposed, key=lambda item: item["planned_start_utc"])
        for index, first in enumerate(ordered):
            first_end = datetime.fromisoformat(first["planned_end_utc"])
            for second in ordered[index + 1 :]:
                second_start = datetime.fromisoformat(second["planned_start_utc"])
                if second_start >= first_end:
                    break
                if datetime.fromisoformat(second["planned_end_utc"]) > datetime.fromisoformat(
                    first["planned_start_utc"]
                ):
                    self._issue(
                        draft,
                        IssueSeverity.WARNING,
                        "schedule_overlap",
                        f"{first['title']} overlaps {second['title']}",
                        blocking=False,
                    )

        existing_occurrences = tuple(
            self.session.scalars(
                select(BlockOccurrence).where(
                    BlockOccurrence.semester_id == semester_id,
                    BlockOccurrence.occurrence_date >= scope_start,
                    BlockOccurrence.occurrence_date <= scope_end,
                    BlockOccurrence.cancelled_at.is_(None),
                    or_(
                        BlockOccurrence.managed_dataset.is_(None),
                        BlockOccurrence.managed_dataset != managed_dataset,
                    ),
                )
            )
        )
        for record in ordered:
            record_start = datetime.fromisoformat(record["planned_start_utc"])
            record_end = datetime.fromisoformat(record["planned_end_utc"])
            for existing in existing_occurrences:
                if existing.id == record.get("id"):
                    continue
                if record_start < existing.planned_end_utc and record_end > (
                    existing.planned_start_utc
                ):
                    self._issue(
                        draft,
                        IssueSeverity.WARNING,
                        "schedule_overlap",
                        f"{record['title']} overlaps existing block {existing.title}",
                        blocking=False,
                    )

    def _detect_assignment_deadlines(
        self, draft: ImportDraft, proposed: list[dict[str, Any]]
    ) -> None:
        timezone_name = get_or_create_settings(self.session).timezone
        for record in proposed:
            planned_end = datetime.fromisoformat(record["planned_end_utc"])
            for assignment_id in dict.fromkeys(record.get("assignment_ids", [])):
                assignment = self.session.get(Assignment, assignment_id)
                if assignment is None:
                    self._issue(
                        draft,
                        IssueSeverity.ERROR,
                        "unknown_assignment_link",
                        f"Linked assignment {assignment_id} does not exist",
                        path=f"occurrence:{record['source_key']}.assignment_ids",
                        blocking=True,
                    )
                    continue
                deadline = self._assignment_deadline(assignment, timezone_name)
                if planned_end > deadline:
                    self._issue(
                        draft,
                        IssueSeverity.ERROR,
                        "assignment_deadline_exceeded",
                        f"{record['title']} ends after the planning deadline for "
                        f"{assignment.title}",
                        path=f"occurrence:{record['source_key']}.assignment_ids",
                        blocking=True,
                    )

    @staticmethod
    def _assignment_deadline(assignment: Assignment, timezone_name: str) -> datetime:
        if assignment.due_precision is DuePrecision.DATETIME:
            if assignment.due_at_utc is None:
                raise ValidationError(f"assignment {assignment.id} has no datetime deadline")
            return assignment.due_at_utc
        if assignment.due_date is None:
            raise ValidationError(f"assignment {assignment.id} has no date deadline")
        return resolve_wall_time(assignment.due_date, time(23, 59), timezone_name).astimezone(UTC)

    def _fixed_move_issue(
        self,
        draft: ImportDraft,
        occurrence: BlockOccurrence,
        after: dict[str, Any],
    ) -> None:
        if occurrence.flexibility is not Flexibility.FIXED:
            return
        if (
            occurrence.planned_start_utc.isoformat() == after["planned_start_utc"]
            and occurrence.planned_end_utc.isoformat() == after["planned_end_utc"]
        ):
            return
        self._issue(
            draft,
            IssueSeverity.ERROR,
            "fixed_occurrence_move",
            f"Fixed occurrence '{occurrence.title}' cannot be moved by a planning draft",
            path=f"occurrence:{occurrence.source_key or occurrence.id}",
            blocking=True,
        )

    @staticmethod
    def _preserve_assignment_links(record: dict[str, Any], occurrence: BlockOccurrence) -> None:
        record["assignment_ids"] = [link.assignment_id for link in occurrence.assignment_links]

    def _preserved_history_issue(self, draft: ImportDraft, occurrence: BlockOccurrence) -> None:
        self._issue(
            draft,
            IssueSeverity.WARNING,
            "tracked_occurrence_preserved",
            f"Tracked or overridden occurrence '{occurrence.title}' will be preserved",
            blocking=False,
        )

    @staticmethod
    def _safe_to_replace(occurrence: BlockOccurrence) -> bool:
        return (
            occurrence.status is TrackingStatus.PLANNED
            and occurrence.actual_start_utc is None
            and occurrence.actual_end_utc is None
            and not occurrence.is_override
            and all(
                item.completed_at is None and item.skipped_at is None
                for item in occurrence.checklist_items
            )
            and all(
                item.completed_at is None and item.consumed_quantity is None
                for item in occurrence.meal_items
            )
            and all(
                workout_set.completed_at is None
                and workout_set.actual_reps is None
                and workout_set.actual_weight is None
                for exercise in occurrence.workout_exercises
                for workout_set in exercise.sets
            )
        )

    def _cancel_materialized_occurrences(
        self,
        draft: ImportDraft,
        template: BlockTemplate,
        scope_start: date,
        scope_end: date,
    ) -> None:
        for occurrence in self._active_template_occurrences(template.id, scope_start, scope_end):
            if self._safe_to_replace(occurrence):
                self._change(
                    draft,
                    ChangeOperation.CANCEL,
                    ImportEntityType.OCCURRENCE,
                    occurrence.id,
                    self._serialize_occurrence(occurrence),
                    None,
                )
            else:
                self._preserved_history_issue(draft, occurrence)

    def _cancel_removed_template_dates(
        self,
        draft: ImportDraft,
        template: BlockTemplate,
        desired_dates: set[date],
        scope_start: date,
        scope_end: date,
    ) -> None:
        for occurrence in self._active_template_occurrences(template.id, scope_start, scope_end):
            if occurrence.occurrence_date in desired_dates:
                continue
            if self._safe_to_replace(occurrence):
                self._change(
                    draft,
                    ChangeOperation.CANCEL,
                    ImportEntityType.OCCURRENCE,
                    occurrence.id,
                    self._serialize_occurrence(occurrence),
                    None,
                )
            else:
                self._preserved_history_issue(draft, occurrence)

    def _active_template_occurrences(
        self, template_id: str, scope_start: date, scope_end: date
    ) -> tuple[BlockOccurrence, ...]:
        return tuple(
            self.session.scalars(
                select(BlockOccurrence).where(
                    BlockOccurrence.template_id == template_id,
                    BlockOccurrence.occurrence_date >= scope_start,
                    BlockOccurrence.occurrence_date <= scope_end,
                    BlockOccurrence.cancelled_at.is_(None),
                )
            )
        )

    def _occurrence_for_template_date(
        self, template_id: str, occurrence_date: date
    ) -> BlockOccurrence | None:
        return self.session.scalar(
            select(BlockOccurrence).where(
                BlockOccurrence.template_id == template_id,
                BlockOccurrence.occurrence_date == occurrence_date,
            )
        )

    def _template_by_source(
        self, semester_id: str, managed_dataset: str, source_key: str
    ) -> BlockTemplate | None:
        return self.session.scalar(
            select(BlockTemplate).where(
                BlockTemplate.semester_id == semester_id,
                BlockTemplate.managed_dataset == managed_dataset,
                BlockTemplate.source_key == source_key,
            )
        )

    def _occurrence_by_source(
        self, semester_id: str, managed_dataset: str, source_key: str
    ) -> BlockOccurrence | None:
        return self.session.scalar(
            select(BlockOccurrence).where(
                BlockOccurrence.semester_id == semester_id,
                BlockOccurrence.managed_dataset == managed_dataset,
                BlockOccurrence.source_key == source_key,
            )
        )

    def _resolve_patch_target(
        self, operation: PatchOperation, semester_id: str, managed_dataset: str
    ) -> BlockTemplate | BlockOccurrence | None:
        if operation.entity_type is ImportEntityType.TEMPLATE:
            template_statement = select(BlockTemplate).where(
                BlockTemplate.semester_id == semester_id,
                BlockTemplate.managed_dataset == managed_dataset,
            )
            if operation.target_id:
                template_statement = template_statement.where(
                    BlockTemplate.id == operation.target_id
                )
            elif operation.target_source_key:
                template_statement = template_statement.where(
                    BlockTemplate.source_key == operation.target_source_key
                )
            else:
                return None
            return self.session.scalar(template_statement)

        occurrence_statement = select(BlockOccurrence).where(
            BlockOccurrence.semester_id == semester_id,
            BlockOccurrence.managed_dataset == managed_dataset,
        )
        if operation.target_id:
            occurrence_statement = occurrence_statement.where(
                BlockOccurrence.id == operation.target_id
            )
        elif operation.target_source_key:
            occurrence_statement = occurrence_statement.where(
                BlockOccurrence.source_key == operation.target_source_key
            )
        else:
            return None
        return self.session.scalar(occurrence_statement)

    def _apply_change(self, change: ImportChange, now: datetime) -> None:
        if change.entity_type is ImportEntityType.SEMESTER:
            self._apply_semester(change, now)
        elif change.entity_type is ImportEntityType.TEMPLATE:
            self._apply_template(change, now)
        else:
            self._apply_occurrence(change, now)
        change.applied_at = now

    def _apply_semester(self, change: ImportChange, now: datetime) -> None:
        if change.operation is not ChangeOperation.ADD or change.after_json is None:
            raise ValidationError("semester changes may only add a new semester")
        data = change.after_json
        for active in self.session.scalars(select(Semester).where(Semester.is_active)):
            active.is_active = False
        semester = Semester(
            id=data["id"],
            name=data["name"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]),
            timezone=data["timezone"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(semester)
        self.session.flush()
        get_or_create_settings(self.session).active_semester_id = semester.id

    def _apply_template(self, change: ImportChange, now: datetime) -> None:
        template = self.session.get(BlockTemplate, change.target_id) if change.target_id else None
        if change.operation is ChangeOperation.CANCEL:
            if template is None:
                raise NotFoundError("template disappeared before draft application")
            template.cancelled_at = now
            template.revision += 1
            return
        if change.after_json is None:
            raise ValidationError("template add/update is missing its desired state")
        data = change.after_json
        if template is None:
            template = BlockTemplate(
                id=data["id"],
                semester_id=data["semester_id"],
                title=data["title"],
                local_start_time=datetime.fromisoformat(f"2000-01-01T{data['start_time']}").time(),
                duration_minutes=data["duration_minutes"],
                effective_start_date=date.fromisoformat(data["effective_start_date"]),
                effective_end_date=date.fromisoformat(data["effective_end_date"]),
                revision=1,
            )
            self.session.add(template)
        self._set_template_data(template, data)
        template.cancelled_at = None
        if change.operation is ChangeOperation.UPDATE:
            template.revision += 1

    def _apply_occurrence(self, change: ImportChange, now: datetime) -> None:
        occurrence = (
            self.session.get(BlockOccurrence, change.target_id) if change.target_id else None
        )
        if change.operation is ChangeOperation.CANCEL:
            if occurrence is None:
                raise NotFoundError("occurrence disappeared before draft application")
            occurrence.cancelled_at = now
            if change.before_json and change.before_json.get("mark_as_override"):
                occurrence.is_override = True
                occurrence.override_reason = change.before_json.get("override_reason")
            occurrence.revision += 1
            return
        if change.after_json is None:
            raise ValidationError("occurrence add/update is missing its desired state")
        data = change.after_json
        if occurrence is None:
            occurrence = BlockOccurrence(
                id=data["id"],
                semester_id=data["semester_id"],
                template_id=data.get("template_id"),
                occurrence_date=date.fromisoformat(data["occurrence_date"]),
                title=data["title"],
                planned_start_utc=datetime.fromisoformat(data["planned_start_utc"]),
                planned_end_utc=datetime.fromisoformat(data["planned_end_utc"]),
                revision=1,
            )
            self.session.add(occurrence)
        self._set_occurrence_data(occurrence, data)
        occurrence.cancelled_at = None
        if change.operation is ChangeOperation.UPDATE:
            occurrence.revision += 1
        self._replace_occurrence_children(occurrence, data)
        self._replace_assignment_links(occurrence, data.get("assignment_ids", []))

    @staticmethod
    def _set_template_data(template: BlockTemplate, data: dict[str, Any]) -> None:
        template.title = data["title"]
        template.category = BlockCategory(data["category"])
        template.flexibility = Flexibility(data["flexibility"])
        template.description = data.get("description")
        template.location = data.get("location")
        template.weekdays = list(data["weekdays"])
        template.local_start_time = datetime.fromisoformat(
            f"2000-01-01T{data['start_time']}"
        ).time()
        template.duration_minutes = data["duration_minutes"]
        template.effective_start_date = date.fromisoformat(data["effective_start_date"])
        template.effective_end_date = date.fromisoformat(data["effective_end_date"])
        template.excluded_dates = list(data.get("excluded_dates", []))
        template.timezone = "America/Chicago"
        template.earliest_start_time = (
            datetime.fromisoformat(f"2000-01-01T{data['earliest_start_time']}").time()
            if data.get("earliest_start_time")
            else None
        )
        template.latest_end_time = (
            datetime.fromisoformat(f"2000-01-01T{data['latest_end_time']}").time()
            if data.get("latest_end_time")
            else None
        )
        template.priority = data["priority"]
        template.preferred_duration_minutes = data.get("preferred_duration_minutes")
        template.minimum_duration_minutes = data.get("minimum_duration_minutes")
        template.may_split = data["may_split"]
        template.requires_completion = data["requires_completion"]
        template.calendar_projection = data["calendar_projection"]
        template.managed_dataset = data["managed_dataset"]
        template.source_key = data["source_key"]
        template.content_json = {
            "checklist_items": data.get("checklist_items", []),
            "meal_items": data.get("meal_items", []),
            "workout_exercises": data.get("workout_exercises", []),
        }

    @staticmethod
    def _set_occurrence_data(occurrence: BlockOccurrence, data: dict[str, Any]) -> None:
        occurrence.template_id = data.get("template_id")
        occurrence.occurrence_date = date.fromisoformat(data["occurrence_date"])
        occurrence.title = data["title"]
        occurrence.category = BlockCategory(data["category"])
        occurrence.flexibility = Flexibility(data["flexibility"])
        occurrence.description = data.get("description")
        occurrence.location = data.get("location")
        occurrence.planned_start_utc = datetime.fromisoformat(data["planned_start_utc"])
        occurrence.planned_end_utc = datetime.fromisoformat(data["planned_end_utc"])
        occurrence.earliest_start_utc = (
            datetime.fromisoformat(data["earliest_start_utc"])
            if data.get("earliest_start_utc")
            else None
        )
        occurrence.latest_end_utc = (
            datetime.fromisoformat(data["latest_end_utc"]) if data.get("latest_end_utc") else None
        )
        occurrence.priority = data["priority"]
        occurrence.preferred_duration_minutes = data.get("preferred_duration_minutes")
        occurrence.minimum_duration_minutes = data.get("minimum_duration_minutes")
        occurrence.may_split = data["may_split"]
        occurrence.requires_completion = data["requires_completion"]
        occurrence.calendar_projection = data["calendar_projection"]
        occurrence.managed_dataset = data["managed_dataset"]
        occurrence.source_key = data["source_key"]
        if data.get("mark_as_override"):
            occurrence.is_override = True
            occurrence.override_reason = data.get("override_reason")

    @staticmethod
    def _replace_occurrence_children(occurrence: BlockOccurrence, data: dict[str, Any]) -> None:
        occurrence.checklist_items = [
            ChecklistItem(
                title=item["title"],
                required=item.get("required", True),
                position=item.get("position", index),
            )
            for index, item in enumerate(data.get("checklist_items", []))
        ]
        occurrence.meal_items = [
            MealItem(
                food_name=item["food_name"],
                unit=item.get("unit", "serving"),
                planned_quantity=Decimal(str(item.get("planned_quantity", "1"))),
                calories_per_unit=Decimal(str(item.get("calories_per_unit", "0"))),
                protein_grams_per_unit=Decimal(str(item.get("protein_grams_per_unit", "0"))),
                required=item.get("required", True),
                position=item.get("position", index),
            )
            for index, item in enumerate(data.get("meal_items", []))
        ]
        occurrence.workout_exercises = []
        RecurrenceService._replace_children(
            occurrence,
            {"workout_exercises": data.get("workout_exercises", [])},
        )

    def _replace_assignment_links(
        self, occurrence: BlockOccurrence, assignment_ids: list[str]
    ) -> None:
        links: list[AssignmentBlockLink] = []
        for assignment_id in assignment_ids:
            if self.session.get(Assignment, assignment_id) is None:
                raise ValidationError(f"assignment {assignment_id} does not exist")
            links.append(AssignmentBlockLink(assignment_id=assignment_id))
        occurrence.assignment_links = links

    @staticmethod
    def _serialize_template(template: BlockTemplate) -> dict[str, Any]:
        content = template.content_json
        return {
            "id": template.id,
            "semester_id": template.semester_id,
            "managed_dataset": template.managed_dataset,
            "source_key": template.source_key,
            "title": template.title,
            "category": template.category.value,
            "flexibility": template.flexibility.value,
            "description": template.description,
            "location": template.location,
            "weekdays": list(template.weekdays),
            "start_time": template.local_start_time.isoformat(),
            "duration_minutes": template.duration_minutes,
            "effective_start_date": template.effective_start_date.isoformat(),
            "effective_end_date": template.effective_end_date.isoformat(),
            "excluded_dates": list(template.excluded_dates),
            "earliest_start_time": (
                template.earliest_start_time.isoformat() if template.earliest_start_time else None
            ),
            "latest_end_time": (
                template.latest_end_time.isoformat() if template.latest_end_time else None
            ),
            "priority": template.priority,
            "preferred_duration_minutes": template.preferred_duration_minutes,
            "minimum_duration_minutes": template.minimum_duration_minutes,
            "may_split": template.may_split,
            "requires_completion": template.requires_completion,
            "calendar_projection": template.calendar_projection,
            "checklist_items": content.get("checklist_items", []),
            "meal_items": content.get("meal_items", []),
            "workout_exercises": content.get("workout_exercises", []),
        }

    @staticmethod
    def _serialize_occurrence(occurrence: BlockOccurrence) -> dict[str, Any]:
        return {
            "id": occurrence.id,
            "semester_id": occurrence.semester_id,
            "template_id": occurrence.template_id,
            "managed_dataset": occurrence.managed_dataset,
            "source_key": occurrence.source_key,
            "occurrence_date": occurrence.occurrence_date.isoformat(),
            "title": occurrence.title,
            "category": occurrence.category.value,
            "flexibility": occurrence.flexibility.value,
            "description": occurrence.description,
            "location": occurrence.location,
            "planned_start_utc": occurrence.planned_start_utc.isoformat(),
            "planned_end_utc": occurrence.planned_end_utc.isoformat(),
            "earliest_start_utc": (
                occurrence.earliest_start_utc.isoformat() if occurrence.earliest_start_utc else None
            ),
            "latest_end_utc": (
                occurrence.latest_end_utc.isoformat() if occurrence.latest_end_utc else None
            ),
            "priority": occurrence.priority,
            "preferred_duration_minutes": occurrence.preferred_duration_minutes,
            "minimum_duration_minutes": occurrence.minimum_duration_minutes,
            "may_split": occurrence.may_split,
            "requires_completion": occurrence.requires_completion,
            "calendar_projection": occurrence.calendar_projection,
            "checklist_items": [
                {"title": item.title, "required": item.required, "position": item.position}
                for item in occurrence.checklist_items
            ],
            "meal_items": [
                {
                    "food_name": item.food_name,
                    "unit": item.unit,
                    "planned_quantity": str(item.planned_quantity),
                    "calories_per_unit": str(item.calories_per_unit),
                    "protein_grams_per_unit": str(item.protein_grams_per_unit),
                    "required": item.required,
                    "position": item.position,
                }
                for item in occurrence.meal_items
            ],
            "workout_exercises": [
                {
                    "name": exercise.name,
                    "planned_sets": exercise.planned_sets,
                    "rep_min": exercise.rep_min,
                    "rep_max": exercise.rep_max,
                    "target_weight": (
                        str(exercise.target_weight) if exercise.target_weight is not None else None
                    ),
                    "weight_unit": exercise.weight_unit,
                    "required": exercise.required,
                    "position": exercise.position,
                    "notes": exercise.notes,
                    "sets": [
                        {"set_number": item.set_number, "target_reps": item.target_reps}
                        for item in exercise.sets
                    ],
                }
                for exercise in occurrence.workout_exercises
            ],
            "assignment_ids": [link.assignment_id for link in occurrence.assignment_links],
        }
