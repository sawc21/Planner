from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from semester_ops.config import Settings
from semester_ops.web.main import create_app


class _SettingsService:
    def get_settings_view(self) -> dict[str, object]:
        return {
            "settings": {
                "timezone": "America/Chicago",
                "operational_day_start": "04:00",
                "missed_grace_minutes": 30,
                "calorie_target": None,
                "protein_target_grams": None,
                "weight_unit": "lb",
                "blackboard_configured": False,
            },
            "connectors": [],
            "sync_runs": [],
            "sync_conflicts": [],
        }


@contextmanager
def _service_factory() -> Iterator[_SettingsService]:
    yield _SettingsService()


def test_https_base_url_allows_only_the_exact_proxy_host_and_secures_cookie() -> None:
    settings = Settings(
        base_url="https://semester-ops.example-tailnet.ts.net/",
        secret_key="remote-access-test-secret",
    )
    app = create_app(settings=settings, service_factory=_service_factory)

    with TestClient(app, base_url=settings.base_url) as client:
        response = client.get("/settings")
        rejected = client.get("/health", headers={"host": "other.example-tailnet.ts.net"})

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()
    assert rejected.status_code == 400


@pytest.mark.parametrize(
    "value",
    [
        "ftp://semester-ops.example-tailnet.ts.net",
        "https://user:secret@semester-ops.example-tailnet.ts.net",
        "https://semester-ops.example-tailnet.ts.net/private",
        "https://semester-ops.example-tailnet.ts.net?token=secret",
    ],
)
def test_base_url_rejects_non_origin_values(value: str) -> None:
    with pytest.raises(ValidationError, match="base_url"):
        Settings(base_url=value)
