from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.templating import Jinja2Templates

from semester_ops.application.errors import (
    DraftBlockedError,
    IdempotencyConflictError,
    NotFoundError,
    StaleRevisionError,
    ValidationError,
)
from semester_ops.config import Settings, get_settings
from semester_ops.web.routes import render_page, router
from semester_ops.web.services import ServiceFactory, WebServiceUnavailable, default_service_factory

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _format_time(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%I:%M %p").lstrip("0")
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%I:%M %p").lstrip("0")


def _format_day(value: Any, pattern: str = "%A, %B %-d") -> str:
    if value is None:
        return ""
    parsed: date
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except ValueError:
            return str(value)
    # Windows' strftime does not support the '-' modifier.
    formatted = parsed.strftime(pattern.replace("%-d", "%d"))
    return formatted.replace(" 0", " ")


def _duration(minutes: Any) -> str:
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return ""
    hours, remainder = divmod(total, 60)
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


def _datetime_local(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return text[:16]


def _configure_templates(template_dir: Path) -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(template_dir))
    templates.env.filters["time"] = _format_time
    templates.env.filters["day"] = _format_day
    templates.env.filters["duration"] = _duration
    templates.env.filters["datetime_local"] = _datetime_local
    return templates


def create_app(
    *,
    settings: Settings | None = None,
    service_factory: ServiceFactory | None = None,
    template_dir: Path | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    active_template_dir = template_dir or PROJECT_ROOT / "templates"
    active_static_dir = static_dir or PROJECT_ROOT / "static"

    app = FastAPI(
        title="Semester Ops",
        description="Local-first full-day schedule tracker",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = active_settings
    app.state.service_factory = service_factory or default_service_factory
    app.state.templates = _configure_templates(active_template_dir)

    app.add_middleware(
        SessionMiddleware,
        secret_key=active_settings.secret_key,
        same_site="strict",
        https_only=False,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver", "[::1]", "::1"],
    )
    app.mount("/static", StaticFiles(directory=str(active_static_dir)), name="static")
    app.include_router(router)

    @app.middleware("http")
    async def local_security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        try:
            with app.state.service_factory() as services:
                services.get_settings_view()
        except Exception:
            logger.exception("Semester Ops readiness check failed")
            return JSONResponse(
                {"status": "unavailable", "service": "semester-ops"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return JSONResponse({"status": "ready", "service": "semester-ops"})

    @app.exception_handler(WebServiceUnavailable)
    async def unavailable_handler(request: Request, exc: WebServiceUnavailable) -> HTMLResponse:
        return render_page(
            request,
            "error.html",
            {"error_title": "Application service unavailable", "error_message": str(exc)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> HTMLResponse:
        return render_page(
            request,
            "error.html",
            {"error_title": "Record not found", "error_message": str(exc)},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(IdempotencyConflictError)
    @app.exception_handler(StaleRevisionError)
    async def conflict_handler(request: Request, exc: Exception) -> HTMLResponse:
        return render_page(
            request,
            "error.html",
            {"error_title": "The schedule changed", "error_message": str(exc)},
            status_code=status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(DraftBlockedError)
    @app.exception_handler(ValidationError)
    async def domain_validation_handler(request: Request, exc: Exception) -> HTMLResponse:
        return render_page(
            request,
            "error.html",
            {"error_title": "That change needs review", "error_message": str(exc)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> HTMLResponse:
        return render_page(
            request,
            "error.html",
            {"error_title": "That change could not be applied", "error_message": str(exc)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> HTMLResponse:
        details = "; ".join(str(error.get("msg", "Invalid value")) for error in exc.errors())
        return render_page(
            request,
            "error.html",
            {"error_title": "Check the submitted values", "error_message": details},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "semester_ops.web.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
