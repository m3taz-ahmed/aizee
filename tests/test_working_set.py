"""Tests for runtime/working_set.py — bounded LRU active-frame pool."""

from __future__ import annotations

import pytest

from runtime.working_set import WorkingSet


def test_put_get_roundtrip() -> None:
    ws = WorkingSet(max_entries=4)
    ws.put("a", 1)
    assert ws.get("a") == 1
    assert "a" in ws
    assert len(ws) == 1


def test_lru_eviction() -> None:
    ws = WorkingSet(max_entries=2)
    ws.put("a", 1)
    ws.put("b", 2)
    ws.put("c", 3)  # evicts "a" (least recent)
    assert "a" not in ws
    assert ws.get("b") == 2
    assert ws.get("c") == 3


def test_access_refreshes_recency() -> None:
    ws = WorkingSet(max_entries=2)
    ws.put("a", 1)
    ws.put("b", 2)
    ws.get("a")  # refresh — now "b" is oldest
    ws.put("c", 3)
    assert "a" in ws
    assert "b" not in ws


def test_on_evict_callback() -> None:
    evicted: list[tuple[str, int]] = []
    ws = WorkingSet(max_entries=1, on_evict=lambda k, v: evicted.append((k, v)))
    ws.put("a", 1)
    ws.put("b", 2)
    assert evicted == [("a", 1)]


def test_hit_miss_stats() -> None:
    ws = WorkingSet(max_entries=4)
    ws.put("a", 1)
    ws.get("a")
    ws.get("missing")
    stats = ws.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
    assert stats["max_entries"] == 4


def test_evict_oldest_manual() -> None:
    ws = WorkingSet(max_entries=4)
    for i in range(3):
        ws.put(i, i)
    ws.evict_oldest(2)
    assert len(ws) == 1
    assert 2 in ws  # newest survives


def test_keys_recent_order() -> None:
    ws = WorkingSet(max_entries=4)
    for k in ("a", "b", "c"):
        ws.put(k, k)
    assert ws.keys_recent() == ["a", "b", "c"]
    assert ws.keys_recent(limit=2) == ["b", "c"]


def test_invalid_size() -> None:
    with pytest.raises(ValueError):
        WorkingSet(max_entries=0)


def test_take_recent_atomic_drain() -> None:
    ws = WorkingSet(max_entries=8)
    ws.put("a", 1)
    ws.put("b", 2)
    ws.put("c", 3)
    assert ws.take_recent() == [("a", 1), ("b", 2), ("c", 3)]
    assert len(ws) == 0


def test_take_recent_limit_keeps_rest() -> None:
    ws = WorkingSet(max_entries=8)
    ws.put("a", 1)
    ws.put("b", 2)
    assert ws.take_recent(1) == [("b", 2)]
    assert ws.keys_recent() == ["a"]


def test_evict_oldest_fires_callback() -> None:
    evicted: list[tuple] = []
    ws = WorkingSet(max_entries=8, on_evict=lambda k, v: evicted.append((k, v)))
    ws.put("a", 1)
    ws.put("b", 2)
    ws.evict_oldest(1)
    assert evicted == [("a", 1)]
    assert ws.keys_recent() == ["b"]


def test_iter_yields_oldest_first() -> None:
    ws = WorkingSet(max_entries=4)
    ws.put("x", 1)
    ws.put("y", 2)
    assert list(ws) == ["x", "y"]
