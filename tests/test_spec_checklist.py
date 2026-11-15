"""Tests for spec rows -> checklist derivation (reanimate spec contract)."""

from __future__ import annotations

from pathlib import Path

from runtime.spec.engine import SpecEngine


def _engine(tmp_path: Path) -> SpecEngine:
    return SpecEngine(tmp_path / "specs")


def test_derive_checklist_every_row_is_a_check(tmp_path: Path) -> None:
    e = _engine(tmp_path)
    e.init_spec("s1", "t", "d")
    e.add_requirement("s1", "User can log in")
    e.add_requirement("s1", "Tokens expire", priority="should")
    out = e.derive_checklist("s1")
    assert out["total"] == 2 and out["resolved"] == 2
    assert out["complete"] is True
    assert [i["check"] for i in out["items"]] == [
        "User can log in",
        "Tokens expire",
    ]
    assert out["items"][1]["priority"] == "should"
    assert all(i["source"] == "requirement" for i in out["items"])


def test_derive_checklist_flags_unresolved_markers(tmp_path: Path) -> None:
    e = _engine(tmp_path)
    e.init_spec("s2", "t", "d")
    e.add_requirement("s2", "Timeout value [NEEDS CLARIFICATION: which?]")
    e.add_requirement("s2", "Retry policy TBD")
    e.add_requirement("s2", "Done properly")
    out = e.derive_checklist("s2")
    assert out["unresolved"] == 2 and out["resolved"] == 1
    assert out["complete"] is False
    unresolved = [i["check"] for i in out["items"] if i["unresolved"]]
    assert "Done properly" not in unresolved


def test_derive_checklist_missing_spec(tmp_path: Path) -> None:
    e = _engine(tmp_path)
    assert "error" in e.derive_checklist("nope")


def test_derive_checklist_empty_spec_not_complete(tmp_path: Path) -> None:
    e = _engine(tmp_path)
    e.init_spec("s3", "t", "d")
    out = e.derive_checklist("s3")
    assert out["total"] == 0 and out["complete"] is False


def test_cli_derive_checklist(tmp_path: Path, capsys) -> None:
    """`aizee spec derive-checklist <id>` prints the checklist JSON (TRIG-01)."""
    import json as _json

    from aizee_cli import main

    e = _engine(tmp_path)
    e.init_spec("s4", "t", "d")
    e.add_requirement("s4", "Feature works")
    rc = main(["--root", str(tmp_path), "spec", "derive-checklist", "s4"])
    assert rc == 0
    out = _json.loads(capsys.readouterr().out)
    assert out["spec_id"] == "s4" and out["total"] == 1 and out["complete"] is True


def test_cli_derive_checklist_requires_id(tmp_path: Path) -> None:
    from aizee_cli import main

    assert main(["--root", str(tmp_path), "spec", "derive-checklist"]) == 1


def test_unresolved_markers_are_boundary_aware(tmp_path: Path) -> None:
    """Ordinary punctuation must not false-flag a finished row (S5)."""
    e = _engine(tmp_path)
    e.init_spec("s5", "t", "d")
    e.add_requirement("s5", "Ask what?? is unclear in casual prose")
    e.add_requirement("s5", "STBDX codes are normalized")
    e.add_requirement("s5", "Timeout ??")
    e.add_requirement("s5", "Retry TBD")
    out = e.derive_checklist("s5")
    assert out["unresolved"] == 2
    assert out["resolved"] == 2
