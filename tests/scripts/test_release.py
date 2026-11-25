"""Tests for scripts/release.py release-gate command construction."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_SPEC = importlib.util.spec_from_file_location("release", ROOT / "scripts" / "release.py")
assert _SPEC is not None and _SPEC.loader is not None
_release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_release)


def test_full_test_command_pins_source_root() -> None:
    assert _release.full_test_command() == [
        sys.executable,
        "aizee_cli.py",
        "--root",
        ".",
        "test",
        "--full",
    ]


def test_release_gate_uses_pinned_test_command() -> None:
    source = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
    assert "_run(full_test_command(), check=False)" in source
