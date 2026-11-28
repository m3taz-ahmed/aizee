"""CLI wiring tests for the tunnel command and codemode --adapters flag."""

from __future__ import annotations

import shutil
import tempfile
from unittest.mock import patch

import pytest

from aizee_cli import main


@pytest.fixture()
def tmp_root():
    d = tempfile.mkdtemp(prefix="aizee_cli_tc_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_codemode_adapters_ok(tmp_root, capsys) -> None:
    with patch("runtime.codemode.adapters.generate", return_value={"ok": True, "written": 3}):
        rc = main(["--root", tmp_root, "codemode", "--adapters"])
    assert rc == 0 and "written" in capsys.readouterr().out


def test_codemode_adapters_failure(tmp_root) -> None:
    with patch("runtime.codemode.adapters.generate", return_value={"ok": False, "written": 0}):
        rc = main(["--root", tmp_root, "codemode", "--adapters", "--server", "graphify"])
    assert rc == 1


def test_tunnel_start_ok(tmp_root, capsys) -> None:
    with patch("runtime.tunnel_manager.start", return_value={"ok": True, "id": "abc123abc123"}):
        rc = main(["--root", tmp_root, "tunnel", "start", "--provider", "cloudflared", "--port", "8080"])
    assert rc == 0 and "abc123abc123" in capsys.readouterr().out


def test_tunnel_start_failure(tmp_root) -> None:
    with patch("runtime.tunnel_manager.start", return_value={"ok": False, "error": "no binary"}):
        rc = main(["--root", tmp_root, "tunnel", "start"])
    assert rc == 1


def test_tunnel_stop(tmp_root, capsys) -> None:
    with patch("runtime.tunnel_manager.stop", return_value={"ok": True, "status": "stopped"}):
        rc = main(["--root", tmp_root, "tunnel", "stop", "--id", "abc123abc123"])
    assert rc == 0 and "stopped" in capsys.readouterr().out


def test_tunnel_status(tmp_root) -> None:
    with patch("runtime.tunnel_manager.status", return_value={"ok": True, "status": "active"}):
        rc = main(["--root", tmp_root, "tunnel", "status", "--id", "abc123abc123"])
    assert rc == 0


def test_tunnel_list_default(tmp_root, capsys) -> None:
    with patch("runtime.tunnel_manager.list_tunnels", return_value={"ok": True, "count": 0, "tunnels": []}):
        rc = main(["--root", tmp_root, "tunnel"])
    assert rc == 0 and "count" in capsys.readouterr().out
