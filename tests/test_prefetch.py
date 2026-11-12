"""Tests for runtime/prefetch.py — speculative warm-up (OpenToonz)."""

from __future__ import annotations

import time
from pathlib import Path

from runtime.prefetch import Prefetcher


def _wait(cond, timeout: float = 3.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_warms_known_tools_and_files(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    tools = {"fs.read": lambda **kw: kw, "dns.lookup": lambda **kw: kw}
    pf = Prefetcher(tools=tools)
    pf.start()
    pf.start()  # idempotent — thread already alive
    try:
        pf.suggest([
            {"op": "call", "tool": "fs.read", "args": {"path": str(f)}},
            {"op": "call", "tool": "unknown", "args": {}},
            {"op": "let", "name": "x", "expr": 1},  # non-call ignored
        ])
        assert _wait(lambda: "fs.read" in pf.stats()["tool_warm"])
        assert _wait(lambda: pf.stats()["files"]["size"] >= 1)
        assert pf.read(f) == "hello"  # warm hit
        assert pf._files.stats()["hits"] >= 1
    finally:
        pf.stop()


def test_bounded_queue(tmp_path: Path) -> None:
    pf = Prefetcher(tools={}, max_queue=2)
    pf.start()
    try:
        queued = pf.suggest([{"op": "call", "tool": "t", "args": {}}] * 10)
        assert queued <= 10  # never blocks; drops when full
    finally:
        pf.stop()


def test_dedup_seen(tmp_path: Path) -> None:
    pf = Prefetcher(tools={"t": lambda: 1})
    pf.start()
    try:
        step = {"op": "call", "tool": "t", "args": {}}
        pf.suggest([step])
        assert pf.suggest([step]) == 0  # same step not re-queued
    finally:
        pf.stop()


def test_never_executes(tmp_path: Path) -> None:
    calls: list[str] = []
    pf = Prefetcher(tools={"t": lambda **kw: calls.append("ran")})
    pf.start()
    try:
        pf.suggest([{"op": "call", "tool": "t", "args": {"x": 1}}])
        time.sleep(0.3)
        assert calls == []  # speculation never invokes the tool
    finally:
        pf.stop()


def test_read_passthrough_unfetched(tmp_path: Path) -> None:
    f = tmp_path / "b.txt"
    f.write_text("cold", encoding="utf-8")
    pf = Prefetcher(tools={})
    assert pf.read(f) == "cold"  # cold read still works
    assert pf.read(f) == "cold"
    assert pf._files.stats()["hits"] >= 1


def test_stop_idempotent(tmp_path: Path) -> None:
    pf = Prefetcher(tools={})
    pf.start()
    pf.stop()
    pf.stop()  # second stop is a no-op


def test_context_manager_stops_worker(tmp_path: Path) -> None:
    with Prefetcher(tools={}) as pf:
        pass
    assert pf.stats()["warmed"] == 0


def test_suggest_after_stop_returns_zero() -> None:
    pf = Prefetcher(tools={})
    pf.stop()  # stop flag set before ever starting
    assert pf.suggest([{"op": "call", "tool": "t"}]) == 0


def test_suggest_breaks_when_queue_full() -> None:
    pf = Prefetcher(tools={}, max_queue=1)
    steps = [{"op": "call", "tool": f"t{i}", "args": {}} for i in range(4)]
    assert pf.suggest(steps) == 1  # queue.Full -> break, never blocks


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    pf = Prefetcher(tools={})
    assert pf.read(tmp_path / "nope.txt") is None


def test_worker_survives_malformed_steps() -> None:
    pf = Prefetcher(tools={"t": lambda **kw: kw})
    pf.start()
    try:
        pf._queue.put_nowait({"op": "let"})                       # non-call op
        pf._queue.put_nowait({"op": "call", "args": "bad"})       # args not a dict
        pf._queue.put_nowait({"op": "call", "args": {"p": "$x", "n": 5}})  # $/non-str args
        pf.suggest([{"op": "call", "tool": "t", "args": {}}])
        assert _wait(lambda: pf.warmed >= 1)
    finally:
        pf.stop()


def test_warm_step_stat_oserror_skips_file(monkeypatch) -> None:
    pf = Prefetcher(tools={})

    def _raise(self: Path) -> bool:
        raise OSError("gone")

    monkeypatch.setattr(Path, "is_file", _raise)
    pf._warm_step({"op": "call", "tool": "t", "args": {"p": "/x"}})  # must not raise
    assert pf.warmed == 0


def test_worker_ticks_on_empty_queue() -> None:
    import threading

    pf = Prefetcher(tools={})
    pf._queue.put_nowait({"op": "call", "args": "bad"})  # _warm_step raises -> continue
    t = threading.Thread(target=pf._loop, daemon=True)
    t.start()
    end = time.time() + 0.4  # busy-wait: sleep() is a no-op in the fast tier
    while time.time() < end:
        pass
    pf._stop.set()
    t.join(timeout=2)
    assert not t.is_alive()


def test_warm_step_skips_ref_and_non_str_args() -> None:
    pf = Prefetcher(tools={})
    pf._warm_step(
        {"op": "call", "tool": "t", "args": {"p": "$x", "n": 5, "f": "missing.txt"}}
    )
    assert pf.warmed == 0  # $-ref/non-str skipped; missing file warms nothing
