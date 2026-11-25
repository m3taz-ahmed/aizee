"""Tests for scripts/update_aizee.py source→mirror sync helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "update_aizee", Path(__file__).resolve().parent.parent.parent / "scripts" / "update_aizee.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_update_aizee = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_update_aizee)

source_version = _update_aizee.source_version
write_version_stamp = _update_aizee.write_version_stamp


class TestVersionStamp:
    def test_source_version_reads_config(self, tmp_path: Path) -> None:
        (tmp_path / "config.py").write_text("VERSION = '9.9.9'\n", encoding="utf-8")
        assert source_version(tmp_path) == "9.9.9"

    def test_write_version_stamp_refreshes_excluded_marker(self, tmp_path: Path) -> None:
        marker = tmp_path / ".aizee-version"
        marker.write_text("6.8.0\n", encoding="utf-8")
        assert write_version_stamp(tmp_path, "6.14.0", dry_run=False) is True
        assert marker.read_text(encoding="utf-8") == "6.14.0\n"

    def test_write_version_stamp_dry_run_preserves_marker(self, tmp_path: Path) -> None:
        marker = tmp_path / ".aizee-version"
        marker.write_text("6.8.0\n", encoding="utf-8")
        assert write_version_stamp(tmp_path, "6.14.0", dry_run=True) is False
        assert marker.read_text(encoding="utf-8") == "6.8.0\n"

    def test_windows_batch_refreshes_version_stamp(self) -> None:
        batch = (Path(__file__).resolve().parent.parent.parent / "scripts" / "update_aizee.bat").read_text(encoding="utf-8")
        assert '>"%TARGET%\\.aizee-version" echo %AIZEE_VERSION%' in batch
        assert 'findstr /R /C:"^version *=' in batch
