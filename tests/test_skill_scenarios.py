"""Tests for eval.skill_scenarios - EGM-style behavioral eval runner."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eval.skill_scenarios import (
    Assertion,
    CheckResult,
    _apply_assertions,
    format_results,
    load_scenarios,
    run_dir,
    run_file,
)


@pytest.fixture()
def scen_root(tmp_path: Path) -> Path:
    skill = tmp_path / "workflows" / "65-goldfish-review.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "# Goldfish Review\n\nfresh, zero-conversation context\nsemantic split\n"
        "ONE question per turn\nartifact-first\n",
        encoding="utf-8")
    return tmp_path


def _write(path: Path, doc: dict) -> Path:
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def test_load_scenarios(scen_root: Path) -> None:
    f = _write(scen_root / "s.yaml", {"scenarios": [{
        "scenario_id": "s1", "description": "d", "eval_type": "static",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u", "assertions": [
            {"type": "required_pattern", "pattern": "semantic split"}]}]}]})
    scs = load_scenarios(f)
    assert scs[0].scenario_id == "s1"
    assert scs[0].eval_type == "static"
    assert scs[0].turns[0].assertions[0].pattern == "semantic split"


def test_load_scenarios_rejects_non_scenarios(tmp_path: Path) -> None:
    _write(tmp_path / "legacy.yaml", {"scenarios": "notalist"})
    f2 = _write(tmp_path / "nope.yaml", {"foo": 1})
    with pytest.raises(ValueError):
        load_scenarios(f2)


def test_static_pass_and_fail(scen_root: Path) -> None:
    f = _write(scen_root / "s.yaml", {"scenarios": [
        {"scenario_id": "ok", "eval_type": "static",
         "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
         "turns": [{"user_input": "u", "assertions": [
             {"type": "required_pattern", "pattern": "zero.conversation"},
             {"type": "forbidden_pattern", "pattern": "same context"}]}]},
        {"scenario_id": "bad", "eval_type": "static",
         "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
         "turns": [{"user_input": "u", "assertions": [
             {"type": "required_pattern", "pattern": "teleportation"}]}]},
    ]})
    results = run_file(f, scen_root)
    assert results[0].passed
    assert not results[1].passed
    assert "required pattern" in results[1].failures[0]


def test_static_missing_skill_skips(scen_root: Path) -> None:
    f = _write(scen_root / "s.yaml", {"scenarios": [
        {"scenario_id": "gone", "eval_type": "static",
         "system_prompt": {"skill_file": "workflows/99-missing.md"},
         "turns": [{"user_input": "u"}]}]})
    (r,) = run_file(f, scen_root)
    assert r.skipped and "missing" in r.reason


def test_apply_assertions_types() -> None:
    fails = _apply_assertions("hello world", [
        Assertion("required_pattern", "hello"),
        Assertion("required_pattern", "goodbye", "need goodbye"),
        Assertion("forbidden_pattern", "world"),
    ])
    assert len(fails) == 2
    assert fails[0] == "need goodbye"


def test_live_without_endpoint_skips(scen_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIZEE_EVAL_ENDPOINT", raising=False)
    monkeypatch.delenv("AIZEE_EVAL_MODEL", raising=False)
    f = _write(scen_root / "s.yaml", {"scenarios": [
        {"scenario_id": "l", "eval_type": "live",
         "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
         "turns": [{"user_input": "hi"}]}]})
    (r,) = run_file(f, scen_root)
    assert r.skipped


def test_run_dir_skips_legacy(scen_root: Path) -> None:
    d = scen_root / "sc"
    d.mkdir()
    _write(d / "legacy.yaml", {"scenarios": [{"name": "n", "prompt": "p", "grade": "contains"}]})
    _write(d / "new.yaml", {"scenarios": [{
        "scenario_id": "x", "eval_type": "static",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u", "assertions": [{"type": "required_pattern", "pattern": "artifact"}]}]}]})
    results = run_dir(d, scen_root)
    assert len(results) == 2
    skipped = next(r for r in results if r.scenario_id == "n")
    assert skipped.skipped
    ok = next(r for r in results if r.scenario_id == "x")
    assert ok.passed


def test_format_results() -> None:
    out = format_results([
        CheckResult("a", "static", True),
        CheckResult("b", "static", False, ["x"]),
        CheckResult("c", "live", False, skipped=True, reason="r"),
    ])
    assert out["total"] == 3 and out["passed"] == 1 and out["failed"] == 1 and out["skipped"] == 1


def test_load_scenarios_tolerates_malformed_entries(tmp_path: Path) -> None:
    f = _write(tmp_path / "m.yaml", {"scenarios": [
        "not-a-dict",
        {"scenario_id": "t", "eval_type": "static", "system_prompt": {"skill_file": "x.md"},
         "turns": ["no", {"user_input": "u", "assertions": [{"type": "forbidden_pattern"}, {"pattern": "p"}]}]},
    ]})
    scs = load_scenarios(f)
    assert len(scs) == 1
    # {"type": ...} without pattern is dropped; {"pattern": "p"} kept w/ default type
    assert [a.pattern for a in scs[0].turns[0].assertions] == ["p"]


def test_live_request_and_run(scen_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json as _json

    class _Resp:
        def __init__(self, body: dict) -> None: self.body = body
        def read(self) -> bytes: return _json.dumps(self.body).encode()
        def __enter__(self) -> _Resp: return self
        def __exit__(self, *a: object) -> None: return None

    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _Resp({"choices": [{"message": {"content": "hi artifact-first"}}]}))
    from eval.skill_scenarios import _live_request

    assert _live_request("http://e", "m", "sys", "u") == "hi artifact-first"
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _Resp({"choices": []}))
    assert _live_request("http://e", "m", "s", "u") == ""

    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _Resp({"choices": [{"message": {"content": "artifact-first reply"}}]}))
    f = _write(scen_root / "live.yaml", {"scenarios": [{
        "scenario_id": "lv", "eval_type": "live",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u", "assertions": [
            {"type": "required_pattern", "pattern": "artifact"},
            {"type": "forbidden_pattern", "pattern": "glazing"}]}]}]})
    (r,) = run_file(f, scen_root, endpoint="http://e", model="m")
    assert r.passed


def test_run_live_unreachable(scen_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.skill_scenarios import run_live

    def boom(req: object, timeout: float = 0) -> object:
        raise OSError("conn refused")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    sc = load_scenarios(_write(scen_root / "l.yaml", {"scenarios": [{
        "scenario_id": "l", "eval_type": "live",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u"}]}]}))[0]
    r = run_live(sc, scen_root, "http://e", "m")
    assert r.skipped and "unreachable" in r.reason


def test_run_live_missing_skill(scen_root: Path) -> None:
    from eval.skill_scenarios import Scenario, run_live
    r = run_live(Scenario("x", "", "live", "nope.md", []), scen_root, "http://e", "m")
    assert r.skipped


def test_run_dir_yml_and_bad_file(scen_root: Path) -> None:
    d = scen_root / "sc2"
    d.mkdir()
    _write(d / "a.yml", {"scenarios": [{
        "scenario_id": "y", "eval_type": "static",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u", "assertions": [{"type": "required_pattern", "pattern": "artifact"}]}]}]})
    _write(d / "bad.yaml", {"not_scenarios": 1})
    results = run_dir(d, scen_root)
    assert len(results) == 1 and results[0].scenario_id == "y"


def test_run_file_live_flag_forces_live(scen_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIZEE_EVAL_ENDPOINT", "http://e")
    monkeypatch.setenv("AIZEE_EVAL_MODEL", "m")
    import json as _json

    class _Resp:
        def read(self) -> bytes: return _json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        def __enter__(self) -> _Resp: return self
        def __exit__(self, *a: object) -> None: return None
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp())
    f = _write(scen_root / "s.yaml", {"scenarios": [{
        "scenario_id": "s", "eval_type": "static",
        "system_prompt": {"skill_file": "workflows/65-goldfish-review.md"},
        "turns": [{"user_input": "u", "assertions": [{"type": "required_pattern", "pattern": "ok"}]}]}]})
    (r,) = run_file(f, scen_root, live=True)
    assert r.eval_type == "live" and r.passed
