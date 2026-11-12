"""Tests for runtime/doctor.py — health report collectors."""

from __future__ import annotations

from pathlib import Path


def test_external_dep_checks_swallows_checker_exception(tmp_path: Path, monkeypatch) -> None:
    """A broken deps manifest/checker never blocks doctor (126-127)."""
    import runtime.deps
    from runtime.doctor import _external_dep_checks

    def _boom(_root):
        raise RuntimeError("manifest corrupt")

    monkeypatch.setattr(runtime.deps, "check_all", _boom)
    checks: list = []
    _external_dep_checks(checks, tmp_path)
    assert checks == []
