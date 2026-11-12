"""Tests for runtime/replay.py — audit timeline dope sheet."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.replay import Frame, ReplayTrack, load_frames


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _rows(n: int = 5) -> list[dict]:
    return [
        {
            "ts": f"2026-11-12T10:00:0{i}+00:00",
            "type": "action" if i % 2 else "policy",
            "details": {"action": f"a{i}", "decision": "allow" if i % 2 else "deny"},
            "hash": f"h{i}",
        }
        for i in range(n)
    ]


def test_load_frames_chronological(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(4))
    frames = load_frames(log)
    assert len(frames) == 4
    assert frames[0].ts < frames[-1].ts
    assert frames[0].label == "a0"
    assert frames[0].verdict == "deny"


def test_load_frames_filter_and_limit(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(6))
    actions = load_frames(log, event_type="action")
    assert all(f.type == "action" for f in actions)
    tail = load_frames(log, limit=2)
    assert len(tail) == 2
    assert tail[-1].details["action"] == "a5"


def test_missing_log(tmp_path: Path) -> None:
    assert load_frames(tmp_path / "none.log") == []


def test_scrub_fraction_and_index(tmp_path: Path) -> None:
    frames = [Frame(idx=i, ts="t", type="x") for i in range(10)]
    track = ReplayTrack(frames)
    assert track.head == 10
    track.scrub(0.5)
    assert track.head == 5
    assert len(track.played()) == 5
    assert len(track.upcoming()) == 5
    track.scrub(0)
    assert track.head_frame() is None
    track.scrub(3)
    assert track.head_frame().idx == 2


def test_by_type_and_span(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(5))
    track = ReplayTrack(load_frames(log))
    counts = track.by_type()
    assert counts["action"] == 2
    assert counts["policy"] == 3
    start, end = track.span()
    assert "10:00:00" in start and "10:00:04" in end


def test_render_dope_sheet(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(3))
    text = ReplayTrack(load_frames(log)).render()
    assert "replay: 3 frames" in text
    assert "▸" in text  # playhead marker
    assert "action" in text


def test_to_dict_shape(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(2))
    d = ReplayTrack(load_frames(log)).to_dict()
    assert d["count"] == 2
    assert len(d["frames"]) == 2
    assert d["frames"][0]["label"] == "a0"


def test_load_frames_skips_blank_bad_and_filtered(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    log.write_text(
        '{"type": "action", "label": "a", "ts": "2026-01-01T00:00:00"}\n'
        "\n"
        "not-json\n"
        '{"type": "other", "label": "o"}\n',
        encoding="utf-8",
    )
    assert [f.type for f in load_frames(log)] == ["action", "other"]
    assert [f.type for f in load_frames(log, event_type="action")] == ["action"]


def test_frame_verdict_empty_without_keys() -> None:
    assert Frame(idx=0, ts="t", type="x", details={}).verdict == ""


def test_render_empty_track() -> None:
    text = ReplayTrack([]).render()
    assert "0 frames" in text


def test_to_dict_without_frames(tmp_path: Path) -> None:
    log = tmp_path / "audit.log"
    _write_log(log, _rows(1))
    d = ReplayTrack(load_frames(log)).to_dict(with_frames=False)
    assert "frames" not in d


def test_fmt_ts_bad_value_falls_back() -> None:
    from runtime.replay import _fmt_ts

    assert _fmt_ts("garbage-ts") == "garbage-"  # ts[:8]
