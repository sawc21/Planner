from typing import Any

from sqlalchemy.orm import Session

from semester_ops.config import get_settings as get_runtime_settings
from semester_ops.db.models import AppSettings, AuditEvent


def get_or_create_settings(session: Session) -> AppSettings:
    settings = session.get(AppSettings, 1)
    if settings is None:
        runtime = get_runtime_settings()
        settings = AppSettings(
            id=1,
            timezone=runtime.timezone,
            blackboard_ics_url=runtime.blackboard_ics_url,
            google_calendar_id=runtime.google_calendar_id,
        )
        session.add(settings)
        session.flush()
    return settings


def increment_schedule_revision(session: Session) -> int:
    settings = get_or_create_settings(session)
    settings.schedule_revision += 1
    session.flush()
    return settings.schedule_revision


def add_audit_event(
    session: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "user",
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        data_json=data or {},
    )
    session.add(event)
    return event
