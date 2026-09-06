from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from semester_ops.integrations.google_calendar import (
    GoogleCalendarAccessError,
    GoogleCalendarGateway,
    SyncTokenExpired,
)

_SECRET = "ya29.gateway-secret"
_SECRET_URI = f"https://www.googleapis.com/calendar/v3/calendars/private?access_token={_SECRET}"


class FailingRequest:
    def __init__(self, error: HttpError) -> None:
        self.error = error

    def execute(self, *, num_retries: int) -> Mapping[str, Any]:
        assert num_retries == 2
        raise self.error


class FailingEventsResource:
    def __init__(self, error: HttpError) -> None:
        self.error = error
        self.list_parameters: list[dict[str, Any]] = []

    def list(self, **parameters: Any) -> FailingRequest:
        self.list_parameters.append(parameters)
        return FailingRequest(self.error)


class FailingCalendarsResource:
    def __init__(self, error: HttpError) -> None:
        self.error = error
        self.insert_bodies: list[dict[str, str]] = []

    def insert(self, *, body: dict[str, str]) -> FailingRequest:
        self.insert_bodies.append(body)
        return FailingRequest(self.error)


class FailingGoogleService:
    def __init__(self, error: HttpError) -> None:
        self.events_resource = FailingEventsResource(error)
        self.calendars_resource = FailingCalendarsResource(error)

    def events(self) -> FailingEventsResource:
        return self.events_resource

    def calendars(self) -> FailingCalendarsResource:
        return self.calendars_resource


def google_http_error(status: int, reason: str) -> HttpError:
    payload = {
        "error": {
            "code": status,
            "message": f"Sensitive provider message containing {_SECRET}",
            "errors": [{"reason": reason}],
        }
    }
    return HttpError(
        Response({"status": str(status), "reason": "provider failure"}),
        json.dumps(payload).encode("utf-8"),
        uri=_SECRET_URI,
    )


@pytest.mark.parametrize(
    ("status", "reason", "expected_code", "message_fragment"),
    [
        (401, "authError", "oauth_refresh_failed", "--reauthorize"),
        (403, "insufficientPermissions", "calendar_permission_denied", "denied access"),
        (403, "rateLimitExceeded", "calendar_rate_limited", "rate limit"),
        (403, "userRateLimitExceeded", "calendar_rate_limited", "rate limit"),
        (403, "quotaExceeded", "calendar_rate_limited", "rate limit"),
        (429, "unknown", "calendar_rate_limited", "rate limit"),
        (404, "notFound", "calendar_not_found", "no longer exists"),
        (503, "backendError", "calendar_temporarily_unavailable", "temporarily unavailable"),
        (400, "badRequest", "calendar_read_failed", "could not be read"),
    ],
)
def test_event_list_http_errors_have_safe_actionable_classifications(
    status: int,
    reason: str,
    expected_code: str,
    message_fragment: str,
) -> None:
    service = FailingGoogleService(google_http_error(status, reason))

    with pytest.raises(GoogleCalendarAccessError) as captured:
        GoogleCalendarGateway(service).list_event_page(
            "dev-calendar",
            sync_token=None,
            page_token=None,
        )

    error = captured.value
    assert error.code == expected_code
    assert error.public_message == str(error)
    assert message_fragment.casefold() in error.public_message.casefold()
    assert _SECRET not in error.public_message
    assert _SECRET_URI not in error.public_message


def test_event_list_410_remains_the_non_destructive_sync_token_signal() -> None:
    service = FailingGoogleService(google_http_error(410, "fullSyncRequired"))

    with pytest.raises(SyncTokenExpired) as captured:
        GoogleCalendarGateway(service).list_event_page(
            "dev-calendar",
            sync_token="expired-token",
            page_token=None,
        )

    assert str(captured.value) == "Google Calendar sync token expired"
    assert _SECRET not in str(captured.value)
    assert _SECRET_URI not in str(captured.value)


def test_calendar_creation_uses_the_same_safe_http_classification() -> None:
    service = FailingGoogleService(google_http_error(401, "authError"))

    with pytest.raises(GoogleCalendarAccessError) as captured:
        GoogleCalendarGateway(service).create_dev_calendar(timezone_name="America/Chicago")

    error = captured.value
    assert error.code == "oauth_refresh_failed"
    assert "--reauthorize" in error.public_message
    assert _SECRET not in error.public_message
    assert _SECRET_URI not in error.public_message
