from __future__ import annotations

import re
from asyncio import run
from contextlib import nullcontext
from typing import Any

from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from semester_ops.application.study import MAX_ASSIGNMENT_UPLOAD_REQUEST_BYTES
from semester_ops.config import Settings
from semester_ops.web.main import AssignmentUploadBodyLimitMiddleware, create_app
from semester_ops.web.services import AssignmentDocumentDownload, AssignmentDocumentUploadCommand


class AssignmentStudyWebServices:
    def __init__(self) -> None:
        self.upload: tuple[str, AssignmentDocumentUploadCommand] | None = None
        self.answers: dict[str, str] | None = None
        self.regenerated = False

    def get_assignment_study(self, assignment_id: str) -> dict[str, Any]:
        return self._view(assignment_id)

    def upload_assignment_document(
        self,
        assignment_id: str,
        command: AssignmentDocumentUploadCommand,
    ) -> None:
        self.upload = (assignment_id, command)

    def get_assignment_document(
        self,
        assignment_id: str,
        document_id: str,
    ) -> AssignmentDocumentDownload:
        assert assignment_id == "a1"
        assert document_id == "d1"
        return AssignmentDocumentDownload("notes.txt", "text/plain", b"study notes")

    def regenerate_assignment_study(self, assignment_id: str) -> None:
        assert assignment_id == "a1"
        self.regenerated = True

    def check_assignment_quiz(
        self,
        assignment_id: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        self.answers = answers
        return self._view(assignment_id, reveal=True)

    @staticmethod
    def _view(assignment_id: str, *, reveal: bool = False) -> dict[str, Any]:
        question: dict[str, Any] = {
            "id": "q1",
            "prompt": "Complete the statement: The primary key _____ a row.",
            "choices": ["identifies", "sorts"],
            "source_filename": "notes.txt",
        }
        if reveal:
            question["feedback"] = {
                "selected": "identifies",
                "correct": True,
                "correct_answer": "identifies",
                "explanation": "The primary key uniquely identifies a row.",
            }
        return {
            "assignment": {
                "id": assignment_id,
                "title": "Keys review",
                "course_code": "DB 301",
                "course_name": "Database Systems",
                "due_label": "Aug 28",
                "description": "Review relational keys.",
            },
            "documents": [
                {
                    "id": "d1",
                    "filename": "notes.txt",
                    "media_type": "text/plain",
                    "size_bytes": 1200,
                    "page_count": None,
                    "extracted_character_count": 1180,
                    "is_truncated": False,
                }
            ],
            "study": {
                "summary": "Primary keys uniquely identify rows.",
                "key_points": ["A candidate key can identify each row."],
                "questions": [question],
                "sources": [
                    {
                        "id": "keys-notes",
                        "filename": "keys-notes.pdf",
                        "media_type": "application/pdf",
                        "sha256": "a" * 64,
                    }
                ],
                "assumptions": ["The course uses standard relational terminology."],
                "generator": "codex-mcp-v1",
            },
            "quiz_result": (
                {"correct_count": 1, "question_count": 1, "percent": 100} if reveal else None
            ),
            "nav_path": "/assignments",
        }


def test_assignment_study_page_hides_answers_until_quiz_is_checked() -> None:
    services = AssignmentStudyWebServices()
    client = _client(services)

    initial = client.get("/assignments/a1")

    assert initial.status_code == 200
    assert "notes.txt" in initial.text
    assert "Primary keys uniquely identify rows" in initial.text
    assert "Send files to Codex" in initial.text
    assert "keys-notes.pdf" in initial.text
    assert "standard relational terminology" in initial.text
    assert "Answer: identifies" not in initial.text
    token = _csrf(initial.text)
    checked = client.post(
        "/assignments/a1/quiz/check",
        data={"_csrf": token, "answer_q1": "identifies"},
    )
    assert checked.status_code == 200
    assert "Answer: identifies" in checked.text
    assert "1/1 / 100%" in checked.text
    assert services.answers == {"q1": "identifies"}


def test_assignment_upload_route_accepts_multipart_and_calls_service() -> None:
    services = AssignmentStudyWebServices()
    client = _client(services)
    token = _csrf(client.get("/assignments/a1").text)

    response = client.post(
        "/assignments/a1/documents",
        data={"_csrf": token},
        files={
            "document": (
                "chapter.md",
                b"# Keys\nA primary key identifies a row.",
                "text/markdown",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/assignments/a1"
    assert services.upload is not None
    assignment_id, command = services.upload
    assert assignment_id == "a1"
    assert command.filename == "chapter.md"
    assert command.media_type == "text/markdown"
    assert command.content.startswith(b"# Keys")


def test_assignment_upload_route_rejects_oversized_body_before_the_service() -> None:
    services = AssignmentStudyWebServices()
    client = _client(services)

    response = client.post(
        "/assignments/a1/documents",
        content=b"x" * (MAX_ASSIGNMENT_UPLOAD_REQUEST_BYTES + 1),
        headers={"content-type": "multipart/form-data; boundary=oversized"},
    )

    assert response.status_code == 413
    assert services.upload is None


def test_assignment_upload_stream_limit_rejects_chunks_and_replays_valid_body() -> None:
    rejected_downstream_calls = 0
    rejected_messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"def", "more_body": False},
    ]
    rejected_responses: list[Message] = []

    async def rejected_downstream(_scope: Scope, _receive: Receive, _send: Send) -> None:
        nonlocal rejected_downstream_calls
        rejected_downstream_calls += 1

    run(
        AssignmentUploadBodyLimitMiddleware(rejected_downstream, max_body_bytes=5)(
            _assignment_upload_scope(),
            _receive_from(rejected_messages),
            _send_to(rejected_responses),
        )
    )

    assert rejected_downstream_calls == 0
    assert rejected_responses[0]["type"] == "http.response.start"
    assert rejected_responses[0]["status"] == 413

    replayed_requests: list[Message] = []
    accepted_responses: list[Message] = []

    async def accepted_downstream(_scope: Scope, receive: Receive, send: Send) -> None:
        replayed_requests.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    accepted_messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"def", "more_body": False},
    ]
    run(
        AssignmentUploadBodyLimitMiddleware(accepted_downstream, max_body_bytes=6)(
            _assignment_upload_scope(),
            _receive_from(accepted_messages),
            _send_to(accepted_responses),
        )
    )

    assert replayed_requests == [{"type": "http.request", "body": b"abcdef", "more_body": False}]
    assert accepted_responses[0]["status"] == 204


def test_assignment_document_download_uses_attachment_headers() -> None:
    response = _client(AssignmentStudyWebServices()).get("/assignments/a1/documents/d1")

    assert response.status_code == 200
    assert response.content == b"study notes"
    assert response.headers["content-type"].startswith("text/plain")
    assert "notes.txt" in response.headers["content-disposition"]


def _client(services: AssignmentStudyWebServices) -> TestClient:
    app = create_app(
        settings=Settings(
            database_path="var/unused-assignment-study-web.db",
            secret_key="assignment-study-test-secret",
        ),
        service_factory=lambda: nullcontext(services),  # type: ignore[arg-type]
    )
    return TestClient(app)


def _assignment_upload_scope() -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/assignments/a1/documents",
        "raw_path": b"/assignments/a1/documents",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8000),
    }


def _receive_from(messages: list[Message]) -> Receive:
    async def receive() -> Message:
        return messages.pop(0)

    return receive


def _send_to(messages: list[Message]) -> Send:
    async def send(message: Message) -> None:
        messages.append(message)

    return send


def _csrf(html: str) -> str:
    match = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)
