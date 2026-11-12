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


def test_external_dep_checks_status_branches(tmp_path: Path, monkeypatch) -> None:
    """ok / can_install / manual-only statuses map to distinct Check rows."""
    import runtime.deps
    from runtime.deps import DepSpec, DepStatus, Kind, State
    from runtime.doctor import _external_dep_checks

    def _spec(dep_id: str) -> DepSpec:
        return DepSpec(
            id=dep_id, name=dep_id, kind=Kind.BINARY,
            severity="recommended", guidance="see the docs",
        )

    statuses = [
        DepStatus(spec=_spec("ok-dep"), ok=True, state=State.OK),
        DepStatus(
            spec=_spec("fixable"), ok=False, state=State.MISSING,
            can_install=True, fix_cmd="aizee deps install fixable",
        ),
        DepStatus(spec=_spec("manual"), ok=False, state=State.MISSING),
    ]
    monkeypatch.setattr(runtime.deps, "check_all", lambda _root: statuses)
    checks: list = []
    _external_dep_checks(checks, tmp_path)
    assert [c.ok for c in checks] == [True, False, False]
    assert checks[1].fix_run == "aizee deps install fixable"
    assert "see the docs" in checks[2].fix_guidance
