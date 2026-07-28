from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Form, HTTPException, Request, status


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


async def require_csrf(
    request: Request,
    submitted_token: Annotated[str, Form(alias="_csrf")],
) -> None:
    expected = request.session.get("csrf_token")
    if not isinstance(expected, str) or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid form token")

    origin = request.headers.get("origin")
    if origin:
        origin_parts = urlsplit(origin)
        request_parts = urlsplit(str(request.base_url))
        if (origin_parts.scheme, origin_parts.netloc) != (
            request_parts.scheme,
            request_parts.netloc,
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid origin")


def safe_return_path(value: str | None, fallback: str = "/") -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return fallback
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return fallback
    return value
