from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from semester_ops.integrations.google_calendar.identity import GOOGLE_CALENDAR_SCOPE
from semester_ops.integrations.google_calendar.mapping import (
    google_event_body,
    remote_event_from_google,
)
from semester_ops.integrations.google_calendar.models import (
    LocalCalendarProjection,
    RemoteCalendarEvent,
)

DEV_CALENDAR_NAME = "Semester Ops - Dev"


class GoogleCalendarError(RuntimeError):
    pass


class GoogleCalendarConfigurationError(GoogleCalendarError):
    pass


class GoogleCalendarAccessError(GoogleCalendarError):
    """An allowlisted, user-actionable Google access failure."""

    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class GoogleCalendarOwnershipError(GoogleCalendarError):
    pass


class SyncTokenExpired(GoogleCalendarError):
    pass


@dataclass(frozen=True, slots=True)
class CalendarPage:
    events: tuple[RemoteCalendarEvent, ...]
    next_page_token: str | None
    next_sync_token: str | None


@dataclass(frozen=True, slots=True)
class IncrementalRead:
    events: tuple[RemoteCalendarEvent, ...]
    next_sync_token: str
    reset_from_full_scan: bool


class CalendarGateway(Protocol):
    def create_dev_calendar(self, *, timezone_name: str) -> str: ...

    def list_event_page(
        self,
        calendar_id: str,
        *,
        sync_token: str | None,
        page_token: str | None,
    ) -> CalendarPage: ...

    def upsert_projection(
        self,
        calendar_id: str,
        *,
        event_id: str,
        projection: LocalCalendarProjection,
    ) -> RemoteCalendarEvent: ...

    def delete_owned_event(
        self,
        calendar_id: str,
        *,
        event_id: str,
        occurrence_id: str,
    ) -> bool: ...


class GoogleCalendarGateway:
    """Thin Google client; all policy and reconciliation remain in pure helpers."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_oauth_files(
        cls,
        *,
        client_secret_file: Path,
        token_file: Path,
        force_reauthorize: bool = False,
    ) -> Self:
        if not client_secret_file.is_file():
            raise GoogleCalendarConfigurationError(
                "Google OAuth client-secret file is not configured or does not exist"
            )

        scopes = [GOOGLE_CALENDAR_SCOPE]
        credentials: Credentials | None = None
        if token_file.is_file() and not force_reauthorize:
            try:
                credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                    str(token_file), scopes
                )
            except (ValueError, OSError) as exc:
                raise GoogleCalendarAccessError(
                    "oauth_required",
                    "Stored Google authorization is invalid. Run Google setup with --reauthorize.",
                ) from exc

        if credentials is not None and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())  # type: ignore[no-untyped-call]
            except TransportError as exc:
                raise GoogleCalendarAccessError(
                    "calendar_temporarily_unavailable",
                    "Google could not be reached while refreshing authorization. Try again.",
                ) from exc
            except GoogleAuthError as exc:
                raise GoogleCalendarAccessError(
                    "oauth_refresh_failed",
                    "Google authorization expired or was revoked. "
                    "Run Google setup with --reauthorize.",
                ) from exc
        elif credentials is None or not credentials.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
                credentials = (
                    flow.run_local_server(port=0, prompt="consent")
                    if force_reauthorize
                    else flow.run_local_server(port=0)
                )
            except (ValueError, OSError) as exc:
                raise GoogleCalendarConfigurationError("Google OAuth setup failed") from exc
            if force_reauthorize and not credentials.refresh_token:
                raise GoogleCalendarAccessError(
                    "oauth_refresh_failed",
                    "Google did not return long-lived authorization. "
                    "Run setup with --reauthorize and approve access again.",
                )

        try:
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        except TransportError as exc:
            raise GoogleCalendarAccessError(
                "calendar_temporarily_unavailable",
                "Google Calendar is temporarily unavailable. Try again.",
            ) from exc
        except GoogleAuthError as exc:
            raise GoogleCalendarAccessError(
                "oauth_refresh_failed",
                "Google authorization could not be used. Run Google setup with --reauthorize.",
            ) from exc
        _write_private_token_file(token_file, credentials.to_json())
        return cls(service)

    def create_dev_calendar(self, *, timezone_name: str) -> str:
        body = {
            "summary": DEV_CALENDAR_NAME,
            "description": "Development projection owned by the local Semester Ops app.",
            "timeZone": timezone_name,
        }
        try:
            response = self._service.calendars().insert(body=body).execute(num_retries=2)
        except HttpError as exc:
            raise _access_error_from_http(
                exc,
                fallback_message="Google Calendar creation failed.",
            ) from exc
        calendar_id = response.get("id") if isinstance(response, Mapping) else None
        if not isinstance(calendar_id, str) or not calendar_id:
            raise GoogleCalendarError("Google did not return the created development calendar ID")
        _require_secondary_calendar(calendar_id)
        return calendar_id

    def list_event_page(
        self,
        calendar_id: str,
        *,
        sync_token: str | None,
        page_token: str | None,
    ) -> CalendarPage:
        _require_secondary_calendar(calendar_id)
        parameters: dict[str, Any] = {
            "calendarId": calendar_id,
            "showDeleted": True,
            "singleEvents": True,
            "maxResults": 2500,
        }
        if sync_token:
            parameters["syncToken"] = sync_token
        if page_token:
            parameters["pageToken"] = page_token

        try:
            response = self._service.events().list(**parameters).execute(num_retries=2)
        except HttpError as exc:
            if _http_status(exc) == 410:
                raise SyncTokenExpired("Google Calendar sync token expired") from exc
            raise _access_error_from_http(
                exc,
                fallback_message="Google Calendar could not be read.",
            ) from exc

        if not isinstance(response, Mapping):
            raise GoogleCalendarError("Google Calendar returned an invalid event-list response")
        raw_items = response.get("items", [])
        if not isinstance(raw_items, list):
            raise GoogleCalendarError("Google Calendar event list contains invalid items")
        events = tuple(remote_event_from_google(item) for item in raw_items)
        return CalendarPage(
            events=events,
            next_page_token=_optional_token(response.get("nextPageToken")),
            next_sync_token=_optional_token(response.get("nextSyncToken")),
        )

    def upsert_projection(
        self,
        calendar_id: str,
        *,
        event_id: str,
        projection: LocalCalendarProjection,
    ) -> RemoteCalendarEvent:
        _require_secondary_calendar(calendar_id)
        body = google_event_body(projection)
        existing = self._get_event(calendar_id, event_id)
        if existing is None:
            insert_body = {"id": event_id, **body}
            try:
                response = (
                    self._service.events()
                    .insert(calendarId=calendar_id, body=insert_body)
                    .execute(num_retries=2)
                )
            except HttpError as exc:
                if _http_status(exc) != 409:
                    raise _access_error_from_http(
                        exc,
                        fallback_message="Google Calendar event creation failed.",
                    ) from exc
                existing = self._get_event(calendar_id, event_id)
                if existing is None:
                    raise GoogleCalendarError(
                        "Google reported an event-ID conflict but the event was not readable"
                    ) from exc
                self._require_owned(existing, projection.occurrence_id)
                response = self._update(calendar_id, event_id, body)
        else:
            self._require_owned(existing, projection.occurrence_id)
            response = self._update(calendar_id, event_id, body)

        if not isinstance(response, Mapping):
            raise GoogleCalendarError("Google Calendar returned an invalid event response")
        return remote_event_from_google(response)

    def delete_owned_event(
        self,
        calendar_id: str,
        *,
        event_id: str,
        occurrence_id: str,
    ) -> bool:
        _require_secondary_calendar(calendar_id)
        existing = self._get_event(calendar_id, event_id)
        if existing is None:
            return False
        self._require_owned(existing, occurrence_id)
        try:
            (
                self._service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute(num_retries=2)
            )
        except HttpError as exc:
            if _http_status(exc) == 404:
                return False
            raise _access_error_from_http(
                exc,
                fallback_message="Google Calendar event deletion failed.",
            ) from exc
        return True

    def _get_event(self, calendar_id: str, event_id: str) -> RemoteCalendarEvent | None:
        try:
            response = (
                self._service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute(num_retries=2)
            )
        except HttpError as exc:
            if _http_status(exc) == 404:
                return None
            raise _access_error_from_http(
                exc,
                fallback_message="Google Calendar event lookup failed.",
            ) from exc
        if not isinstance(response, Mapping):
            raise GoogleCalendarError("Google Calendar returned an invalid event response")
        return remote_event_from_google(response)

    def _update(
        self,
        calendar_id: str,
        event_id: str,
        body: dict[str, Any],
    ) -> Mapping[str, Any]:
        try:
            response = (
                self._service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=body)
                .execute(num_retries=2)
            )
        except HttpError as exc:
            raise _access_error_from_http(
                exc,
                fallback_message="Google Calendar event update failed.",
            ) from exc
        if not isinstance(response, Mapping):
            raise GoogleCalendarError("Google Calendar returned an invalid event response")
        return response

    @staticmethod
    def _require_owned(event: RemoteCalendarEvent, occurrence_id: str) -> None:
        if not event.owned or event.occurrence_id != occurrence_id:
            raise GoogleCalendarOwnershipError(
                "Refusing to mutate a Google event without matching Semester Ops ownership tags"
            )


def read_incremental_changes(
    gateway: CalendarGateway,
    calendar_id: str,
    *,
    sync_token: str | None,
) -> IncrementalRead:
    """Read every page and recover a stale token with one non-destructive full scan."""

    try:
        events, next_token = _read_pages(gateway, calendar_id, sync_token=sync_token)
        return IncrementalRead(events, next_token, False)
    except SyncTokenExpired:
        if sync_token is None:
            raise
        events, next_token = _read_pages(gateway, calendar_id, sync_token=None)
        return IncrementalRead(events, next_token, True)


def _read_pages(
    gateway: CalendarGateway,
    calendar_id: str,
    *,
    sync_token: str | None,
) -> tuple[tuple[RemoteCalendarEvent, ...], str]:
    page_token: str | None = None
    seen_page_tokens: set[str] = set()
    events: list[RemoteCalendarEvent] = []
    while True:
        page = gateway.list_event_page(
            calendar_id,
            sync_token=sync_token,
            page_token=page_token,
        )
        events.extend(page.events)
        if page.next_page_token is None:
            if page.next_sync_token is None:
                raise GoogleCalendarError("Final Google Calendar page omitted nextSyncToken")
            return (tuple(events), page.next_sync_token)
        if page.next_page_token in seen_page_tokens:
            raise GoogleCalendarError("Google Calendar returned a repeated page token")
        seen_page_tokens.add(page.next_page_token)
        page_token = page.next_page_token


def _require_secondary_calendar(calendar_id: str) -> None:
    if not calendar_id.strip() or calendar_id.strip().lower() == "primary":
        raise GoogleCalendarConfigurationError(
            "An explicit app-created secondary Google calendar ID is required"
        )


def _optional_token(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _http_status(error: HttpError) -> int | None:
    return getattr(error.resp, "status", None)


def _access_error_from_http(
    error: HttpError,
    *,
    fallback_message: str,
) -> GoogleCalendarAccessError:
    status = _http_status(error)
    if status == 401:
        return GoogleCalendarAccessError(
            "oauth_refresh_failed",
            "Google authorization expired or was revoked. Run Google setup with --reauthorize.",
        )
    if status in {403, 429} and (status == 429 or _is_rate_limit_error(error)):
        return GoogleCalendarAccessError(
            "calendar_rate_limited",
            "Google Calendar rate limit reached. Wait briefly, then sync again.",
        )
    if status == 403:
        return GoogleCalendarAccessError(
            "calendar_permission_denied",
            "Google denied access to the Semester Ops calendar. "
            "Run Google setup with --reauthorize.",
        )
    if status == 404:
        return GoogleCalendarAccessError(
            "calendar_not_found",
            "The saved Semester Ops development calendar no longer exists in Google.",
        )
    if status is not None and status >= 500:
        return GoogleCalendarAccessError(
            "calendar_temporarily_unavailable",
            "Google Calendar is temporarily unavailable. Try syncing again.",
        )
    return GoogleCalendarAccessError("calendar_read_failed", fallback_message)


def _is_rate_limit_error(error: HttpError) -> bool:
    allowed_reasons = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
    try:
        payload = json.loads(error.content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, Mapping):
        return False
    error_payload = payload.get("error")
    if not isinstance(error_payload, Mapping):
        return False
    raw_errors = error_payload.get("errors")
    if not isinstance(raw_errors, list):
        return False
    return any(
        isinstance(item, Mapping) and item.get("reason") in allowed_reasons for item in raw_errors
    )


def reauthorizing_gateway_from_oauth_files(
    *,
    client_secret_file: Path,
    token_file: Path,
) -> GoogleCalendarGateway:
    return GoogleCalendarGateway.from_oauth_files(
        client_secret_file=client_secret_file,
        token_file=token_file,
        force_reauthorize=True,
    )


def _write_private_token_file(token_file: Path, contents: str) -> None:
    """Atomically replace an OAuth token with owner-only permissions where supported."""

    token_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=token_file.parent,
        prefix=f".{token_file.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                if os.name == "posix":
                    raise
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor = -1
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, token_file)
        try:
            token_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            if os.name == "posix":
                raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
