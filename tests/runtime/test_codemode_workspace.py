"""Tests for codemode hardening: workspace bridge, output caps, tool-call
caps, and strict result enforcement."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.codemode import _child
from runtime.codemode.executor import CodeModeExecutor


def _ex(tmp_path: Path, **kw) -> CodeModeExecutor:
    kw.setdefault("tool_caller", lambda s, t, a: {"ok": True})
    return CodeModeExecutor(tmp_path, **kw)


# ---------------------------------------------------------------------------
# Workspace bridge — end to end through the real subprocess
# ---------------------------------------------------------------------------


def test_workspace_roundtrip(tmp_path: Path) -> None:
    src = (
        "workspace_write('notes/a.txt', 'hello')\n"
        "print(workspace_read('notes/a.txt'))\n"
    )
    r = _ex(tmp_path).execute(src)
    assert r.ok and "hello" in r.output
    assert (tmp_path / "state" / "codemode" / "workspace" / "notes" / "a.txt").read_text() == "hello"


def test_workspace_list_roundtrip(tmp_path: Path) -> None:
    src = (
        "workspace_write('x/1.txt', 'a')\n"
        "workspace_write('x/2.txt', 'b')\n"
        "print(workspace_list())\n"
    )
    r = _ex(tmp_path).execute(src)
    assert r.ok and "x/1.txt" in r.output and "x/2.txt" in r.output


def test_workspace_traversal_rejected(tmp_path: Path) -> None:
    r = _ex(tmp_path).execute("workspace_write('../evil.txt', 'x')")
    assert not r.ok and "escapes" in r.error


def test_workspace_absolute_rejected(tmp_path: Path) -> None:
    r = _ex(tmp_path).execute("workspace_read('/etc/passwd')")
    assert not r.ok and "escapes" in r.error


def test_workspace_empty_path_rejected(tmp_path: Path) -> None:
    r = _ex(tmp_path).execute("workspace_read('')")
    assert not r.ok and "required" in r.error


# ---------------------------------------------------------------------------
# Child-side workspace ops (in-process, injected streams)
# ---------------------------------------------------------------------------


def test_child_workspace_ops_roundtrip() -> None:
    inp = io.StringIO(json.dumps({"ok": True, "result": "data"}) + "\n")
    out = io.StringIO()
    ws_read, _w, _l = _child.make_workspace_ops(inp, out)
    assert ws_read("f.txt") == "data"
    sent = json.loads(out.getvalue().splitlines()[0])
    assert sent["type"] == "workspace" and sent["op"] == "read" and sent["path"] == "f.txt"
    assert "data" not in sent  # read carries no payload


def test_child_workspace_write_sends_data() -> None:
    inp = io.StringIO(json.dumps({"ok": True, "result": 3}) + "\n")
    out = io.StringIO()
    _r, ws_write, _l = _child.make_workspace_ops(inp, out)
    assert ws_write("f.txt", "abc") == 3
    sent = json.loads(out.getvalue().splitlines()[0])
    assert sent["data"] == "abc"


def test_child_workspace_write_non_str_raises() -> None:
    _r, ws_write, _l = _child.make_workspace_ops(io.StringIO(), io.StringIO())
    with pytest.raises(TypeError):
        ws_write("f.txt", 123)  # type: ignore[arg-type]


def test_child_workspace_denied_raises() -> None:
    inp = io.StringIO(json.dumps({"ok": False, "error": "escapes workspace root"}) + "\n")
    out = io.StringIO()
    _r, _w, ws_list = _child.make_workspace_ops(inp, out)
    with pytest.raises(PermissionError):
        ws_list()


# ---------------------------------------------------------------------------
# Parent-side workspace dispatch edge branches
# ---------------------------------------------------------------------------


def test_dispatch_unknown_op(tmp_path: Path) -> None:
    resp = _ex(tmp_path)._dispatch_workspace({"op": "delete", "path": "x"})
    assert not resp["ok"] and "unknown workspace op" in resp["error"]


def test_resolve_drive_letter_rejected(tmp_path: Path) -> None:
    assert _ex(tmp_path)._resolve_ws_path("C:/windows/win.ini") is None


def test_resolve_backslash_normalized(tmp_path: Path) -> None:
    resolved = _ex(tmp_path)._resolve_ws_path("a\\b.txt")
    assert resolved is not None and resolved.name == "b.txt"


def test_resolve_exception_returns_none(tmp_path: Path) -> None:
    with patch.object(Path, "resolve", side_effect=OSError("bad")):
        assert _ex(tmp_path)._resolve_ws_path("a.txt") is None


def test_ws_read_missing(tmp_path: Path) -> None:
    resp = _ex(tmp_path)._dispatch_workspace({"op": "read", "path": "nope.txt"})
    assert not resp["ok"] and "not found" in resp["error"]


def test_ws_read_too_big(tmp_path: Path) -> None:
    ex = _ex(tmp_path)
    root = tmp_path / "state" / "codemode" / "workspace"
    root.mkdir(parents=True)
    big = root / "big.txt"
    big.write_bytes(b"x" * (262144 + 1))
    resp = ex._dispatch_workspace({"op": "read", "path": "big.txt"})
    assert not resp["ok"] and "exceeds" in resp["error"]


def test_ws_read_oserror(tmp_path: Path) -> None:
    ex = _ex(tmp_path)
    root = tmp_path / "state" / "codemode" / "workspace"
    root.mkdir(parents=True)
    (root / "f.txt").write_text("x")
    with patch.object(Path, "read_text", side_effect=OSError("gone")):
        resp = ex._dispatch_workspace({"op": "read", "path": "f.txt"})
    assert not resp["ok"] and "read failed" in resp["error"]


def test_ws_write_too_big(tmp_path: Path) -> None:
    resp = _ex(tmp_path)._dispatch_workspace({"op": "write", "path": "f.txt", "data": "x" * (262144 + 1)})
    assert not resp["ok"] and "exceeds" in resp["error"]


def test_ws_write_oserror(tmp_path: Path) -> None:
    with patch.object(Path, "write_text", side_effect=OSError("ro")):
        resp = _ex(tmp_path)._dispatch_workspace({"op": "write", "path": "f.txt", "data": "x"})
    assert not resp["ok"] and "write failed" in resp["error"]


def test_ws_write_non_str_data_coerced(tmp_path: Path) -> None:
    resp = _ex(tmp_path)._dispatch_workspace({"op": "write", "path": "f.txt", "data": 42})
    assert resp["ok"] and resp["result"] == 0


def test_ws_list_non_dir_empty(tmp_path: Path) -> None:
    resp = _ex(tmp_path)._dispatch_workspace({"op": "list", "path": ""})
    assert resp["ok"] and resp["result"] == []


def test_ws_list_cap(tmp_path: Path) -> None:
    ex = _ex(tmp_path)
    root = tmp_path / "state" / "codemode" / "workspace"
    root.mkdir(parents=True)
    for i in range(4):
        (root / f"f{i}.txt").write_text("x")
    with patch("runtime.codemode.executor._WS_LIST_CAP", 2):
        resp = ex._dispatch_workspace({"op": "list", "path": ""})
    assert resp["ok"] and len(resp["result"]) == 2


def test_ws_list_oserror(tmp_path: Path) -> None:
    ex = _ex(tmp_path)
    root = tmp_path / "state" / "codemode" / "workspace"
    root.mkdir(parents=True)
    with patch.object(Path, "rglob", side_effect=OSError("bad")):
        resp = ex._dispatch_workspace({"op": "list", "path": ""})
    assert not resp["ok"] and "list failed" in resp["error"]


# ---------------------------------------------------------------------------
# Output cap
# ---------------------------------------------------------------------------


def test_output_cap_truncates(tmp_path: Path) -> None:
    r = _ex(tmp_path, max_output_bytes=1024).execute("print('x' * 5000)")
    assert r.ok and r.output_truncated and len(r.output) < 5000
    assert r.to_dict()["output_truncated"] is True


def test_output_exact_fit_then_overflow(tmp_path: Path) -> None:
    # First write exactly fills the cap (1023 chars + newline == 1024); the
    # next write hits the truncate-without-append branch (remaining == 0).
    r = _ex(tmp_path, max_output_bytes=1024).execute(
        "print('x' * 1023)\nprint('OVERFLOW')"
    )
    assert r.ok and r.output_truncated and "OVERFLOW" not in r.output


def test_output_post_truncation_discarded(tmp_path: Path) -> None:
    # Third print happens entirely after truncation -> dropped branch.
    r = _ex(tmp_path, max_output_bytes=1024).execute(
        "print('x' * 2000)\nprint('second')\nprint('third')"
    )
    assert r.ok and r.output_truncated and "second" not in r.output and "third" not in r.output


def test_output_under_cap_not_truncated(tmp_path: Path) -> None:
    r = _ex(tmp_path).execute("print('small')")
    assert r.ok and not r.output_truncated


# ---------------------------------------------------------------------------
# Tool-call cap
# ---------------------------------------------------------------------------


def test_tool_call_cap(tmp_path: Path) -> None:
    ex = _ex(tmp_path, max_tool_calls=2)
    with (
        patch("runtime.enforcement.enforce_tool_call_root", return_value=None),
        patch("runtime.enforcement.enforce_tool_result_root", return_value=(True, "{}")),
    ):
        r = ex.execute(
            "for i in range(5):\n"
            "    try:\n"
            "        call_tool('s', 't', {})\n"
            "    except Exception:\n"
            "        pass\n"
        )
    assert len(r.tool_calls) == 2  # attempts past the cap are not even recorded


def test_tool_caller_crash_reported_not_dead(tmp_path: Path) -> None:
    def crashing(_s: str, _t: str, _a: dict) -> dict:
        raise RuntimeError("dispatcher exploded")

    ex = CodeModeExecutor(tmp_path, tool_caller=crashing)
    with (
        patch("runtime.enforcement.enforce_tool_call_root", return_value=None),
    ):
        r = ex.execute("call_tool('s', 't', {})")
    assert not r.ok and "dispatcher exploded" in r.error
    assert r.tool_calls[0].decision == "error"


# ---------------------------------------------------------------------------
# Strict result enforcement
# ---------------------------------------------------------------------------


def test_strict_results_error_denies(tmp_path: Path) -> None:
    ex = _ex(tmp_path, strict_results=True)
    with (
        patch("runtime.enforcement.enforce_tool_call_root", return_value=None),
        patch("runtime.enforcement.enforce_tool_result_root", side_effect=RuntimeError("boom")),
    ):
        r = ex.execute("call_tool('s', 't', {})")
    assert not r.ok and "strict" in r.error
    assert r.tool_calls[0].decision == "deny"


def test_strict_results_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIZEE_CODEMODE_RESULT_STRICT", "1")
    assert CodeModeExecutor(tmp_path).strict_results is True


def test_lenient_results_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIZEE_CODEMODE_RESULT_STRICT", raising=False)
    assert CodeModeExecutor(tmp_path).strict_results is False


def test_init_clamps(tmp_path: Path) -> None:
    ex = CodeModeExecutor(tmp_path, max_output_bytes=1, max_tool_calls=0)
    assert ex.max_output_bytes == 1024 and ex.max_tool_calls == 1
