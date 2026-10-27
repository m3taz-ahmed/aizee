"""Batch-5 adoption tests: context_composition + inventory_note + plugin_transactions.

DeepTutor-derived: context-window composition telemetry, manifest-pattern
inventory facts, and lockfile-serialized plugin state transactions.
"""

from __future__ import annotations

import sqlite3
import sys
import threading
from pathlib import Path

import pytest
import yaml

from runtime import context_composition as cc
from runtime import inventory_note as inv
from runtime import plugin_transactions as pt

# ---------------------------------------------------------------------------
# context_composition
# ---------------------------------------------------------------------------


def test_default_token_counter_empty_and_scaling() -> None:
    assert cc.default_token_counter("") == 0
    assert cc.default_token_counter("ab") == 1
    assert cc.default_token_counter("x" * 400) == 100


def test_measure_sorts_desc_and_reports_utilization() -> None:
    report = cc.measure(
        [("small", "x" * 40), cc.ContextSegment("big", "x" * 400), ("mid", "x" * 200)],
        window_tokens=200,
    )
    assert [s.name for s in report.segments] == ["big", "mid", "small"]
    assert report.total_tokens == 160
    assert report.window_tokens == 200
    assert report.utilization == pytest.approx(0.8)
    assert report.over_budget is False
    assert report.dominant == "big"
    assert report.segments[0].share_of_window == pytest.approx(0.5)
    assert report.segments[0].share_of_total == pytest.approx(0.625)


def test_measure_over_budget_and_zero_window() -> None:
    over = cc.measure([("a", "x" * 400)], window_tokens=50)
    assert over.over_budget is True
    assert over.utilization > 1.0
    no_window = cc.measure([("a", "x" * 400)], window_tokens=0)
    assert no_window.over_budget is False
    assert no_window.utilization == 0.0
    assert no_window.segments[0].share_of_window == 0.0
    empty = cc.measure([], window_tokens=100)
    assert empty.dominant == ""
    assert empty.segments == []


def test_measure_custom_counter_and_degraded_counter() -> None:
    report = cc.measure(
        [("a", "xyz")], window_tokens=10, token_counter=lambda t: len(t)
    )
    assert report.segments[0].tokens == 3

    def boom(_t: str) -> int:
        raise RuntimeError("counter exploded")

    degraded = cc.measure([("bad", "text"), ("ok", "text")], window_tokens=10, token_counter=boom)
    assert degraded.degraded == ["bad", "ok"]
    assert degraded.total_tokens == 0


def test_render_and_to_dict() -> None:
    report = cc.measure([("memory", "x" * 400), ("tools", "x" * 100)], window_tokens=50)
    text = report.render()
    assert "memory" in text and "tools" in text
    assert "OVER" in text and "250.0%" in text
    d = report.to_dict()
    assert d["over_budget"] is True
    assert d["dominant"] == "memory"
    assert len(d["segments"]) == 2

    degraded = cc.measure(
        [("bad", "x")], window_tokens=5, token_counter=lambda _t: 1 / 0  # type: ignore[return-value]
    )
    assert "degraded" in degraded.render()


# ---------------------------------------------------------------------------
# inventory_note
# ---------------------------------------------------------------------------


def _build_root(tmp_path: Path) -> Path:
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "a.md").write_text("---\nalways: true\n---\nx", encoding="utf-8")
    (tmp_path / "skills" / "b.md").write_text("---\nname: b\n---\nx", encoding="utf-8")
    (tmp_path / "skills" / "README.md").write_text("docs", encoding="utf-8")
    sub = tmp_path / "skills" / "c"
    sub.mkdir()
    (sub / "SKILL.md").write_text("---\nalways: true\n---\nx", encoding="utf-8")
    sub2 = tmp_path / "skills" / "d"
    sub2.mkdir()
    (sub2 / "SKILL.md").write_text("---\nname: d\n---\nx", encoding="utf-8")
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "01-a.md").write_text("w", encoding="utf-8")
    (tmp_path / "workflows" / "notes.md").write_text("w", encoding="utf-8")
    (tmp_path / "tech-stack").mkdir()
    (tmp_path / "tech-stack" / "python-3.11.md").write_text("t", encoding="utf-8")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "kernel.py").write_text("k", encoding="utf-8")
    (tmp_path / "runtime" / "policy.py").write_text("p", encoding="utf-8")
    (tmp_path / "plugins.yaml").write_text(
        yaml.safe_dump({"plugins": {"x": {"enabled": True}, "y": {"enabled": False}}}),
        encoding="utf-8",
    )
    return tmp_path


def test_collect_inventory_counts_everything(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    mem = root / "memory"
    mem.mkdir()
    db = mem / "store.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE memories (id TEXT PRIMARY KEY, bank TEXT, deleted_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO memories VALUES (?, ?, ?)",
            [("1", "global", None), ("2", "work", None), ("3", "work", "2026-01-01")],
        )
    result = inv.collect_inventory(root)
    assert result.skills == 4
    assert result.skills_always == 2
    assert result.workflows == 1
    assert result.tech_stack_refs == 1
    assert result.runtime_modules == 2
    assert result.memory_banks == 2
    assert result.memory_entries == 2
    assert result.bank_names == ["global", "work"]
    assert result.plugins == 2
    assert result.plugins_enabled == 1


def test_collect_inventory_empty_root(tmp_path: Path) -> None:
    result = inv.collect_inventory(tmp_path)
    assert result.skills == 0
    assert result.memory_banks == 0
    assert result.bank_names == []


def test_collect_inventory_tolerates_corrupt_inputs(tmp_path: Path) -> None:
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "store.db").write_bytes(b"not a sqlite db")
    (tmp_path / "plugins.yaml").write_text("{unclosed: [", encoding="utf-8")
    result = inv.collect_inventory(tmp_path)
    assert result.memory_banks == 0
    assert result.plugins == 0

    (tmp_path / "plugins.yaml").write_text("plugins: not_a_dict", encoding="utf-8")
    assert inv.collect_inventory(tmp_path).plugins == 0

    (tmp_path / "plugins.yaml").write_text(
        yaml.safe_dump({"plugins": {"z": {"enabled": True}}}), encoding="utf-8"
    )
    assert inv.collect_inventory(tmp_path).plugins_enabled == 1


def test_render_note_and_report() -> None:
    note = inv.render_inventory_note(inv.Inventory(skills=5, skills_always=2, memory_entries=9, memory_banks=2))
    assert "skills: 5" in note and "9 entries" in note
    assert "Inventory questions" in note

    report = inv.render_inventory_report(
        inv.Inventory(skills=5, bank_names=["global", "work"], plugins=3, plugins_enabled=1)
    )
    assert "skills" in report and "global, work" in report
    assert "1 enabled of 3" in report

    no_banks = inv.render_inventory_report(inv.Inventory())
    assert "banks" not in no_banks

    assert inv.Inventory(skills=2).to_dict()["skills"] == 2


def test_memory_counts_missing_db(tmp_path: Path) -> None:
    assert inv._memory_counts(tmp_path) == (0, 0, [])


def test_plugin_counts_yaml_unimportable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "plugins.yaml").write_text("plugins: {}", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)
    assert inv._plugin_counts(tmp_path) == (0, 0)


# ---------------------------------------------------------------------------
# plugin_transactions
# ---------------------------------------------------------------------------


def test_state_lock_serializes_and_releases(tmp_path: Path) -> None:
    state = tmp_path / "plugins.yaml"
    state.write_text("plugins: {}", encoding="utf-8")
    entered = threading.Event()
    proceed = threading.Event()

    def holder() -> None:
        with pt.plugin_state_lock(state):
            entered.set()
            proceed.wait(timeout=5)

    t = threading.Thread(target=holder)
    t.start()
    assert entered.wait(timeout=5)
    with pytest.raises(pt.PluginStateError, match="Another plugin state transaction"):
        with pt.plugin_state_lock(state):
            pass
    proceed.set()
    t.join(timeout=5)
    # released: reacquire succeeds
    with pt.plugin_state_lock(state):
        pass


def test_state_lock_posix_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    class _FakeFcntl:
        LOCK_EX = 1
        LOCK_NB = 2
        LOCK_UN = 8

        @staticmethod
        def flock(_fd: int, op: int) -> None:
            calls.append(op)

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "fcntl", _FakeFcntl)
    state = tmp_path / "plugins.yaml"
    with pt.plugin_state_lock(state):
        pass
    assert calls == [_FakeFcntl.LOCK_EX | _FakeFcntl.LOCK_NB, _FakeFcntl.LOCK_UN]


def test_posix_lock_contention_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _DenyFcntl:
        LOCK_EX = 1
        LOCK_NB = 2
        LOCK_UN = 8

        @staticmethod
        def flock(_fd: int, _op: int) -> None:
            raise OSError("locked")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "fcntl", _DenyFcntl)
    with pytest.raises(pt.PluginStateError):
        with pt.plugin_state_lock(tmp_path / "plugins.yaml"):
            pass


def test_mutate_and_set_enabled(tmp_path: Path) -> None:
    prior = pt.set_plugin_enabled(tmp_path, "weather", True)
    assert prior is False
    data = yaml.safe_load((tmp_path / "plugins.yaml").read_text(encoding="utf-8"))
    assert data["plugins"]["weather"]["enabled"] is True

    prior = pt.set_plugin_enabled(tmp_path, "weather", False)
    assert prior is True
    data = yaml.safe_load((tmp_path / "plugins.yaml").read_text(encoding="utf-8"))
    assert data["plugins"]["weather"]["enabled"] is False


def test_mutate_preserves_existing_and_readonly_probe(tmp_path: Path) -> None:
    cfg_path = tmp_path / "plugins.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"top": 1, "plugins": {"keep": {"enabled": True, "permissions": ["net"]}}}),
        encoding="utf-8",
    )
    mtime_probe = pt.mutate_plugins_yaml(tmp_path, lambda cfg: None)  # read-only
    assert mtime_probe is None

    result = pt.mutate_plugins_yaml(
        tmp_path, lambda cfg: cfg["plugins"]["keep"]["permissions"]
    )
    assert result == ["net"]
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["top"] == 1  # unrelated keys preserved


def test_mutate_corrupt_and_nondict_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "plugins.yaml"
    cfg_path.write_text("{unclosed: [", encoding="utf-8")
    with pytest.raises(pt.PluginStateError, match="unreadable"):
        pt.mutate_plugins_yaml(tmp_path, lambda cfg: True)

    cfg_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    pt.set_plugin_enabled(tmp_path, "x", True)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["plugins"]["x"]["enabled"] is True


def test_serialized_decorator(tmp_path: Path) -> None:
    class Registry:
        state_path = tmp_path / "plugins.yaml"

        @pt.serialized
        def bump(self) -> int:
            return 42

    assert Registry().bump() == 42


def test_atomic_write_cleans_tmp_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(_src: str, _dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pt.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        pt._atomic_write(tmp_path / "out.yaml", "data: 1")
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


# ---------------------------------------------------------------------------
# gateway_proxy — context-composition wiring (measure_request + Provider window)
# ---------------------------------------------------------------------------


def test_payload_segments_shapes() -> None:
    import runtime.gateway_proxy as gp

    payload = {
        "system": "be terse",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]},
            {"role": "user", "content": [{"type": "image"}]},  # no text -> skipped
            {"role": "user", "content": ""},  # empty -> skipped
        ],
        "tools": [{"name": "t1"}],
        "prompt": "extra",
    }
    names = [name for name, _text in gp.payload_segments(payload)]
    assert names == [
        "system",
        "messages[0]:user",
        "messages[1]:assistant",
        "tools",
        "prompt",
    ]
    # system as content-block list
    seg2 = gp.payload_segments({"system": [{"text": "sys-blk"}]})
    assert seg2 == [("system", "sys-blk")]
    # system list with no text blocks -> skipped entirely
    assert gp.payload_segments({"system": [{"type": "image"}]}) == []
    assert gp.payload_segments({}) == []


def test_measure_request_report() -> None:
    import runtime.gateway_proxy as gp

    report = gp.measure_request(
        {"system": "s" * 40, "messages": [{"role": "user", "content": "u" * 40}]},
        window_tokens=100,
    )
    assert report.total_tokens == 20
    assert report.dominant in ("system", "messages[0]:user")
    assert report.over_budget is False


def test_gate_attaches_composition_to_kernel_act() -> None:
    import io
    from unittest.mock import MagicMock

    import runtime.gateway_proxy as gp

    kernel = MagicMock()
    kernel.act.return_value = {"ok": True}
    provider = gp.Provider(
        name="p1", base_url="https://x", context_window=200, tiers=("flash",)
    )
    cfg = gp.GatewayConfig(providers=(provider,), verify="off")
    handler_cls = gp.make_handler(cfg, kernel)
    req = handler_cls.__new__(handler_cls)
    req.rfile = io.BytesIO(b"")  # type: ignore[attr-defined]
    payload = {
        "tier": "flash",
        "system": "s" * 400,
        "messages": [{"role": "user", "content": "u" * 400}],
    }
    assert req._gate(payload) is None
    kwargs = kernel.act.call_args.kwargs
    assert kwargs["context_total"] == 200
    assert kwargs["context_utilization"] == 1.0
    assert kwargs["context_dominant"] in ("system", "messages[0]:user")


def test_gate_window_from_metadata_tier_and_none_declared() -> None:
    import io
    from unittest.mock import MagicMock

    import runtime.gateway_proxy as gp

    kernel = MagicMock()
    kernel.act.return_value = {"ok": True}
    provider = gp.Provider(name="p1", base_url="https://x")  # context_window=0
    cfg = gp.GatewayConfig(providers=(provider,), verify="off")
    handler_cls = gp.make_handler(cfg, kernel)
    req = handler_cls.__new__(handler_cls)
    req.rfile = io.BytesIO(b"")  # type: ignore[attr-defined]
    req._gate({"metadata": {"tier": "extraction"}, "messages": [{"content": "x" * 4}]})
    kwargs = kernel.act.call_args.kwargs
    assert kwargs["context_utilization"] == 0.0  # no window declared


def test_provider_context_window_yaml(tmp_path: Path) -> None:
    import runtime.gateway_proxy as gp

    cfg_path = tmp_path / "gateway.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "providers": [
                    {"name": "a", "base_url": "https://a", "context_window": 128000},
                    {"name": "b", "base_url": "https://b"},
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = gp.GatewayConfig.load(cfg_path)
    assert cfg.providers[0].context_window == 128000
    assert cfg.providers[1].context_window == 0
