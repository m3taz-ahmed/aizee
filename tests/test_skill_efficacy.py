from __future__ import annotations

import json

import pytest

from runtime.skill_efficacy import (
    Badge,
    SkillEfficacyStore,
    badge_for,
    current_commit,
    efficacy_report,
    make_record,
    rig_fingerprint,
)


def test_make_record_validates_verdicts() -> None:
    with pytest.raises(Exception, match="verdict_with"):
        make_record("s", "sc", "maybe", "pass", "m", "c")
    with pytest.raises(Exception, match="verdict_without"):
        make_record("s", "sc", "pass", "maybe", "m", "c")


def test_make_record_requires_names() -> None:
    with pytest.raises(Exception):
        make_record("", "sc", "pass", "fail", "m", "c")
    with pytest.raises(Exception):
        make_record("s", "  ", "pass", "fail", "m", "c")


def test_delta_classification() -> None:
    helped = make_record("s", "sc", "pass", "fail", "m", "c")
    assert helped.delta == 1
    hurt = make_record("s", "sc", "fail", "pass", "m", "c")
    assert hurt.delta == -1
    flat = make_record("s", "sc", "pass", "pass", "m", "c")
    assert flat.delta == 0
    skipped = make_record("s", "sc", "skip", "fail", "m", "c")
    assert skipped.delta == 0


def test_rig_fingerprint_stable_and_distinct() -> None:
    a = rig_fingerprint("gpt-x", "scenario-1")
    assert a == rig_fingerprint("gpt-x", "scenario-1")
    assert a != rig_fingerprint("gpt-y", "scenario-1")
    assert len(a) == 16


def test_record_rig_autofill() -> None:
    rec = make_record("s", "sc", "pass", "fail", "model-a", "abc")
    assert rec.rig == rig_fingerprint("model-a", "sc")
    assert rec.ts


def test_store_roundtrip(tmp_path) -> None:
    store = SkillEfficacyStore(tmp_path / "state" / "eff.jsonl")
    assert store.records() == []
    store.append(make_record("alpha", "sc1", "pass", "fail", "m", "c"))
    store.append(make_record("alpha", "sc2", "pass", "pass", "m", "c"))
    rows = store.records()
    assert len(rows) == 2
    assert rows[0]["skill"] == "alpha"
    assert rows[0]["delta"] == 1


def test_store_skips_corrupt_lines(tmp_path) -> None:
    path = tmp_path / "eff.jsonl"
    path.write_text('{"skill": "x", "delta": 1}\nnot-json\n\n', encoding="utf-8")
    assert len(SkillEfficacyStore(path).records()) == 1


def test_badge_aggregation() -> None:
    assert badge_for([]) is Badge.UNMEASURED
    assert badge_for([{"delta": 1}, {"delta": 0}]) is Badge.PROVEN
    assert badge_for([{"delta": 0}, {"delta": 0}]) is Badge.FLAT
    assert badge_for([{"delta": 1}, {"delta": -1}]) is Badge.HARMFUL


def test_efficacy_report_structure(tmp_path) -> None:
    store = SkillEfficacyStore(tmp_path / "eff.jsonl")
    store.append(make_record("alpha", "sc1", "pass", "fail", "gpt-x", "c1"))
    store.append(make_record("beta", "sc1", "pass", "pass", "gpt-x", "c1"))
    report = efficacy_report(store)
    assert report["skills"]["alpha"]["badge"] == "proven"
    assert report["skills"]["alpha"]["helped"] == 1
    assert report["skills"]["beta"]["badge"] == "flat"
    assert report["badges"]["proven"] == 1
    assert report["badges"]["flat"] == 1
    narrow = efficacy_report(store, skill="alpha")
    assert list(narrow["skills"]) == ["alpha"]


def test_report_json_serializable(tmp_path) -> None:
    store = SkillEfficacyStore(tmp_path / "eff.jsonl")
    store.append(make_record("alpha", "sc1", "pass", "fail", "gpt-x", "c1"))
    json.dumps(efficacy_report(store))


def test_current_commit_never_raises(tmp_path) -> None:
    commit = current_commit(tmp_path)
    assert isinstance(commit, str)


def test_current_commit_git_missing(monkeypatch, tmp_path) -> None:
    def boom(*args, **kwargs):
        raise OSError("git absent")

    monkeypatch.setattr("runtime.skill_efficacy.subprocess.run", boom)
    assert current_commit(tmp_path) == ""
