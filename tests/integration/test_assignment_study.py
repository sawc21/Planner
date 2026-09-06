from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from semester_ops.application.errors import (
    IdempotencyConflictError,
    NotFoundError,
    ValidationError,
)
from semester_ops.application.facade import SemesterOpsService
from semester_ops.application.study import (
    MAX_ASSIGNMENT_DOCUMENT_BYTES,
    MAX_ASSIGNMENT_DOCUMENTS,
    AssignmentStudyService,
    LocalDocumentTextExtractor,
)
from semester_ops.db.base import Base
from semester_ops.db.models import Assignment, AssignmentDocument, AssignmentStudySet, AuditEvent
from semester_ops.db.session import create_sqlite_engine
from semester_ops.domain.enums import DuePrecision
from semester_ops.web.services import AssignmentDocumentUploadCommand


def test_text_upload_builds_scoped_study_material_and_checks_answers(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        assignment = _assignment("assignment-one", "Cell energy review")
        other_assignment = _assignment("assignment-two", "Database review")
        session.add_all((assignment, other_assignment))
        session.commit()
        service = SemesterOpsService(session)

        service.upload_assignment_document(
            assignment.id,
            AssignmentDocumentUploadCommand(
                filename="../week-one-notes.txt",
                media_type="text/plain",
                content=(
                    b"Photosynthesis converts light energy into chemical energy stored in glucose. "
                    b"Cellular respiration releases usable energy from glucose through a series of "
                    b"controlled reactions. Mitochondria produce most cellular ATP during aerobic "
                    b"respiration."
                ),
            ),
        )

        view = service.get_assignment_study(assignment.id)
        assert view["documents"][0]["filename"] == "week-one-notes.txt"
        assert view["study"]["questions"]
        assert "correct_answer" not in view["study"]["questions"][0]
        document_id = view["documents"][0]["id"]
        download = service.get_assignment_document(assignment.id, document_id)
        assert download.media_type == "text/plain"
        assert b"Photosynthesis" in download.content

        with pytest.raises(NotFoundError):
            service.get_assignment_document(other_assignment.id, document_id)

        study_set = session.scalar(
            select(AssignmentStudySet).where(AssignmentStudySet.assignment_id == assignment.id)
        )
        assert study_set is not None
        first_question = study_set.questions_json[0]
        checked = service.check_assignment_quiz(
            assignment.id,
            {str(first_question["id"]): str(first_question["correct_answer"])},
        )
        assert checked["quiz_result"]["correct_count"] == 1
        assert checked["quiz_result"]["question_count"] == 1
        feedback = checked["study"]["questions"][0]["feedback"]
        assert feedback["correct"] is True
        assert feedback["correct_answer"] == first_question["correct_answer"]
        for unanswered in checked["study"]["questions"][1:]:
            assert "feedback" not in unanswered

        with pytest.raises(ValidationError, match="Select at least one"):
            service.check_assignment_quiz(assignment.id, {})
        with pytest.raises(ValidationError, match="available choices"):
            service.check_assignment_quiz(
                assignment.id,
                {str(first_question["id"]): "A forged answer"},
            )


def test_duplicate_and_invalid_uploads_leave_no_partial_records(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        assignment = _assignment("assignment-one", "Network layers")
        session.add(assignment)
        session.commit()
        service = SemesterOpsService(session)
        command = AssignmentDocumentUploadCommand(
            filename="layers.md",
            media_type="text/markdown",
            content=(
                b"The transport layer provides end-to-end communication between application "
                b"processes on different hosts. Reliable delivery requires acknowledgements and "
                b"retransmission when packets are lost."
            ),
        )

        service.upload_assignment_document(assignment.id, command)
        with pytest.raises(ValidationError, match="already attached"):
            service.upload_assignment_document(assignment.id, command)
        with pytest.raises(ValidationError, match="PDF, TXT, or Markdown"):
            service.upload_assignment_document(
                assignment.id,
                AssignmentDocumentUploadCommand(
                    filename="instructions.exe",
                    media_type="application/octet-stream",
                    content=b"not a document",
                ),
            )

        assert session.scalar(select(func.count()).select_from(AssignmentDocument)) == 1
        assert session.scalar(select(func.count()).select_from(AssignmentStudySet)) == 1


def test_pdf_text_is_extracted_and_spoofed_pdf_is_rejected() -> None:
    extractor = LocalDocumentTextExtractor()

    extracted = extractor.extract("lecture.pdf", "application/pdf", _text_pdf())

    assert extracted.page_count == 1
    assert "Photosynthesis converts sunlight" in extracted.text
    with pytest.raises(ValidationError, match="valid PDF header"):
        extractor.extract("spoofed.pdf", "application/pdf", b"not really a pdf")


def test_pdf_extraction_stops_after_the_text_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    class OversizedPage:
        def extract_text(self) -> str:
            return "x" * 250_001

    class PageThatMustNotBeRead:
        def extract_text(self) -> str:
            raise AssertionError("PDF extraction continued after reaching the text budget")

    class Reader:
        is_encrypted = False

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.pages = [OversizedPage(), PageThatMustNotBeRead()]

    monkeypatch.setattr("semester_ops.application.study.PdfReader", Reader)

    extracted = LocalDocumentTextExtractor().extract(
        "large.pdf",
        "application/pdf",
        b"%PDF-placeholder",
    )

    assert len(extracted.text) == 250_000
    assert extracted.is_truncated is True
    assert extracted.page_count == 2


def test_upload_size_is_capped_before_extraction() -> None:
    extractor = LocalDocumentTextExtractor()

    with pytest.raises(ValidationError, match="5 MB"):
        extractor.extract("huge.txt", "text/plain", b"x" * (5 * 1024 * 1024 + 1))


def test_failed_generation_rolls_back_the_document(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        assignment = _assignment("assignment-one", "Sparse notes")
        session.add(assignment)
        session.commit()

        with pytest.raises(ValidationError, match="enough terms"):
            SemesterOpsService(session).upload_assignment_document(
                assignment.id,
                AssignmentDocumentUploadCommand(
                    filename="empty-vocabulary.txt",
                    media_type="text/plain",
                    content=b"this that those these",
                ),
            )

        assert session.scalar(select(func.count()).select_from(AssignmentDocument)) == 0
        assert session.scalar(select(func.count()).select_from(AssignmentStudySet)) == 0


def test_assignment_document_count_and_total_storage_are_capped(tmp_path: Path) -> None:
    class ExtractorThatMustNotRun:
        def extract(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("quota rejection should happen before document extraction")

    with _session(tmp_path) as session:
        count_limited = _assignment("assignment-count", "Count-limited notes")
        storage_limited = _assignment("assignment-storage", "Storage-limited notes")
        session.add_all((count_limited, storage_limited))
        session.flush()
        session.add_all(
            _stored_document(count_limited.id, index, size_bytes=1)
            for index in range(MAX_ASSIGNMENT_DOCUMENTS)
        )
        session.add_all(
            _stored_document(
                storage_limited.id,
                100 + index,
                size_bytes=MAX_ASSIGNMENT_DOCUMENT_BYTES,
            )
            for index in range(10)
        )
        session.commit()
        service = AssignmentStudyService(
            session,
            extractor=ExtractorThatMustNotRun(),  # type: ignore[arg-type]
        )
        content = (
            b"Normalization transforms data into related tables while preserving "
            b"dependencies and reducing update anomalies."
        )

        with pytest.raises(ValidationError, match="at most 20 documents"):
            service.upload_document(
                count_limited.id,
                filename="new-notes.txt",
                media_type="text/plain",
                content=content,
            )
        with pytest.raises(ValidationError, match="at most 50 MB"):
            service.upload_document(
                storage_limited.id,
                filename="new-notes.txt",
                media_type="text/plain",
                content=content,
            )


def test_codex_json_submission_stores_provenance_without_raw_source_content(
    tmp_path: Path,
) -> None:
    with _session(tmp_path) as session:
        assignment = _assignment("assignment-codex", "Transaction isolation review")
        session.add(assignment)
        session.commit()
        service = SemesterOpsService(session)
        payload = _codex_study_payload()

        created = service.submit_assignment_study_set(
            assignment.id,
            payload,
            "transaction-isolation-notes-v1",
        )

        assert created["status"] == "created"
        assert created["review_url"] == f"/assignments/{assignment.id}"
        assert session.scalar(select(func.count()).select_from(AssignmentDocument)) == 0
        view = service.get_assignment_study(assignment.id)
        assert view["study"]["generator"] == "codex-mcp-v1"
        assert view["study"]["sources"][0]["filename"] == "transaction-isolation.pdf"
        assert "correct_answer" not in view["study"]["questions"][0]

        duplicate = service.submit_assignment_study_set(
            assignment.id,
            payload,
            "transaction-isolation-notes-v1",
        )
        assert duplicate["status"] == "duplicate"
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "assignment.study.submitted")
            )
            == 1
        )

        changed = deepcopy(payload)
        changed["summary"] = "A different result must use a different idempotency key."
        with pytest.raises(IdempotencyConflictError, match="different JSON"):
            service.submit_assignment_study_set(
                assignment.id,
                changed,
                "transaction-isolation-notes-v1",
            )

        invalid = deepcopy(payload)
        invalid["questions"][0]["correct_answer"] = "Not one of the choices"
        with pytest.raises(ValidationError, match="correct_answer"):
            service.submit_assignment_study_set(assignment.id, invalid, "invalid-answer-v1")

        raw_text = deepcopy(payload)
        raw_text["sources"][0]["text"] = "Raw attachment content must stay in Codex."
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            service.submit_assignment_study_set(assignment.id, raw_text, "raw-text-v1")


def _session(tmp_path: Path) -> Session:
    engine = create_sqlite_engine(tmp_path / "assignment-study.db")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _assignment(uid: str, title: str) -> Assignment:
    return Assignment(
        external_uid=uid,
        title=title,
        due_precision=DuePrecision.DATE,
        due_date=date(2026, 8, 28),
    )


def _stored_document(assignment_id: str, index: int, *, size_bytes: int) -> AssignmentDocument:
    return AssignmentDocument(
        assignment_id=assignment_id,
        original_filename=f"source-{index}.txt",
        media_type="text/plain",
        size_bytes=size_bytes,
        sha256=f"{index:064x}",
        content_bytes=b"x",
        extracted_text=(
            "A stored source contains enough vocabulary for deterministic study material."
        ),
        extracted_character_count=76,
        page_count=None,
        is_truncated=False,
    )


def _codex_study_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "sources": [
            {
                "id": "transaction-isolation-notes",
                "filename": "transaction-isolation.pdf",
                "media_type": "application/pdf",
                "sha256": "a" * 64,
            }
        ],
        "summary": (
            "Transaction isolation controls which concurrent changes a transaction can observe."
        ),
        "key_points": [
            "Serializable isolation prevents non-serializable concurrent outcomes.",
            "Read committed prevents dirty reads but can permit non-repeatable reads.",
        ],
        "questions": [
            {
                "id": "isolation-q1",
                "prompt": "Which isolation level prevents dirty reads?",
                "choices": ["Read uncommitted", "Read committed", "No isolation"],
                "correct_answer": "Read committed",
                "explanation": (
                    "Read committed exposes only changes committed by other transactions."
                ),
                "source_id": "transaction-isolation-notes",
            },
            {
                "id": "isolation-q2",
                "prompt": "Which level provides the strongest standard isolation?",
                "choices": ["Serializable", "Read committed", "Read uncommitted"],
                "correct_answer": "Serializable",
                "explanation": "Serializable execution is equivalent to some serial ordering.",
                "source_id": "transaction-isolation-notes",
            },
        ],
        "assumptions": ["The course uses the ANSI isolation-level terminology."],
    }


def _text_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        (
            b"<< /Length 91 >>\nstream\nBT /F1 12 Tf 72 720 Td "
            b"(Photosynthesis converts sunlight into stored chemical energy for plants.) "
            b"Tj ET\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(pdf)
