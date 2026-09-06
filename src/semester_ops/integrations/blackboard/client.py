from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class BlackboardFetchError(RuntimeError):
    """A feed fetch failed without exposing the private subscription URL."""


@dataclass(frozen=True, slots=True)
class BlackboardFetchResult:
    content: bytes | None
    etag: str | None
    last_modified: str | None
    not_modified: bool


class BlackboardFeedClient:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        max_response_bytes: int = 5 * 1024 * 1024,
        max_redirects: int = 5,
    ) -> None:
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")
        self._client = client
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects

    def fetch(
        self,
        private_url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> BlackboardFetchResult:
        """Fetch a private feed conditionally and never include its URL in errors."""

        validate_blackboard_feed_url(private_url)
        headers = {"Accept": "text/calendar, text/plain;q=0.8"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        owned_client = self._client is None
        client = self._client or httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        try:
            request_url = private_url
            redirect_count = 0
            while True:
                validate_blackboard_feed_url(request_url)
                with client.stream(
                    "GET",
                    request_url,
                    headers=headers,
                    follow_redirects=False,
                ) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        if redirect_count >= self._max_redirects:
                            raise BlackboardFetchError(
                                "Blackboard calendar exceeded the redirect limit"
                            )
                        location = response.headers.get("Location")
                        if location is None:
                            raise BlackboardFetchError(
                                "Blackboard calendar returned a redirect without a destination"
                            )
                        validate_blackboard_feed_url(location)
                        request_url = location
                        redirect_count += 1
                        continue

                    if response.status_code == 304:
                        return BlackboardFetchResult(None, etag, last_modified, True)
                    if response.status_code != 200:
                        raise BlackboardFetchError(
                            f"Blackboard calendar returned HTTP {response.status_code}"
                        )

                    declared_length = response.headers.get("Content-Length")
                    if declared_length and int(declared_length) > self._max_response_bytes:
                        raise BlackboardFetchError(
                            "Blackboard calendar exceeded the response-size limit"
                        )

                    chunks: list[bytes] = []
                    received = 0
                    for chunk in response.iter_bytes():
                        received += len(chunk)
                        if received > self._max_response_bytes:
                            raise BlackboardFetchError(
                                "Blackboard calendar exceeded the response-size limit"
                            )
                        chunks.append(chunk)

                    return BlackboardFetchResult(
                        b"".join(chunks),
                        response.headers.get("ETag"),
                        response.headers.get("Last-Modified"),
                        False,
                    )
        except BlackboardFetchError:
            raise
        except (httpx.HTTPError, ValueError):
            raise BlackboardFetchError("Blackboard calendar request failed") from None
        finally:
            if owned_client:
                client.close()


def validate_blackboard_feed_url(value: str) -> None:
    """Require the private calendar subscription to use an absolute HTTPS URL."""

    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise ValueError("Blackboard calendar URL must be an absolute HTTPS URL")
