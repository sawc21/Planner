from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Protocol

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from semester_ops.application.common import add_audit_event
from semester_ops.application.errors import (
    IdempotencyConflictError,
    NotFoundError,
    ValidationError,
)
from semester_ops.application.study_contract import (
    assignment_study_payload_digest,
    assignment_study_source_digest,
    parse_assignment_study_payload,
)
from semester_ops.db.models import (
    Assignment,
    AssignmentDocument,
    AssignmentStudySet,
    AuditEvent,
)

MAX_ASSIGNMENT_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_ASSIGNMENT_DOCUMENTS = 20
MAX_ASSIGNMENT_DOCUMENT_TOTAL_BYTES = 50 * 1024 * 1024
MAX_ASSIGNMENT_UPLOAD_REQUEST_BYTES = MAX_ASSIGNMENT_DOCUMENT_BYTES + 256 * 1024
MAX_EXTRACTED_CHARACTERS = 250_000
MAX_PDF_PAGES = 100

_MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}
_ACCEPTED_UPLOAD_MEDIA_TYPES = {
    ".txt": {"text/plain", "application/octet-stream", ""},
    ".md": {"text/markdown", "text/plain", "application/octet-stream", ""},
    ".pdf": {"application/pdf", "application/octet-stream", ""},
}
_SENTENCE_SPLIT: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
_WORD: re.Pattern[str] = re.compile(r"[A-Za-z][A-Za-z0-9'-]{2,}")
_STOPWORDS = {
    "and",
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "between",
    "could",
    "does",
    "from",
    "for",
    "have",
    "into",
    "more",
    "most",
    "other",
    "should",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "using",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    filename: str
    media_type: str
    text: str
    page_count: int | None
    is_truncated: bool


@dataclass(frozen=True, slots=True)
class StudySource:
    document_id: str
    filename: str
    text: str
    sha256: str


@dataclass(frozen=True, slots=True)
class GeneratedQuestion:
    id: str
    prompt: str
    choices: tuple[str, ...]
    correct_answer: str
    explanation: str
    source_document_id: str
    source_filename: str

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "choices": list(self.choices),
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "source_document_id": self.source_document_id,
            "source_filename": self.source_filename,
        }


@dataclass(frozen=True, slots=True)
class GeneratedStudyMaterial:
    summary: str
    key_points: tuple[str, ...]
    questions: tuple[GeneratedQuestion, ...]
    generator: str = "local-deterministic-v1"
    schema_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class QuizResult:
    correct_count: int
    question_count: int
    answers: dict[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class StudySubmissionResult:
    study_set: AssignmentStudySet
    status: str
    payload_digest: str
    source_digest: str


class DocumentTextExtractor(Protocol):
    def extract(self, filename: str, media_type: str | None, content: bytes) -> ExtractedDocument:
        """Validate an upload and return normalized, locally extracted text."""


class StudyMaterialGenerator(Protocol):
    def generate(self, sources: Sequence[StudySource]) -> GeneratedStudyMaterial:
        """Return the stable JSON-shaped contract used by local or future AI generators."""


class LocalDocumentTextExtractor:
    def extract(self, filename: str, media_type: str | None, content: bytes) -> ExtractedDocument:
        safe_filename = self._safe_filename(filename)
        extension = PurePosixPath(safe_filename.lower()).suffix
        if extension not in _MEDIA_TYPES:
            raise ValidationError("Upload a PDF, TXT, or Markdown file.")
        if not content:
            raise ValidationError("The uploaded document is empty.")
        if len(content) > MAX_ASSIGNMENT_DOCUMENT_BYTES:
            raise ValidationError("Assignment documents must be 5 MB or smaller.")

        submitted_type = (media_type or "").split(";", maxsplit=1)[0].strip().lower()
        if submitted_type not in _ACCEPTED_UPLOAD_MEDIA_TYPES[extension]:
            raise ValidationError(
                f"The file type {submitted_type or 'unknown'} does not match {extension}."
            )

        page_count: int | None = None
        extraction_truncated = False
        if extension == ".pdf":
            text, page_count, extraction_truncated = self._extract_pdf(content)
        else:
            text = self._extract_utf8_text(content)
        normalized = _normalize_text(text)
        if not normalized:
            if extension == ".pdf":
                raise ValidationError(
                    "No selectable text was found. Image-only PDFs need OCR before upload."
                )
            raise ValidationError("The uploaded document contains no readable text.")
        is_truncated = extraction_truncated or len(normalized) > MAX_EXTRACTED_CHARACTERS
        normalized = normalized[:MAX_EXTRACTED_CHARACTERS]
        return ExtractedDocument(
            filename=safe_filename,
            media_type=_MEDIA_TYPES[extension],
            text=normalized,
            page_count=page_count,
            is_truncated=is_truncated,
        )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
        basename = PurePosixPath(normalized).name.strip()
        if not basename or basename in {".", ".."}:
            raise ValidationError("The uploaded document needs a filename.")
        if len(basename) > 255 or any(ord(character) < 32 for character in basename):
            raise ValidationError("The uploaded filename is not valid.")
        return basename

    @staticmethod
    def _extract_utf8_text(content: bytes) -> str:
        if b"\x00" in content:
            raise ValidationError("TXT and Markdown uploads must contain UTF-8 text.")
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("TXT and Markdown uploads must use UTF-8 encoding.") from exc

    @staticmethod
    def _extract_pdf(content: bytes) -> tuple[str, int, bool]:
        if not content.startswith(b"%PDF-"):
            raise ValidationError("The uploaded PDF does not have a valid PDF header.")
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise ValidationError("Password-protected PDFs are not supported.")
            page_count = len(reader.pages)
            if page_count == 0:
                raise ValidationError("The uploaded PDF has no pages.")
            if page_count > MAX_PDF_PAGES:
                raise ValidationError("Assignment PDFs may contain at most 100 pages.")
            pieces: list[str] = []
            remaining = MAX_EXTRACTED_CHARACTERS + 1
            is_truncated = False
            for page in reader.pages:
                page_text = page.extract_text() or ""
                piece = ("\n\n" if pieces else "") + page_text
                if len(piece) >= remaining:
                    pieces.append(piece[:remaining])
                    is_truncated = True
                    break
                pieces.append(piece)
                remaining -= len(piece)
            return "".join(pieces), page_count, is_truncated
        except ValidationError:
            raise
        except (PdfReadError, ValueError, OSError) as exc:
            raise ValidationError("The uploaded PDF could not be read.") from exc


class LocalStudyMaterialGenerator:
    """Deterministic offline fallback matching the future AI/MCP output boundary."""

    def generate(self, sources: Sequence[StudySource]) -> GeneratedStudyMaterial:
        if not sources:
            raise ValidationError("Upload at least one document before generating a quiz.")
        sentence_rows = self._sentences(sources)
        if not sentence_rows:
            raise ValidationError("The uploaded documents do not contain enough text for a quiz.")

        all_terms = self._ranked_terms(" ".join(row[1] for row in sentence_rows))
        questions: list[GeneratedQuestion] = []
        for source, sentence in sentence_rows:
            answer = self._answer_term(sentence)
            if answer is None:
                continue
            distractors = [term for term in all_terms if term.casefold() != answer.casefold()][:9]
            choices = self._choices(answer, distractors, sentence)
            prompt = re.sub(
                rf"\b{re.escape(answer)}\b",
                "_____",
                sentence,
                count=1,
                flags=re.IGNORECASE,
            )
            question_id = hashlib.sha256(
                f"{source.document_id}\0{sentence}\0{answer}".encode()
            ).hexdigest()[:12]
            questions.append(
                GeneratedQuestion(
                    id=question_id,
                    prompt=f"Complete the statement: {prompt}",
                    choices=choices,
                    correct_answer=answer,
                    explanation=sentence,
                    source_document_id=source.document_id,
                    source_filename=source.filename,
                )
            )
            if len(questions) == 5:
                break
        if not questions:
            raise ValidationError("The uploaded documents do not contain enough terms for a quiz.")

        key_points = tuple(sentence for _, sentence in sentence_rows[:5])
        summary = " ".join(key_points[:2])
        return GeneratedStudyMaterial(
            summary=summary,
            key_points=key_points,
            questions=tuple(questions),
        )

    @staticmethod
    def _sentences(sources: Sequence[StudySource]) -> list[tuple[StudySource, str]]:
        result: list[tuple[StudySource, str]] = []
        seen: set[str] = set()
        for source in sources:
            pieces = [_clean_sentence(piece) for piece in _SENTENCE_SPLIT.split(source.text)]
            eligible = [
                piece
                for piece in pieces
                if 30 <= len(piece) <= 280 and len(_WORD.findall(piece)) >= 5
            ]
            if not eligible:
                fallback = _clean_sentence(source.text[:280])
                if fallback:
                    eligible = [fallback]
            for sentence in eligible:
                identity = sentence.casefold()
                if identity in seen:
                    continue
                seen.add(identity)
                result.append((source, sentence))
        return result

    @staticmethod
    def _ranked_terms(text: str) -> list[str]:
        words = [word for word in _WORD.findall(text) if word.casefold() not in _STOPWORDS]
        frequencies = Counter(word.casefold() for word in words)
        display = {word.casefold(): word for word in words}
        ranked = sorted(frequencies, key=lambda word: (-frequencies[word], -len(word), word))
        return [display[word] for word in ranked]

    @staticmethod
    def _answer_term(sentence: str) -> str | None:
        terms: list[str] = [
            str(word) for word in _WORD.findall(sentence) if str(word).casefold() not in _STOPWORDS
        ]
        if not terms:
            return None
        return sorted(terms, key=lambda word: (-len(word), word.casefold()))[0]

    @staticmethod
    def _choices(answer: str, distractors: Sequence[str], sentence: str) -> tuple[str, ...]:
        selected = [answer]
        for candidate in distractors:
            if candidate.casefold() not in {choice.casefold() for choice in selected}:
                selected.append(candidate)
            if len(selected) == 4:
                break
        if len(selected) == 1:
            selected.append("Not stated")
        return tuple(
            sorted(
                selected,
                key=lambda choice: hashlib.sha256(f"{sentence}\0{choice}".encode()).hexdigest(),
            )
        )


class AssignmentStudyService:
    def __init__(
        self,
        session: Session,
        *,
        extractor: DocumentTextExtractor | None = None,
        generator: StudyMaterialGenerator | None = None,
    ) -> None:
        self.session = session
        self.extractor = extractor or LocalDocumentTextExtractor()
        self.generator = generator or LocalStudyMaterialGenerator()

    def get_assignment(self, assignment_id: str) -> Assignment:
        assignment = self.session.scalar(
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .options(
                selectinload(Assignment.course),
                selectinload(Assignment.documents).load_only(
                    AssignmentDocument.id,
                    AssignmentDocument.assignment_id,
                    AssignmentDocument.original_filename,
                    AssignmentDocument.media_type,
                    AssignmentDocument.size_bytes,
                    AssignmentDocument.extracted_character_count,
                    AssignmentDocument.page_count,
                    AssignmentDocument.is_truncated,
                    AssignmentDocument.created_at,
                ),
                selectinload(Assignment.study_set),
            )
            .execution_options(populate_existing=True)
        )
        if assignment is None:
            raise NotFoundError(f"assignment {assignment_id} was not found")
        return assignment

    def upload_document(
        self,
        assignment_id: str,
        *,
        filename: str,
        media_type: str | None,
        content: bytes,
    ) -> AssignmentDocument:
        self.get_assignment(assignment_id)
        document_count, total_bytes = self.session.execute(
            select(
                func.count(AssignmentDocument.id),
                func.coalesce(func.sum(AssignmentDocument.size_bytes), 0),
            ).where(AssignmentDocument.assignment_id == assignment_id)
        ).one()
        if int(document_count) >= MAX_ASSIGNMENT_DOCUMENTS:
            raise ValidationError(
                f"An assignment may have at most {MAX_ASSIGNMENT_DOCUMENTS} documents."
            )
        if int(total_bytes) + len(content) > MAX_ASSIGNMENT_DOCUMENT_TOTAL_BYTES:
            raise ValidationError("Assignment documents may use at most 50 MB in total.")
        digest = hashlib.sha256(content).hexdigest()
        duplicate = self.session.scalar(
            select(AssignmentDocument.id).where(
                AssignmentDocument.assignment_id == assignment_id,
                AssignmentDocument.sha256 == digest,
            )
        )
        if duplicate is not None:
            raise ValidationError("This document is already attached to the assignment.")
        extracted = self.extractor.extract(filename, media_type, content)
        document = AssignmentDocument(
            assignment_id=assignment_id,
            original_filename=extracted.filename,
            media_type=extracted.media_type,
            size_bytes=len(content),
            sha256=digest,
            content_bytes=content,
            extracted_text=extracted.text,
            extracted_character_count=len(extracted.text),
            page_count=extracted.page_count,
            is_truncated=extracted.is_truncated,
        )
        with self.session.begin_nested():
            self.session.add(document)
            self.session.flush()
            self.regenerate(assignment_id)
        return document

    def regenerate(self, assignment_id: str) -> AssignmentStudySet:
        self.get_assignment(assignment_id)
        documents = list(
            self.session.scalars(
                select(AssignmentDocument)
                .where(AssignmentDocument.assignment_id == assignment_id)
                .options(
                    load_only(
                        AssignmentDocument.id,
                        AssignmentDocument.original_filename,
                        AssignmentDocument.media_type,
                        AssignmentDocument.extracted_text,
                        AssignmentDocument.sha256,
                    )
                )
                .order_by(AssignmentDocument.created_at, AssignmentDocument.id)
            )
        )
        sources = [
            StudySource(
                document_id=document.id,
                filename=document.original_filename,
                text=document.extracted_text,
                sha256=document.sha256,
            )
            for document in documents
        ]
        material = self.generator.generate(sources)
        source_digest = hashlib.sha256(
            "\0".join(source.sha256 for source in sources).encode()
        ).hexdigest()
        study_set = self.session.scalar(
            select(AssignmentStudySet).where(AssignmentStudySet.assignment_id == assignment_id)
        )
        if study_set is None:
            study_set = AssignmentStudySet(assignment_id=assignment_id, source_digest=source_digest)
            self.session.add(study_set)
        study_set.schema_version = material.schema_version
        study_set.generator = material.generator
        study_set.source_digest = source_digest
        study_set.source_metadata_json = [
            {
                "id": document.id,
                "filename": document.original_filename,
                "media_type": document.media_type,
                "sha256": document.sha256,
            }
            for document in documents
        ]
        study_set.summary = material.summary
        study_set.key_points_json = list(material.key_points)
        study_set.questions_json = [question.as_json() for question in material.questions]
        study_set.assumptions_json = []
        study_set.payload_digest = None
        study_set.generated_at = datetime.now(UTC)
        self.session.flush()
        return study_set

    def submit_json(
        self,
        assignment_id: str,
        *,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> StudySubmissionResult:
        self.get_assignment(assignment_id)
        key = idempotency_key.strip()
        if not key:
            raise ValidationError("idempotency_key cannot be blank")
        if len(key) > 200:
            raise ValidationError("idempotency_key cannot exceed 200 characters")

        parsed = parse_assignment_study_payload(payload)
        payload_digest = assignment_study_payload_digest(parsed)
        source_digest = assignment_study_source_digest(parsed)
        previous_events = self.session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "assignment.study.submitted",
                AuditEvent.entity_type == "assignment",
                AuditEvent.entity_id == assignment_id,
            )
            .order_by(AuditEvent.occurred_at.desc())
        )
        previous = next(
            (event for event in previous_events if event.data_json.get("idempotency_key") == key),
            None,
        )
        if previous is not None:
            if previous.data_json.get("payload_digest") != payload_digest:
                raise IdempotencyConflictError(
                    "The study idempotency key was already used for different JSON."
                )
            current = self.session.scalar(
                select(AssignmentStudySet).where(AssignmentStudySet.assignment_id == assignment_id)
            )
            if current is None:
                raise ValidationError("The previously submitted study set is no longer available.")
            status = "duplicate" if current.payload_digest == payload_digest else "superseded"
            return StudySubmissionResult(current, status, payload_digest, source_digest)

        study_set = self.session.scalar(
            select(AssignmentStudySet).where(AssignmentStudySet.assignment_id == assignment_id)
        )
        status = "updated"
        if study_set is None:
            study_set = AssignmentStudySet(assignment_id=assignment_id, source_digest=source_digest)
            self.session.add(study_set)
            status = "created"

        sources_by_id = {source.id: source for source in parsed.sources}
        study_set.schema_version = parsed.schema_version
        study_set.generator = "codex-mcp-v1"
        study_set.source_digest = source_digest
        study_set.source_metadata_json = [
            source.model_dump(mode="json") for source in parsed.sources
        ]
        study_set.summary = parsed.summary
        study_set.key_points_json = list(parsed.key_points)
        study_set.questions_json = [
            {
                "id": question.id,
                "prompt": question.prompt,
                "choices": list(question.choices),
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "source_document_id": question.source_id,
                "source_filename": sources_by_id[question.source_id].filename,
            }
            for question in parsed.questions
        ]
        study_set.assumptions_json = list(parsed.assumptions)
        study_set.payload_digest = payload_digest
        study_set.generated_at = datetime.now(UTC)
        self.session.flush()
        add_audit_event(
            self.session,
            event_type="assignment.study.submitted",
            entity_type="assignment",
            entity_id=assignment_id,
            actor="codex-mcp",
            data={
                "idempotency_key": key,
                "payload_digest": payload_digest,
                "source_digest": source_digest,
                "study_set_id": study_set.id,
                "source_filenames": [source.filename for source in parsed.sources],
            },
        )
        self.session.flush()
        return StudySubmissionResult(study_set, status, payload_digest, source_digest)

    def get_document(self, assignment_id: str, document_id: str) -> AssignmentDocument:
        document = self.session.scalar(
            select(AssignmentDocument)
            .where(
                AssignmentDocument.id == document_id,
                AssignmentDocument.assignment_id == assignment_id,
            )
            .options(
                load_only(
                    AssignmentDocument.id,
                    AssignmentDocument.original_filename,
                    AssignmentDocument.media_type,
                    AssignmentDocument.content_bytes,
                )
            )
        )
        if document is None:
            raise NotFoundError(
                f"document {document_id} was not found on assignment {assignment_id}"
            )
        return document

    def check_quiz(self, assignment_id: str, answers: Mapping[str, str]) -> QuizResult:
        assignment = self.get_assignment(assignment_id)
        if assignment.study_set is None:
            raise ValidationError("Upload a document before checking a quiz.")
        checked: dict[str, dict[str, Any]] = {}
        correct_count = 0
        for question in assignment.study_set.questions_json:
            question_id = str(question["id"])
            selected = answers.get(question_id)
            if selected is None or not selected.strip():
                continue
            choices = [str(choice) for choice in question["choices"]]
            if selected not in choices:
                raise ValidationError(
                    "A submitted quiz answer is not one of the available choices."
                )
            correct_answer = str(question["correct_answer"])
            is_correct = selected.casefold() == correct_answer.casefold()
            correct_count += int(is_correct)
            checked[question_id] = {
                "selected": selected,
                "correct": is_correct,
                "correct_answer": correct_answer,
                "explanation": str(question["explanation"]),
            }
        if not checked:
            raise ValidationError("Select at least one answer before checking the quiz.")
        return QuizResult(correct_count, len(checked), checked)


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\x00", "")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -*#\t")
