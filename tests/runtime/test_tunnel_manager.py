"""Tests for runtime/tunnel_manager.py — governed tunnel lifecycle."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime import tunnel_manager as tm

_FAKE_CMD = (
    "import time; print('https://abc-123.trycloudflare.com', flush=True); time.sleep(60)"
)
FAKE_PROVIDERS = {
    "fake": {
        "cmd": [sys.executable, "-c", _FAKE_CMD],
        "pattern": r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
    },
    "silent": {
        "cmd": [sys.executable, "-c", "import time; time.sleep(60)"],
        "pattern": r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
    },
    "dying": {
        "cmd": [sys.executable, "-c", "print('bye')"],
        "pattern": r"https://[a-zA-Z0-9-]+\.trycloudflare\.com",
    },
}


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


def test_start_and_stop_roundtrip(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    assert res["ok"] and res["url"] == "https://abc-123.trycloudflare.com"
    assert res["status"] == "active" and res["pid"] > 0
    state = json.loads((root / "state" / "tunnels" / f"{res['id']}.json").read_text())
    assert state["url"] == res["url"]
    try:
        stop = tm.stop(root, res["id"])
        assert stop["ok"] and stop["status"] == "stopped"
    finally:
        tm._terminate_pid(res["pid"])  # belt-and-braces cleanup


def test_start_unknown_provider(root: Path) -> None:
    res = tm.start(root, "nope", 8080, providers=FAKE_PROVIDERS)
    assert not res["ok"] and "unknown provider" in res["error"]


def test_start_invalid_port(root: Path) -> None:
    res = tm.start(root, "fake", 70000, providers=FAKE_PROVIDERS)
    assert not res["ok"] and "invalid port" in res["error"]


def test_start_ttl_clamped(root: Path) -> None:
    res = tm.start(root, "fake", 8080, ttl_s=999999, providers=FAKE_PROVIDERS)
    try:
        assert res["ttl_s"] == 14400
    finally:
        tm.stop(root, res["id"])
        tm._terminate_pid(res["pid"])


def test_start_spawn_failure(root: Path) -> None:
    bad = {"bad": {"cmd": ["definitely-not-a-real-binary-xyz"], "pattern": "x"}}
    res = tm.start(root, "bad", 8080, providers=bad)
    assert not res["ok"] and "failed to start" in res["error"]


def test_start_no_url_times_out(root: Path) -> None:
    res = tm.start(root, "silent", 8080, providers=FAKE_PROVIDERS, timeout_s=1.0)
    assert not res["ok"] and "no public URL" in res["error"]
    state = tm._load(root, res["id"])
    assert state["status"] == "failed"


def test_stop_unknown(root: Path) -> None:
    assert not tm.stop(root, "deadbeefdead")["ok"]


def test_stop_already_stopped(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    tm.stop(root, res["id"])
    again = tm.stop(root, res["id"])
    assert again["ok"] and again.get("already") is True


def test_status_active_and_dead(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    tid = res["id"]
    st = tm.status(root, tid)
    assert st["ok"] and st["status"] == "active" and st["alive"] is True
    tm._terminate_pid(res["pid"])
    time.sleep(0.3)
    st2 = tm.status(root, tid)
    assert st2["status"] == "dead"
    tm.stop(root, tid)


def test_status_unknown(root: Path) -> None:
    assert not tm.status(root, "deadbeefdead")["ok"]


def test_status_expired_sweeps(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    state = tm._load(root, res["id"])
    state["expires_at"] = time.time() - 10
    tm._save(root, state)
    st = tm.status(root, res["id"])
    assert st["status"] == "stopped"


def test_load_rejects_bad_id(root: Path) -> None:
    assert tm._load(root, "../evil") is None
    assert tm._load(root, "zzzzzzzzzzzz") is None


def test_load_corrupt_json(root: Path) -> None:
    tdir = root / "state" / "tunnels"
    tdir.mkdir(parents=True)
    (tdir / "abcdef123456.json").write_text("{corrupt", encoding="utf-8")
    assert tm._load(root, "abcdef123456") is None


def test_pid_alive_false_for_dead() -> None:
    assert tm._pid_alive(2**22 + 12345) is False


def test_terminate_pid_missing() -> None:
    assert tm._terminate_pid(2**22 + 12345) is False


def test_list_empty(root: Path) -> None:
    res = tm.list_tunnels(root)
    assert res["ok"] and res["count"] == 0


def test_list_redacts_url(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    try:
        listing = tm.list_tunnels(root)
        assert listing["count"] == 1
        assert "url" not in listing["tunnels"][0]
        no_sweep = tm.list_tunnels(root, sweep=False)
        assert no_sweep["count"] == 1
    finally:
        tm.stop(root, res["id"])
        tm._terminate_pid(res["pid"])


def test_audit_failure_tolerated(root: Path) -> None:
    with patch("runtime.audit.AuditLogger", side_effect=RuntimeError("audit down")):
        res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
        assert res["ok"]
        assert tm.stop(root, res["id"])["ok"]


def test_log_unwritable(root: Path) -> None:
    import builtins

    real_open = builtins.open

    def failing_open(file, *a, **kw):
        if str(file).endswith(".log"):
            raise OSError("ro")
        return real_open(file, *a, **kw)

    with patch("builtins.open", failing_open):
        res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    assert not res["ok"] and "log file unavailable" in res["error"]


def test_start_process_exits_before_url(root: Path) -> None:
    res = tm.start(root, "dying", 8080, providers=FAKE_PROVIDERS, timeout_s=5.0)
    assert not res["ok"] and "no public URL" in res["error"]


def test_start_log_read_oserror(root: Path) -> None:
    with patch.object(Path, "read_text", side_effect=OSError("gone")):
        res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS, timeout_s=1.0)
    assert not res["ok"]
    tm._terminate_pid(res.get("pid", 0) or 0)


def test_terminate_fallback_to_kill() -> None:
    from unittest.mock import MagicMock

    import psutil

    mock_proc = MagicMock()
    mock_proc.terminate.side_effect = psutil.NoSuchProcess(12345)
    with patch.object(tm.psutil, "Process", return_value=mock_proc):
        assert tm._terminate_pid(12345) is True
        mock_proc.kill.assert_called_once()


def test_terminate_kill_also_fails() -> None:
    from unittest.mock import MagicMock

    import psutil

    mock_proc = MagicMock()
    mock_proc.terminate.side_effect = psutil.NoSuchProcess(12345)
    mock_proc.kill.side_effect = psutil.NoSuchProcess(12345)
    with patch.object(tm.psutil, "Process", return_value=mock_proc):
        assert tm._terminate_pid(12345) is False


def test_status_stopped_skips_sweep_branch(root: Path) -> None:
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    tm.stop(root, res["id"])
    st = tm.status(root, res["id"])
    assert st["status"] == "stopped" and st["alive"] is False


def test_list_skips_entries_without_id(root: Path) -> None:
    tdir = root / "state" / "tunnels"
    tdir.mkdir(parents=True)
    (tdir / "nothexid!.json").write_text("{}", encoding="utf-8")
    res = tm.start(root, "fake", 8080, providers=FAKE_PROVIDERS)
    try:
        listing = tm.list_tunnels(root, sweep=False)
        assert listing["count"] == 1  # corrupt entry skipped, real one listed
    finally:
        tm.stop(root, res["id"])
        tm._terminate_pid(res["pid"])
