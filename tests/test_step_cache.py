"""Tests for runtime/step_cache.py — content-hash memoization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.schemas import ValidationError
from runtime.step_cache import MISSING, StepCache


def test_key_deterministic_and_arg_order_invariant() -> None:
    a = StepCache.key_for("tool", {"x": 1, "y": 2})
    b = StepCache.key_for("tool", {"y": 2, "x": 1})
    assert a == b
    assert a != StepCache.key_for("tool", {"x": 1, "y": 3})
    assert a != StepCache.key_for("other", {"x": 1, "y": 2})


def test_get_tolerates_corrupt_cache_file(tmp_path: Path) -> None:
    c = StepCache(tmp_path / "c")
    (tmp_path / "c").mkdir(parents=True)
    (tmp_path / "c" / "k.json").write_text("{not json", encoding="utf-8")
    assert c.get("k") is MISSING


def test_put_is_noop_when_dir_unwritable(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    c = StepCache(blocker / "sub")  # mkdir under a file -> OSError
    c.put("k", 1)  # swallowed — the cache must never break a run
    assert c.stores == 0


def test_clear_missing_dir(tmp_path: Path) -> None:
    assert StepCache(tmp_path / "nope").clear() == 0


def test_clear_skips_undeletable_file(tmp_path: Path) -> None:
    c = StepCache(tmp_path / "c")
    c.put("a", 1)
    victim = tmp_path / "c" / "a.json"
    with victim.open("r", encoding="utf-8"):
        c.clear()  # unlink OSError (Windows open-handle) must not propagate
    c.clear()
    assert c.stats()["files"] == 0


def test_put_get_roundtrip(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "cache")
    key = cache.key_for("t", {"a": 1})
    assert cache.get(key) is MISSING
    cache.put(key, {"r": 42}, tool="t")
    assert cache.get(key) == {"r": 42}


def test_persistence_across_instances(tmp_path: Path) -> None:
    d = tmp_path / "cache"
    key = StepCache.key_for("t", {"a": 1})
    StepCache(d).put(key, "v")
    assert StepCache(d).get(key) == "v"  # new instance reads disk


def test_non_serializable_skipped(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "cache")
    cache.put("k", object())
    assert cache.get("k") is MISSING
    assert not list((tmp_path / "cache").glob("*.json"))


def test_clear(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "cache")
    cache.put("k1", 1)
    cache.put("k2", 2)
    assert cache.clear() == 2
    assert cache.get("k1") is MISSING


def test_stats(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "cache")
    cache.put("k", "v")
    cache.get("k")
    stats = cache.stats()
    assert stats["files"] == 1
    assert stats["hits"] >= 1
    assert stats["stores"] == 1


def test_atomic_record_format(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "cache")
    cache.put("abc", {"v": 1}, tool="t")
    rec = json.loads((tmp_path / "cache" / "abc.json").read_text())
    assert rec == {"key": "abc", "tool": "t", "value": {"v": 1}}


def test_bad_key_rejected(tmp_path: Path) -> None:
    """REGRESSION: keys become filenames — separators must not escape the dir."""
    cache = StepCache(tmp_path / "cache")
    with pytest.raises(ValidationError):
        cache.put("../evil", 1)
    with pytest.raises(ValidationError):
        cache.get("a/b")
    assert not (tmp_path / "evil.json").exists()


def test_clear_removes_tmp_orphans(tmp_path: Path) -> None:
    """Crash-orphaned .tmp files must not survive a clear()."""
    d = tmp_path / "cache"
    d.mkdir()
    (d / ".deadbeef.tmp").write_text("{}", encoding="utf-8")
    cache = StepCache(d)
    assert cache.clear() == 1
    assert not list(d.iterdir())
