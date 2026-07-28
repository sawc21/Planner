from collections import deque

import pytest

from semester_ops.integrations.google_calendar import (
    CalendarPage,
    GoogleCalendarError,
    SyncTokenExpired,
    read_incremental_changes,
)


class FakeGateway:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.calls = []

    def list_event_page(self, calendar_id, *, sync_token, page_token):
        self.calls.append((calendar_id, sync_token, page_token))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


def test_incremental_reader_pages_to_final_sync_token() -> None:
    gateway = FakeGateway(
        [
            CalendarPage((), "page-2", None),
            CalendarPage((), None, "sync-next"),
        ]
    )

    result = read_incremental_changes(gateway, "dev-calendar", sync_token="sync-old")

    assert result.next_sync_token == "sync-next"
    assert not result.reset_from_full_scan
    assert gateway.calls == [
        ("dev-calendar", "sync-old", None),
        ("dev-calendar", "sync-old", "page-2"),
    ]


def test_expired_token_triggers_one_safe_full_scan() -> None:
    gateway = FakeGateway(
        [
            SyncTokenExpired("expired"),
            CalendarPage((), None, "fresh-token"),
        ]
    )

    result = read_incremental_changes(gateway, "dev-calendar", sync_token="old-token")

    assert result.reset_from_full_scan
    assert result.next_sync_token == "fresh-token"
    assert gateway.calls == [
        ("dev-calendar", "old-token", None),
        ("dev-calendar", None, None),
    ]


def test_missing_final_sync_token_is_an_explicit_failure() -> None:
    gateway = FakeGateway([CalendarPage((), None, None)])

    with pytest.raises(GoogleCalendarError, match="nextSyncToken"):
        read_incremental_changes(gateway, "dev-calendar", sync_token=None)
