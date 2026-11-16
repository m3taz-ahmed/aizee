"""Tests for `aizee deps ensure` — on-demand convergence (start only what's down)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aizee_cli import main

_PY = sys.executable.replace("\\", "/")


def _marker_dep(root: Path, marker: Path, check_expr: str | None = None) -> str:
    """A dep that 'comes up' only once the install ran (touches marker)."""
    helper = root / "touch_marker.py"
    helper.write_text(
        "import sys\nfrom pathlib import Path\nPath(sys.argv[1]).touch()\n",
        encoding="utf-8",
    )
    posix_m = str(marker).replace("\\", "/")
    posix_h = str(helper).replace("\\", "/")
    check = check_expr or f"sys.exit(0 if __import__('pathlib').Path(r'{posix_m}').exists() else 1)"
    return f"""  - id: fake-svc
    name: fake service
    kind: command
    check_cmd:
      all: ["{_PY}", "-c", "import sys;{check}"]
    severity: optional
    install:
      all: '"{_PY}" "{posix_h}" "{posix_m}"'
"""


def _ensure(tmp_path: Path, *extra: str) -> int:
    return main(["--root", str(tmp_path), "deps", "ensure", *extra])


def test_ensure_starts_down_dep_then_verifies(tmp_path: Path) -> None:
    marker = tmp_path / "svc.marker"
    (tmp_path / "deps.yaml").write_text("deps:\n" + _marker_dep(tmp_path, marker))
    assert _ensure(tmp_path, "fake-svc", "--wait", "30") == 0
    assert marker.exists()


def test_ensure_skips_satisfied_dep(tmp_path: Path) -> None:
    marker = tmp_path / "already.marker"
    (tmp_path / "deps.yaml").write_text(
        "deps:\n" + _marker_dep(tmp_path, marker, check_expr="sys.exit(0)")
    )
    assert _ensure(tmp_path, "fake-svc") == 0
    assert not marker.exists()  # already-satisfied → install never ran


def test_ensure_manual_only_dep_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "deps.yaml").write_text(
        "deps:\n"
        "  - id: manual-only\n"
        "    name: manual\n"
        "    kind: command\n"
        "    check_cmd:\n"
        '      all: ["exit-42-no-such-binary"]\n'
        "    severity: optional\n"
    )
    assert _ensure(tmp_path, "manual-only") == 1


def test_ensure_dry_run_starts_nothing(tmp_path: Path) -> None:
    marker = tmp_path / "dry.marker"
    (tmp_path / "deps.yaml").write_text("deps:\n" + _marker_dep(tmp_path, marker))
    assert _ensure(tmp_path, "fake-svc", "--dry-run") == 0
    assert not marker.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
