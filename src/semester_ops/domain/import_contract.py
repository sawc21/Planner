from datetime import date, time
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from semester_ops.domain.enums import (
    BlockCategory,
    ChangeOperation,
    Flexibility,
    ImportEntityType,
    ImportMode,
)

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceMetadata(ContractModel):
    filename: str | None = Field(default=None, max_length=500)
    media_type: str | None = Field(default=None, max_length=200)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    description: str | None = Field(default=None, max_length=2_000)


class SemesterInput(ContractModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    timezone: Literal["America/Chicago"] = "America/Chicago"

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("semester end_date must be on or after start_date")
        return self


class ImportScope(ContractModel):
    semester_id: str | None = None
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("scope end_date must be on or after start_date")
        return self


class ChecklistInput(ContractModel):
    title: str = Field(min_length=1, max_length=300)
    required: bool = True
    position: int = Field(default=0, ge=0)


class MealItemInput(ContractModel):
    food_name: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="serving", min_length=1, max_length=100)
    planned_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    calories_per_unit: Decimal = Field(default=Decimal("0"), ge=0)
    protein_grams_per_unit: Decimal = Field(default=Decimal("0"), ge=0)
    required: bool = True
    position: int = Field(default=0, ge=0)


class WorkoutSetInput(ContractModel):
    set_number: int = Field(ge=1)
    target_reps: int | None = Field(default=None, ge=0)


class WorkoutExerciseInput(ContractModel):
    name: str = Field(min_length=1, max_length=300)
    planned_sets: int = Field(default=1, ge=1, le=100)
    rep_min: int | None = Field(default=None, ge=0)
    rep_max: int | None = Field(default=None, ge=0)
    target_weight: Decimal | None = Field(default=None, ge=0)
    weight_unit: Literal["lb", "kg"] = "lb"
    required: bool = True
    position: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=2_000)
    sets: list[WorkoutSetInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_reps_and_sets(self) -> Self:
        if self.rep_min is not None and self.rep_max is not None and self.rep_max < self.rep_min:
            raise ValueError("rep_max must be greater than or equal to rep_min")
        if self.sets and len({item.set_number for item in self.sets}) != len(self.sets):
            raise ValueError("workout set numbers must be unique within an exercise")
        return self


class BlockInput(ContractModel):
    source_key: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=300)
    category: BlockCategory = BlockCategory.CUSTOM
    flexibility: Flexibility = Flexibility.FLEXIBLE
    description: str | None = Field(default=None, max_length=10_000)
    location: str | None = Field(default=None, max_length=500)
    priority: int = Field(default=50, ge=0, le=100)
    preferred_duration_minutes: int | None = Field(default=None, ge=1, le=10_080)
    minimum_duration_minutes: int | None = Field(default=None, ge=1, le=10_080)
    may_split: bool = False
    requires_completion: bool = True
    calendar_projection: bool = True
    checklist_items: list[ChecklistInput] = Field(default_factory=list)
    meal_items: list[MealItemInput] = Field(default_factory=list)
    workout_exercises: list[WorkoutExerciseInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_durations(self) -> Self:
        if (
            self.minimum_duration_minutes is not None
            and self.preferred_duration_minutes is not None
            and self.minimum_duration_minutes > self.preferred_duration_minutes
        ):
            raise ValueError("minimum_duration_minutes cannot exceed preferred_duration_minutes")
        return self


class TemplateInput(BlockInput):
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_time: time
    duration_minutes: int = Field(ge=1, le=10_080)
    effective_start_date: date
    effective_end_date: date
    excluded_dates: list[date] = Field(default_factory=list)
    earliest_start_time: time | None = None
    latest_end_time: time | None = None

    @model_validator(mode="after")
    def valid_recurrence(self) -> Self:
        if self.effective_end_date < self.effective_start_date:
            raise ValueError("template effective_end_date must be on or after effective_start_date")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("template weekdays must be unique")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("template weekdays use Monday=0 through Sunday=6")
        if any(
            value < self.effective_start_date or value > self.effective_end_date
            for value in self.excluded_dates
        ):
            raise ValueError("excluded_dates must fall inside the template effective range")
        return self


class OccurrenceInput(BlockInput):
    occurrence_date: date
    start_time: time
    duration_minutes: int = Field(ge=1, le=10_080)
    earliest_start_time: time | None = None
    latest_end_time: time | None = None
    template_source_key: str | None = Field(default=None, max_length=300)
    assignment_ids: list[str] = Field(default_factory=list)


class PatchOperation(ContractModel):
    operation: ChangeOperation
    entity_type: ImportEntityType
    target_id: str | None = None
    target_source_key: str | None = Field(default=None, max_length=300)
    value: dict[str, Any] | None = None

    @model_validator(mode="after")
    def valid_target_and_value(self) -> Self:
        if self.entity_type is ImportEntityType.SEMESTER:
            raise ValueError("semester patch operations are not supported")
        if self.operation is ChangeOperation.ADD:
            if self.value is None:
                raise ValueError("add operations require value")
        elif self.target_id is None and self.target_source_key is None:
            raise ValueError("update and cancel operations require a target")
        if self.operation is ChangeOperation.UPDATE and self.value is None:
            raise ValueError("update operations require value")
        if self.operation is ChangeOperation.CANCEL and self.value is not None:
            raise ValueError("cancel operations cannot include value")
        return self


class UnresolvedField(ContractModel):
    path: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2_000)


class ImportPayload(ContractModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    mode: ImportMode
    managed_dataset: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")
    idempotency_key: str = Field(min_length=8, max_length=200)
    base_revision: int = Field(ge=0)
    scope: ImportScope
    semester: SemesterInput | None = None
    source: SourceMetadata = Field(default_factory=SourceMetadata)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_fields: list[UnresolvedField] = Field(default_factory=list)
    templates: list[TemplateInput] = Field(default_factory=list)
    occurrences: list[OccurrenceInput] = Field(default_factory=list)
    operations: list[PatchOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_mode_and_scope(self) -> Self:
        if self.scope.semester_id is None and self.semester is None:
            raise ValueError("scope.semester_id or semester is required")
        if self.semester is not None:
            if self.scope.semester_id is not None and self.semester.id not in {
                None,
                self.scope.semester_id,
            }:
                raise ValueError("semester.id must match scope.semester_id")
            if (
                self.scope.start_date < self.semester.start_date
                or self.scope.end_date > self.semester.end_date
            ):
                raise ValueError("scope must be inside semester bounds")
        if self.mode is ImportMode.REPLACE_SCOPE:
            if self.operations:
                raise ValueError("replace_scope cannot include operations")
            if not self.templates and not self.occurrences:
                raise ValueError("replace_scope requires templates or occurrences")
        else:
            if self.templates or self.occurrences:
                raise ValueError("patch uses operations instead of top-level schedule records")
            if not self.operations:
                raise ValueError("patch requires at least one operation")
        for template in self.templates:
            if (
                template.effective_start_date < self.scope.start_date
                or template.effective_end_date > self.scope.end_date
            ):
                raise ValueError("template effective range must stay inside the import scope")
        for occurrence in self.occurrences:
            if not self.scope.start_date <= occurrence.occurrence_date <= self.scope.end_date:
                raise ValueError("occurrence_date must stay inside the import scope")
        return self
