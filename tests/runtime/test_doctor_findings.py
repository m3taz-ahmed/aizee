"""Tests for runtime/doctor_findings.py — notify-once findings store."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.doctor import Check
from runtime.doctor_findings import (
    diff_and_record,
    open_store,
    unresolved,
)


def _check(name: str, ok: bool, severity: str = "required") -> Check:
    return Check(name=name, ok=ok, severity=severity)


def _state(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


class TestDiffAndRecord:
    def test_first_failure_is_new_and_notified(self, tmp_path: Path) -> None:
        factory, backend = open_store(_state(tmp_path))
        diff = diff_and_record(backend, [_check("ffmpeg", False)])
        factory.shutdown_all()
        assert [f.check for f in diff.new] == ["ffmpeg"]
        assert diff.new[0].notified is True
        assert diff.persisting == [] and diff.resolved == []

    def test_repeat_failure_persists_silently(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        factory, backend = open_store(state)
        diff_and_record(backend, [_check("ffmpeg", False)])
        factory.shutdown_all()

        factory, backend = open_store(state)
        diff = diff_and_record(backend, [_check("ffmpeg", False)])
        factory.shutdown_all()
        assert diff.new == []
        assert [f.check for f in diff.persisting] == ["ffmpeg"]

    def test_recovery_marks_resolved(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        factory, backend = open_store(state)
        diff_and_record(backend, [_check("ffmpeg", False)])
        factory.shutdown_all()

        factory, backend = open_store(state)
        diff = diff_and_record(backend, [_check("ffmpeg", True)])
        assert [f.check for f in diff.resolved] == ["ffmpeg"]
        assert unresolved(backend) == []
        factory.shutdown_all()

    def test_refailure_after_resolution_is_new_again(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        factory, backend = open_store(state)
        diff_and_record(backend, [_check("ffmpeg", False)])
        diff_and_record(backend, [_check("ffmpeg", True)])
        diff = diff_and_record(backend, [_check("ffmpeg", False)])
        assert [f.check for f in diff.new] == ["ffmpeg"]
        factory.shutdown_all()

    def test_passing_checks_never_stored(self, tmp_path: Path) -> None:
        factory, backend = open_store(_state(tmp_path))
        diff = diff_and_record(backend, [_check("python", True)])
        assert diff.new == [] and unresolved(backend) == []
        factory.shutdown_all()

    def test_malformed_state_fails_closed(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        (state / "doctor-findings.json").write_text("{corrupt", encoding="utf-8")
        factory, backend = open_store(state)
        diff = diff_and_record(backend, [_check("x", False)])
        assert [f.check for f in diff.new] == ["x"]
        factory.shutdown_all()

    def test_state_persists_on_disk(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        factory, backend = open_store(state)
        diff_and_record(backend, [_check("ffmpeg", False)])
        factory.shutdown_all()
        data = json.loads((state / "doctor-findings.json").read_text(encoding="utf-8"))
        assert data["ffmpeg"]["notified"] is True
        assert data["ffmpeg"]["resolved_at"] == ""


class TestStoreEdgeCases:
    def test_non_dict_entries_ignored(self, tmp_path: Path) -> None:
        factory, backend = open_store(_state(tmp_path))
        backend.put("junk", "not-a-dict")
        diff = diff_and_record(backend, [_check("ok-check", True)])
        assert diff.new == [] and diff.resolved == []
        factory.shutdown_all()

    def test_already_resolved_stays_resolved(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        factory, backend = open_store(state)
        diff_and_record(backend, [_check("x", False)])
        diff_and_record(backend, [_check("x", True)])   # resolved
        diff = diff_and_record(backend, [_check("x", True)])  # still passing
        assert diff.resolved == []  # not re-resolved
        factory.shutdown_all()

    def test_finding_fields_roundtrip(self, tmp_path: Path) -> None:
        factory, backend = open_store(_state(tmp_path))
        diff_and_record(backend, [_check("c", False, "optional")], now="t1")
        got = unresolved(backend)
        assert got[0].severity == "optional"
        assert got[0].first_seen == "t1" and got[0].last_seen == "t1"
        factory.shutdown_all()


def test_diff_to_dict(tmp_path: Path) -> None:
    factory, backend = open_store(_state(tmp_path))
    diff = diff_and_record(backend, [_check("x", False)])
    payload = diff.to_dict()
    assert payload["new"][0]["check"] == "x"
    assert payload["persisting"] == [] and payload["resolved"] == []
    factory.shutdown_all()
