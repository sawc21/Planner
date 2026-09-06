from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from semester_ops.application.facade import SemesterOpsService
from semester_ops.db.base import Base
from semester_ops.db.models import AppSettings, ExternalSourceState
from semester_ops.db.session import create_sqlite_engine
from semester_ops.domain.enums import SyncConnector
from semester_ops.web.services import SettingsCommand


def _session_factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_sqlite_engine(tmp_path / "settings-test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _command(
    *,
    blackboard_ics_url: str | None,
    clear_blackboard_ics: bool = False,
) -> SettingsCommand:
    return SettingsCommand(
        timezone="America/Chicago",
        operational_day_start="04:00",
        missed_grace_minutes=30,
        calorie_target=2600,
        protein_target_grams=180,
        weight_unit="lb",
        blackboard_ics_url=blackboard_ics_url,
        clear_blackboard_ics=clear_blackboard_ics,
    )


def _seed_cached_sources(session: Session, url: str) -> None:
    session.add(AppSettings(id=1, blackboard_ics_url=url))
    session.add_all(
        [
            ExternalSourceState(
                connector=SyncConnector.BLACKBOARD,
                source_key="default",
                etag='"blackboard-old"',
                last_modified="Mon, 27 Jul 2026 12:00:00 GMT",
            ),
            ExternalSourceState(
                connector=SyncConnector.GOOGLE,
                source_key="default",
                etag='"google-current"',
                last_modified="Tue, 28 Jul 2026 12:00:00 GMT",
            ),
        ]
    )
    session.commit()


def test_changing_blackboard_url_clears_only_blackboard_http_validators(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    old_url = "https://school.example/private/old.ics"
    new_url = "https://school.example/private/new.ics"

    with factory() as session:
        _seed_cached_sources(session, old_url)
        SemesterOpsService(session).update_settings(_command(blackboard_ics_url=new_url))

        settings = session.get(AppSettings, 1)
        blackboard_state = session.scalar(
            select(ExternalSourceState).where(
                ExternalSourceState.connector == SyncConnector.BLACKBOARD
            )
        )
        google_state = session.scalar(
            select(ExternalSourceState).where(ExternalSourceState.connector == SyncConnector.GOOGLE)
        )

    assert settings is not None
    assert settings.blackboard_ics_url == new_url
    assert blackboard_state is not None
    assert blackboard_state.etag is None
    assert blackboard_state.last_modified is None
    assert google_state is not None
    assert google_state.etag == '"google-current"'
    assert google_state.last_modified == "Tue, 28 Jul 2026 12:00:00 GMT"


def test_saving_same_blackboard_url_preserves_http_validators(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    url = "https://school.example/private/current.ics"

    with factory() as session:
        _seed_cached_sources(session, url)
        SemesterOpsService(session).update_settings(_command(blackboard_ics_url=url))
        state = session.scalar(
            select(ExternalSourceState).where(
                ExternalSourceState.connector == SyncConnector.BLACKBOARD
            )
        )

    assert state is not None
    assert state.etag == '"blackboard-old"'
    assert state.last_modified == "Mon, 27 Jul 2026 12:00:00 GMT"


def test_clearing_blackboard_url_also_clears_http_validators(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)

    with factory() as session:
        _seed_cached_sources(session, "https://school.example/private/current.ics")
        SemesterOpsService(session).update_settings(
            _command(blackboard_ics_url=None, clear_blackboard_ics=True)
        )
        settings = session.get(AppSettings, 1)
        state = session.scalar(
            select(ExternalSourceState).where(
                ExternalSourceState.connector == SyncConnector.BLACKBOARD
            )
        )

    assert settings is not None
    assert settings.blackboard_ics_url is None
    assert state is not None
    assert state.etag is None
    assert state.last_modified is None


def test_invalid_blackboard_url_is_rejected_before_any_settings_are_saved(
    tmp_path: Path,
) -> None:
    factory = _session_factory(tmp_path)
    old_url = "https://school.example/private/current.ics"

    with factory() as session:
        _seed_cached_sources(session, old_url)
        with pytest.raises(ValueError, match="absolute HTTPS URL"):
            SemesterOpsService(session).update_settings(
                _command(blackboard_ics_url="http://school.example/private/current.ics")
            )

        settings = session.get(AppSettings, 1)
        state = session.scalar(
            select(ExternalSourceState).where(
                ExternalSourceState.connector == SyncConnector.BLACKBOARD
            )
        )

    assert settings is not None
    assert settings.blackboard_ics_url == old_url
    assert settings.calorie_target is None
    assert state is not None
    assert state.etag == '"blackboard-old"'
    assert state.last_modified == "Mon, 27 Jul 2026 12:00:00 GMT"
