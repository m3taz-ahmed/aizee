"""Tests for runtime/task_farm.py — leases, heartbeats, reaping."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from runtime.task_farm import FarmError, TaskFarm


def _expire_lease(farm: TaskFarm, task_id: str) -> None:
    """Force a leased task's lease into the past (time.sleep is a no-op here)."""
    path = farm._task_path(task_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["lease_until"] = time.time() - 1.0
    path.write_text(json.dumps(data), encoding="utf-8")


def test_submit_claim_complete(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("echo", {"a": 1}, name="t1")
    claimed = farm.claim("w1", lease_seconds=30)
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == "leased"
    assert claimed.worker == "w1"
    assert claimed.attempts == 1
    done = farm.complete("w1", task.id, result={"ok": True})
    assert done.status == "done"
    assert farm.claim("w1") is None  # nothing left


def test_claim_oldest_first(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    first = farm.submit("a", {})
    farm.submit("b", {})
    assert farm.claim("w").id == first.id


def test_double_claim_isolated(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("a", {})
    assert farm.claim("w1") is not None
    assert farm.claim("w2") is None  # leased task invisible to others


def test_heartbeat_extends_lease(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("a", {})
    farm.claim("w1", lease_seconds=10)
    renewed = farm.heartbeat("w1", task.id, extend=60)
    assert renewed.lease_until > time.time() + 50


def test_heartbeat_wrong_worker_rejected(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("a", {})
    farm.claim("w1")
    with pytest.raises(FarmError) as exc:
        farm.heartbeat("w2", task.id)
    assert exc.value.error_code == "LEASE_LOST"


def test_fail_requeues_then_dead_letters(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("a", {}, max_attempts=2)
    farm.claim("w")
    farm.fail("w", task.id, "boom")
    # attempt 1 of 2 used -> back to pending
    assert farm._load_task(task.id).status == "pending"
    farm.claim("w")
    farm.fail("w", task.id, "boom2")
    assert farm._load_task(task.id).status == "dead"


def test_reap_expired_requeues(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("a", {})
    claimed = farm.claim("w", lease_seconds=0.0)
    assert claimed is not None
    # lease already expired (0s) -> reaper puts it back
    reaped = farm.reap_expired()
    assert task.id in reaped
    assert farm._load_task(task.id).status == "pending"


def test_complete_after_expiry_rejected(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    task = farm.submit("a", {})
    farm.claim("w", lease_seconds=0.0)
    time.sleep(0.01)
    with pytest.raises(FarmError) as exc:
        farm.complete("w", task.id)
    assert exc.value.error_code == "LEASE_EXPIRED"


def test_capacity_bound(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm", max_tasks=2)
    farm.submit("a", {})
    farm.submit("b", {})
    with pytest.raises(FarmError) as exc:
        farm.submit("c", {})
    assert exc.value.error_code == "FARM_FULL"


def test_stats_and_list(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("a", {})
    farm.submit("b", {})
    farm.claim("w")
    stats = farm.stats()
    assert stats["counts"]["leased"] == 1
    assert stats["counts"]["pending"] == 1
    assert "w" in stats["workers"]
    assert len(farm.list_tasks(status="pending")) == 1


def test_corrupt_task_file_skipped(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    (tmp_path / "farm" / "tasks" / "bad.json").write_text("{broken", encoding="utf-8")
    assert farm.list_tasks() == []  # no crash


def test_traversal_ids_rejected(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("t", {})
    import pytest

    from runtime.task_farm import FarmError

    for bad in ("../x", "..\\x", "a/b", "a\\b", "", "x y", "x:y"):
        with pytest.raises(FarmError) as exc:
            farm.heartbeat("w", bad)
        assert exc.value.error_code == "BAD_ID"
        with pytest.raises(FarmError):
            farm.claim(bad)


def test_submit_empty_tool_rejected(tmp_path: Path) -> None:
    """REGRESSION: a tool-less task can never run — reject at submit time."""
    farm = TaskFarm(tmp_path / "farm")
    with pytest.raises(FarmError) as exc:
        farm.submit("", {})
    assert exc.value.error_code == "BAD_TOOL"


def test_load_missing_and_corrupt_task(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    with pytest.raises(FarmError) as exc:
        farm.complete("w", "missing")
    assert exc.value.error_code == "NO_TASK"
    task = farm.submit("t", {}, name="bad")
    farm._task_path(task.id).write_text("{corrupt", encoding="utf-8")
    with pytest.raises(FarmError) as exc2:
        farm.complete("w", task.id)
    assert exc2.value.error_code == "CORRUPT"


def test_reap_expired_skips_live_requeues_and_dead_letters(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    live = farm.submit("t", {})
    farm.claim("w", lease_seconds=30)  # leased + unexpired -> skipped
    farm.submit("t", {}, name="d", max_attempts=1)
    d = farm.claim("w2", lease_seconds=0.02)
    assert d is not None
    _expire_lease(farm, d.id)
    reaped = farm.reap_expired()
    assert d.id in reaped
    assert farm._load_task(d.id).status == "dead"  # attempts >= max -> dead-letter
    assert farm._load_task(live.id).status == "leased"
    farm.submit("t", {}, name="p", max_attempts=3)
    c = farm.claim("w3", lease_seconds=0.02)
    assert c is not None
    _expire_lease(farm, c.id)
    farm.reap_expired()
    assert farm._load_task(c.id).status == "pending"


def test_complete_after_lease_expiry_requeues(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("t", {})
    claimed = farm.claim("w", lease_seconds=0.02)
    assert claimed is not None
    _expire_lease(farm, claimed.id)
    with pytest.raises(FarmError) as exc:
        farm.complete("w", claimed.id, result={})
    assert exc.value.error_code == "LEASE_EXPIRED"
    assert farm._load_task(claimed.id).status == "pending"


def test_corrupt_worker_files_are_replaced(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("t", {})
    farm._workers.mkdir(parents=True, exist_ok=True)
    (farm._workers / "w1.json").write_text("{bad", encoding="utf-8")
    assert farm.stats()["workers"] == {}  # unreadable worker skipped
    farm._bump_worker("w1", leased=1)  # corrupt file -> falls back to fresh
    (farm._workers / "w1.json").write_text("{bad", encoding="utf-8")
    c = farm.claim("w1", lease_seconds=30)  # _touch_worker falls back to fresh
    assert c is not None
    farm.heartbeat("w1", c.id)
    assert farm.stats()["workers"]["w1"] > 0


def test_complete_by_wrong_worker_rejected(tmp_path: Path) -> None:
    farm = TaskFarm(tmp_path / "farm")
    farm.submit("t", {})
    claimed = farm.claim("w", lease_seconds=30)
    assert claimed is not None
    with pytest.raises(FarmError) as exc:
        farm.complete("intruder", claimed.id, result={})
    assert exc.value.error_code == "NOT_LEASED"
