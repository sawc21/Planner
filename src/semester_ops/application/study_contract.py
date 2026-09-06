from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic import ValidationError as PydanticValidationError

from semester_ops.application.errors import ValidationError

STUDY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_STUDY_SOURCES = 20
MAX_STUDY_QUESTIONS = 20

KeyPoint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
Assumption = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Choice = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class StudySourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=3, max_length=100, pattern=r"^[^\s/]+/[^\s/]+$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        basename = PurePosixPath(normalized).name.strip()
        if basename != normalized or basename in {".", ".."}:
            raise ValueError("filename must be a plain basename without a path")
        if any(ord(character) < 32 for character in basename):
            raise ValueError("filename contains control characters")
        return basename


class StudyQuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    prompt: str = Field(min_length=1, max_length=1_000)
    choices: list[Choice] = Field(min_length=2, max_length=6)
    correct_answer: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=1_500)
    source_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @model_validator(mode="after")
    def validate_choices(self) -> StudyQuestionPayload:
        normalized = [choice.casefold() for choice in self.choices]
        if len(normalized) != len(set(normalized)):
            raise ValueError("choices must be unique")
        if self.correct_answer not in self.choices:
            raise ValueError("correct_answer must exactly match one choice")
        return self


class AssignmentStudyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"] = STUDY_SCHEMA_VERSION
    sources: list[StudySourcePayload] = Field(min_length=1, max_length=MAX_STUDY_SOURCES)
    summary: str = Field(min_length=1, max_length=4_000)
    key_points: list[KeyPoint] = Field(min_length=1, max_length=12)
    questions: list[StudyQuestionPayload] = Field(
        min_length=1,
        max_length=MAX_STUDY_QUESTIONS,
    )
    assumptions: list[Assumption] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_references(self) -> AssignmentStudyPayload:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question ids must be unique")
        unknown_sources = {
            question.source_id
            for question in self.questions
            if question.source_id not in source_ids
        }
        if unknown_sources:
            raise ValueError(
                "every question source_id must identify a submitted source: "
                + ", ".join(sorted(unknown_sources))
            )
        return self


def parse_assignment_study_payload(payload: dict[str, Any]) -> AssignmentStudyPayload:
    try:
        return AssignmentStudyPayload.model_validate(payload)
    except PydanticValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValidationError(f"Assignment study JSON is invalid: {messages}") from exc


def assignment_study_payload_digest(payload: AssignmentStudyPayload) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assignment_study_source_digest(payload: AssignmentStudyPayload) -> str:
    canonical_sources = json.dumps(
        sorted(
            (source.model_dump(mode="json") for source in payload.sources),
            key=lambda source: (str(source["id"]), str(source["sha256"])),
        ),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_sources.encode("utf-8")).hexdigest()


def assignment_study_schema() -> dict[str, Any]:
    return {
        "schema_version": STUDY_SCHEMA_VERSION,
        "payload_schema": AssignmentStudyPayload.model_json_schema(),
        "workflow": [
            "Keep the original attachment in the AI host; do not send raw document text.",
            "Include filename, media_type, and SHA-256 provenance for every source.",
            "Submit only the validated study payload for one known assignment id.",
            "Reuse an idempotency key only when retrying the identical payload.",
        ],
        "idempotency_key": {"min_length": 1, "max_length": 200},
    }
