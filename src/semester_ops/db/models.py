from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semester_ops.db.base import Base
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    ChangeOperation,
    DraftStatus,
    DuePrecision,
    ExternalRecordState,
    Flexibility,
    ImportEntityType,
    ImportMode,
    IssueSeverity,
    SyncConflictStatus,
    SyncConnector,
    SyncStatus,
    TrackingStatus,
)


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC datetimes while restoring tzinfo lost by SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime values must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda values: [member.value for member in values],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class Semester(TimestampMixin, Base):
    __tablename__ = "semesters"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_semester_bounds"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    templates: Mapped[list[BlockTemplate]] = relationship(back_populates="semester")
    occurrences: Mapped[list[BlockOccurrence]] = relationship(back_populates="semester")
    courses: Mapped[list[Course]] = relationship(back_populates="semester")


class BlockTemplate(TimestampMixin, Base):
    __tablename__ = "block_templates"
    __table_args__ = (
        UniqueConstraint("semester_id", "managed_dataset", "source_key", name="uq_template_source"),
        CheckConstraint("effective_end_date >= effective_start_date", name="ck_template_bounds"),
        CheckConstraint("duration_minutes > 0", name="ck_template_duration"),
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_template_priority"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    semester_id: Mapped[str] = mapped_column(
        ForeignKey("semesters.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[BlockCategory] = mapped_column(
        enum_type(BlockCategory, "block_category"), default=BlockCategory.CUSTOM
    )
    flexibility: Mapped[Flexibility] = mapped_column(
        enum_type(Flexibility, "block_flexibility"), default=Flexibility.FLEXIBLE
    )
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(500))
    weekdays: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    local_start_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    effective_start_date: Mapped[date] = mapped_column(Date)
    effective_end_date: Mapped[date] = mapped_column(Date)
    excluded_dates: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago")
    earliest_start_time: Mapped[time | None] = mapped_column(Time)
    latest_end_time: Mapped[time | None] = mapped_column(Time)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    preferred_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    minimum_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    may_split: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    calendar_projection: Mapped[bool] = mapped_column(Boolean, default=True)
    managed_dataset: Mapped[str | None] = mapped_column(String(100), index=True)
    source_key: Mapped[str | None] = mapped_column(String(300))
    content_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    semester: Mapped[Semester] = relationship(back_populates="templates")
    occurrences: Mapped[list[BlockOccurrence]] = relationship(back_populates="template")


class BlockOccurrence(TimestampMixin, Base):
    __tablename__ = "block_occurrences"
    __table_args__ = (
        UniqueConstraint("template_id", "occurrence_date", name="uq_template_occurrence_date"),
        UniqueConstraint(
            "semester_id", "managed_dataset", "source_key", name="uq_occurrence_source"
        ),
        CheckConstraint("planned_end_utc > planned_start_utc", name="ck_occurrence_planned_range"),
        CheckConstraint(
            "actual_end_utc IS NULL OR actual_start_utc IS NULL "
            "OR actual_end_utc >= actual_start_utc",
            name="ck_occurrence_actual_range",
        ),
        CheckConstraint("status != 'missed'", name="ck_occurrence_missed_is_derived"),
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_occurrence_priority"),
        Index("ix_occurrences_schedule", "semester_id", "planned_start_utc", "planned_end_utc"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    semester_id: Mapped[str] = mapped_column(
        ForeignKey("semesters.id", ondelete="RESTRICT"), index=True
    )
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("block_templates.id", ondelete="SET NULL"), index=True
    )
    occurrence_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[BlockCategory] = mapped_column(
        enum_type(BlockCategory, "block_category"), default=BlockCategory.CUSTOM
    )
    flexibility: Mapped[Flexibility] = mapped_column(
        enum_type(Flexibility, "block_flexibility"), default=Flexibility.FLEXIBLE
    )
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(500))
    planned_start_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    planned_end_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    actual_start_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    actual_end_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[TrackingStatus] = mapped_column(
        enum_type(TrackingStatus, "tracking_status"), default=TrackingStatus.PLANNED
    )
    notes: Mapped[str | None] = mapped_column(Text)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[int] = mapped_column(Integer, default=50)
    preferred_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    minimum_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    earliest_start_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    latest_end_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    may_split: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    calendar_projection: Mapped[bool] = mapped_column(Boolean, default=True)
    managed_dataset: Mapped[str | None] = mapped_column(String(100), index=True)
    source_key: Mapped[str | None] = mapped_column(String(300))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)

    semester: Mapped[Semester] = relationship(back_populates="occurrences")
    template: Mapped[BlockTemplate | None] = relationship(back_populates="occurrences")
    checklist_items: Mapped[list[ChecklistItem]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan", order_by="ChecklistItem.position"
    )
    meal_items: Mapped[list[MealItem]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan", order_by="MealItem.position"
    )
    workout_exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.position",
    )
    assignment_links: Mapped[list[AssignmentBlockLink]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan"
    )
    calendar_link: Mapped[CalendarEventLink | None] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan", uselist=False
    )

    def planned_nutrition(self) -> tuple[Decimal, Decimal]:
        calories = sum(
            (item.calories_per_unit * item.planned_quantity for item in self.meal_items),
            start=Decimal("0"),
        )
        protein = sum(
            (item.protein_grams_per_unit * item.planned_quantity for item in self.meal_items),
            start=Decimal("0"),
        )
        return calories, protein

    def consumed_nutrition(self) -> tuple[Decimal, Decimal]:
        consumed = [item for item in self.meal_items if item.completed_at is not None]
        calories = sum((item.consumed_calories for item in consumed), start=Decimal("0"))
        protein = sum((item.consumed_protein for item in consumed), start=Decimal("0"))
        return calories, protein


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    skipped_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    occurrence: Mapped[BlockOccurrence] = relationship(back_populates="checklist_items")


class MealItem(Base):
    __tablename__ = "meal_items"
    __table_args__ = (
        CheckConstraint("planned_quantity > 0", name="ck_meal_planned_quantity"),
        CheckConstraint(
            "consumed_quantity IS NULL OR consumed_quantity >= 0",
            name="ck_meal_consumed_quantity",
        ),
        CheckConstraint("calories_per_unit >= 0", name="ck_meal_calories"),
        CheckConstraint("protein_grams_per_unit >= 0", name="ck_meal_protein"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), index=True
    )
    food_name: Mapped[str] = mapped_column(String(300))
    unit: Mapped[str] = mapped_column(String(100), default="serving")
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    consumed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    calories_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    protein_grams_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    occurrence: Mapped[BlockOccurrence] = relationship(back_populates="meal_items")

    @property
    def effective_consumed_quantity(self) -> Decimal:
        return self.consumed_quantity or self.planned_quantity

    @property
    def consumed_calories(self) -> Decimal:
        return self.calories_per_unit * self.effective_consumed_quantity

    @property
    def consumed_protein(self) -> Decimal:
        return self.protein_grams_per_unit * self.effective_consumed_quantity


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (
        CheckConstraint("planned_sets > 0", name="ck_exercise_planned_sets"),
        CheckConstraint("rep_min IS NULL OR rep_min >= 0", name="ck_exercise_rep_min"),
        CheckConstraint("rep_max IS NULL OR rep_max >= rep_min", name="ck_exercise_rep_max"),
        CheckConstraint(
            "target_weight IS NULL OR target_weight >= 0", name="ck_exercise_target_weight"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer, default=0)
    planned_sets: Mapped[int] = mapped_column(Integer, default=1)
    rep_min: Mapped[int | None] = mapped_column(Integer)
    rep_max: Mapped[int | None] = mapped_column(Integer)
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    weight_unit: Mapped[str] = mapped_column(String(10), default="lb")
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    occurrence: Mapped[BlockOccurrence] = relationship(back_populates="workout_exercises")
    sets: Mapped[list[WorkoutSet]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="WorkoutSet.set_number"
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    __table_args__ = (
        UniqueConstraint("exercise_id", "set_number", name="uq_exercise_set_number"),
        CheckConstraint("set_number > 0", name="ck_workout_set_number"),
        CheckConstraint("actual_reps IS NULL OR actual_reps >= 0", name="ck_workout_actual_reps"),
        CheckConstraint(
            "actual_weight IS NULL OR actual_weight >= 0", name="ck_workout_actual_weight"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("workout_exercises.id", ondelete="CASCADE"), index=True
    )
    set_number: Mapped[int] = mapped_column(Integer)
    target_reps: Mapped[int | None] = mapped_column(Integer)
    actual_reps: Mapped[int | None] = mapped_column(Integer)
    actual_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("semester_id", "external_source", "external_id", name="uq_course_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    semester_id: Mapped[str] = mapped_column(
        ForeignKey("semesters.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(300))
    code: Mapped[str | None] = mapped_column(String(100))
    external_source: Mapped[str] = mapped_column(String(100), default="blackboard")
    external_id: Mapped[str | None] = mapped_column(String(500))

    semester: Mapped[Semester] = relationship(back_populates="courses")
    assignments: Mapped[list[Assignment]] = relationship(back_populates="course")


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint(
            "external_source", "external_uid", "recurrence_id", name="uq_assignment_source"
        ),
        CheckConstraint(
            "(due_precision = 'date' AND due_date IS NOT NULL) OR "
            "(due_precision = 'datetime' AND due_at_utc IS NOT NULL)",
            name="ck_assignment_due_value",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    external_source: Mapped[str] = mapped_column(String(100), default="blackboard")
    external_uid: Mapped[str] = mapped_column(String(500))
    recurrence_id: Mapped[str] = mapped_column(String(500), default="")
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    due_precision: Mapped[DuePrecision] = mapped_column(enum_type(DuePrecision, "due_precision"))
    due_date: Mapped[date | None] = mapped_column(Date)
    due_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    url: Mapped[str | None] = mapped_column(Text)
    source_state: Mapped[ExternalRecordState] = mapped_column(
        enum_type(ExternalRecordState, "external_record_state"),
        default=ExternalRecordState.ACTIVE,
    )
    inbox_status: Mapped[AssignmentInboxStatus] = mapped_column(
        enum_type(AssignmentInboxStatus, "assignment_inbox_status"),
        default=AssignmentInboxStatus.INBOX,
    )
    estimated_effort_minutes: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int | None] = mapped_column(Integer)
    source_dtstamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source_last_modified: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    source_changed: Mapped[bool] = mapped_column(Boolean, default=False)

    course: Mapped[Course | None] = relationship(back_populates="assignments")
    block_links: Mapped[list[AssignmentBlockLink]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )
    documents: Mapped[list[AssignmentDocument]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="AssignmentDocument.created_at",
    )
    study_set: Mapped[AssignmentStudySet | None] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        uselist=False,
    )


class AssignmentDocument(TimestampMixin, Base):
    __tablename__ = "assignment_documents"
    __table_args__ = (
        UniqueConstraint("assignment_id", "sha256", name="uq_assignment_document_hash"),
        CheckConstraint("size_bytes > 0", name="ck_assignment_document_size"),
        CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_assignment_document_pages",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    extracted_text: Mapped[str] = mapped_column(Text)
    extracted_character_count: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False)

    assignment: Mapped[Assignment] = relationship(back_populates="documents")


class AssignmentStudySet(TimestampMixin, Base):
    __tablename__ = "assignment_study_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), unique=True, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    generator: Mapped[str] = mapped_column(String(100), default="local-deterministic-v1")
    source_digest: Mapped[str] = mapped_column(String(64))
    source_metadata_json: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    summary: Mapped[str] = mapped_column(Text)
    key_points_json: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    questions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    assumptions_json: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    payload_digest: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    assignment: Mapped[Assignment] = relationship(back_populates="study_set")


class AssignmentBlockLink(Base):
    __tablename__ = "assignment_block_links"
    __table_args__ = (
        UniqueConstraint("assignment_id", "occurrence_id", name="uq_assignment_block_link"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), index=True
    )
    needs_replanning: Mapped[bool] = mapped_column(Boolean, default=False)

    assignment: Mapped[Assignment] = relationship(back_populates="block_links")
    occurrence: Mapped[BlockOccurrence] = relationship(back_populates="assignment_links")


class ImportDraft(Base):
    __tablename__ = "import_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    schema_version: Mapped[str] = mapped_column(String(20))
    mode: Mapped[ImportMode] = mapped_column(enum_type(ImportMode, "import_mode"))
    managed_dataset: Mapped[str] = mapped_column(String(100), index=True)
    semester_id: Mapped[str | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"), index=True
    )
    scope_start_date: Mapped[date] = mapped_column(Date)
    scope_end_date: Mapped[date] = mapped_column(Date)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON))
    source_filename: Mapped[str | None] = mapped_column(String(500))
    source_media_type: Mapped[str | None] = mapped_column(String(200))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    assumptions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    base_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[DraftStatus] = mapped_column(
        enum_type(DraftStatus, "draft_status"), default=DraftStatus.READY
    )
    warnings_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    changes: Mapped[list[ImportChange]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", order_by="ImportChange.position"
    )
    issues: Mapped[list[ImportIssue]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", order_by="ImportIssue.position"
    )


class ImportChange(Base):
    __tablename__ = "import_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("import_drafts.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    operation: Mapped[ChangeOperation] = mapped_column(
        enum_type(ChangeOperation, "change_operation")
    )
    entity_type: Mapped[ImportEntityType] = mapped_column(
        enum_type(ImportEntityType, "import_entity_type")
    )
    target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON))
    after_json: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON))
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    draft: Mapped[ImportDraft] = relationship(back_populates="changes")


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("import_drafts.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    severity: Mapped[IssueSeverity] = mapped_column(enum_type(IssueSeverity, "issue_severity"))
    code: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(500))
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)

    draft: Mapped[ImportDraft] = relationship(back_populates="issues")


class CalendarEventLink(Base):
    __tablename__ = "calendar_event_links"
    __table_args__ = (UniqueConstraint("calendar_id", "event_id", name="uq_calendar_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), unique=True, index=True
    )
    calendar_id: Mapped[str] = mapped_column(String(500))
    event_id: Mapped[str] = mapped_column(String(200))
    etag: Mapped[str | None] = mapped_column(String(500))
    last_synced_local_revision: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_start_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_synced_end_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    remote_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    occurrence: Mapped[BlockOccurrence] = relationship(back_populates="calendar_link")


class ExternalSourceState(Base):
    __tablename__ = "external_source_states"
    __table_args__ = (UniqueConstraint("connector", "source_key", name="uq_external_source"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[SyncConnector] = mapped_column(enum_type(SyncConnector, "sync_connector"))
    source_key: Mapped[str] = mapped_column(String(200), default="default")
    sync_token: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[SyncConnector] = mapped_column(enum_type(SyncConnector, "sync_connector"))
    status: Mapped[SyncStatus] = mapped_column(
        enum_type(SyncStatus, "sync_status"), default=SyncStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict)

    conflicts: Mapped[list[SyncConflict]] = relationship(
        back_populates="sync_run", cascade="all, delete-orphan"
    )


class SyncConflict(Base):
    __tablename__ = "sync_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sync_run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id", ondelete="CASCADE"))
    occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("block_occurrences.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SyncConflictStatus] = mapped_column(
        enum_type(SyncConflictStatus, "sync_conflict_status"),
        default=SyncConflictStatus.OPEN,
    )
    planner_start_utc: Mapped[datetime] = mapped_column(UTCDateTime())
    planner_end_utc: Mapped[datetime] = mapped_column(UTCDateTime())
    remote_start_utc: Mapped[datetime] = mapped_column(UTCDateTime())
    remote_end_utc: Mapped[datetime] = mapped_column(UTCDateTime())
    base_start_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    base_end_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    sync_run: Mapped[SyncRun] = relationship(back_populates="conflicts")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String(100), default="user")
    data_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_singleton_app_settings"),
        CheckConstraint("missed_grace_minutes >= 0", name="ck_missed_grace"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_semester_id: Mapped[str | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL")
    )
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago")
    operational_day_boundary: Mapped[time] = mapped_column(Time, default=time(hour=4))
    missed_grace_minutes: Mapped[int] = mapped_column(Integer, default=30)
    weight_unit: Mapped[str] = mapped_column(String(10), default="lb")
    calorie_target: Mapped[int | None] = mapped_column(Integer)
    protein_target_grams: Mapped[int | None] = mapped_column(Integer)
    blackboard_ics_url: Mapped[str | None] = mapped_column(Text)
    google_calendar_id: Mapped[str | None] = mapped_column(String(500))
    schedule_revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
