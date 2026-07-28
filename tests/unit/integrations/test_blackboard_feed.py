from datetime import date, datetime

import httpx
import pytest

from semester_ops.integrations.blackboard import (
    BlackboardFeedClient,
    BlackboardFeedParseError,
    BlackboardFetchError,
    parse_blackboard_ics,
)


def test_parses_date_and_timed_deadlines_without_losing_source_precision() -> None:
    parsed = parse_blackboard_ics(
        b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Blackboard//Calendar//EN\r
BEGIN:VEVENT\r
UID:assignment-1\r
SUMMARY:Read chapter 1\r
DTSTART;VALUE=DATE:20260824\r
CATEGORIES:CS 101\r
SEQUENCE:2\r
DTSTAMP:20260728T120000Z\r
LAST-MODIFIED:20260728T130000Z\r
URL:https://school.example/assignment/1\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:assignment-2\r
RECURRENCE-ID;TZID=America/Chicago:20260825T090000\r
SUMMARY:Lab report\r
DTSTART;TZID=America/Chicago:20260825T170000\r
SEQUENCE:0\r
END:VEVENT\r
END:VCALENDAR\r
"""
    )

    items = parsed.require_valid()
    assert len(items) == 2
    assert items[0].due == date(2026, 8, 24)
    assert items[0].due_precision == "date"
    assert items[0].course_name == "CS 101"
    assert items[0].sequence == 2
    assert items[1].due_precision == "datetime"
    assert isinstance(items[1].due, datetime)
    assert items[1].due.isoformat() == "2026-08-25T17:00:00-05:00"
    assert items[1].recurrence_id == "2026-08-25T14:00:00+00:00"


def test_canceled_event_can_omit_deadline_but_invalid_active_event_blocks_reconcile() -> None:
    parsed = parse_blackboard_ics(
        b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Blackboard//Calendar//EN\r
BEGIN:VEVENT\r
UID:removed\r
SUMMARY:Removed assignment\r
STATUS:CANCELLED\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:broken\r
SUMMARY:No deadline\r
END:VEVENT\r
END:VCALENDAR\r
"""
    )

    assert parsed.items[0].status == "cancelled"
    assert parsed.items[0].due is None
    assert parsed.issues[0].uid == "broken"
    with pytest.raises(BlackboardFeedParseError):
        parsed.require_valid()


def test_feed_client_uses_conditional_headers_and_does_not_expose_private_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["If-None-Match"] == '"old"'
        assert request.headers["If-Modified-Since"] == "Mon, 27 Jul 2026 12:00:00 GMT"
        return httpx.Response(503, request=request)

    private_url = "https://school.example/private/secret-token/calendar.ics"
    client = BlackboardFeedClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(BlackboardFetchError) as error:
        client.fetch(
            private_url,
            etag='"old"',
            last_modified="Mon, 27 Jul 2026 12:00:00 GMT",
        )
    assert "secret-token" not in str(error.value)


def test_feed_client_enforces_streaming_size_limit() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"12345"))
    client = BlackboardFeedClient(
        client=httpx.Client(transport=transport),
        max_response_bytes=4,
    )

    with pytest.raises(BlackboardFetchError, match="response-size limit"):
        client.fetch("https://school.example/calendar.ics")


def test_feed_client_validates_each_absolute_https_redirect() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if len(requested_urls) == 1:
            return httpx.Response(
                302,
                headers={"Location": "https://feeds.example/calendar.ics"},
                request=request,
            )
        assert request.headers["If-None-Match"] == '"old"'
        return httpx.Response(304, request=request)

    client = BlackboardFeedClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.fetch("https://school.example/private.ics", etag='"old"')

    assert result.not_modified
    assert requested_urls == [
        "https://school.example/private.ics",
        "https://feeds.example/calendar.ics",
    ]


@pytest.mark.parametrize(
    "location",
    [
        "/relative/calendar.ics",
        "http://school.example/calendar.ics",
        "not-a-url",
    ],
)
def test_feed_client_rejects_unsafe_redirect_destination_without_disclosing_it(
    location: str,
) -> None:
    private_value = f"{location}?secret-token" if "?" not in location else location
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"Location": private_value},
            request=request,
        )
    )
    client = BlackboardFeedClient(client=httpx.Client(transport=transport))

    with pytest.raises(BlackboardFetchError) as error:
        client.fetch("https://school.example/private.ics")

    assert "secret-token" not in str(error.value)


def test_feed_client_bounds_redirect_count() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            307,
            headers={"Location": f"https://school.example/redirect/{request_count}"},
            request=request,
        )

    client = BlackboardFeedClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_redirects=2,
    )

    with pytest.raises(BlackboardFetchError, match="redirect limit"):
        client.fetch("https://school.example/private.ics")

    assert request_count == 3
