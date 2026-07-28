import os
import stat
from pathlib import Path

from semester_ops.integrations.google_calendar.gateway import _write_private_token_file


def test_oauth_token_replacement_is_atomic_and_private(
    tmp_path: Path,
    monkeypatch,
) -> None:
    token_file = tmp_path / "nested" / "google-token.json"
    token_file.parent.mkdir()
    token_file.write_text("old", encoding="utf-8")
    original_replace = os.replace
    replace_observation: dict[str, object] = {}

    def observed_replace(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> None:
        source_path = Path(source)
        replace_observation["source_name"] = source_path.name
        replace_observation["temporary_contents"] = source_path.read_text(encoding="utf-8")
        replace_observation["destination_contents"] = Path(destination).read_text(encoding="utf-8")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", observed_replace)

    _write_private_token_file(token_file, "new-token")

    assert token_file.read_text(encoding="utf-8") == "new-token"
    assert replace_observation["temporary_contents"] == "new-token"
    assert replace_observation["destination_contents"] == "old"
    assert str(replace_observation["source_name"]).startswith(".google-token.json.")
    if os.name == "posix":
        assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
