"""Tests for aizee_mcp/tools/codemode_tools.py — code mode MCP surface."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aizee_mcp._compat import FastMCP

pytestmark = pytest.mark.mcp

_ROOT = tempfile.mkdtemp(prefix="aizee_cm_test_")
os.environ["AIZEE_ROOT"] = _ROOT
ROOT = Path(_ROOT)
for sub in ("state", "brain"):
    (ROOT / sub).mkdir(parents=True, exist_ok=True)

from aizee_mcp.tools.codemode_tools import (  # noqa: E402
    _inprocess_caller,
    register_codemode_tools,
)
from aizee_mcp.tools.common import reset_state  # noqa: E402

_mcp = FastMCP("test-codemode")
register_codemode_tools(_mcp)


def _call(name: str, arguments: dict) -> dict:
    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    tool = _mcp._tool_manager.get_tool(name)
    assert tool is not None
    return json.loads(tool.fn(**arguments))


# ---------------------------------------------------------------------------
# search_tools
# ---------------------------------------------------------------------------


def test_search_tools_description_detail() -> None:
    res = _call("search_tools", {"query": "execute", "detail": "description"})
    assert res["ok"] and res["count"] >= 1
    names = [t["tool"] for t in res["tools"]]
    assert "execute_code" in names
    hit = next(t for t in res["tools"] if t["tool"] == "execute_code")
    assert hit["server"] == "aizee" and "description" in hit and "schema" not in hit


def test_search_tools_name_detail_is_minimal() -> None:
    res = _call("search_tools", {"query": "", "detail": "name"})
    assert res["ok"]
    assert all(set(t.keys()) == {"server", "tool"} for t in res["tools"])


def test_search_tools_schema_detail() -> None:
    res = _call("search_tools", {"query": "search_tools", "detail": "schema"})
    hit = next(t for t in res["tools"] if t["tool"] == "search_tools")
    assert "schema" in hit and len(hit["schema_sha256"]) == 16


def test_search_tools_invalid_detail() -> None:
    res = _call("search_tools", {"detail": "everything"})
    assert not res["ok"] and "detail" in res["error"]


def test_search_tools_query_too_long() -> None:
    res = _call("search_tools", {"query": "x" * 501})
    assert not res["ok"] and "too long" in res["error"]


def test_search_tools_bad_limit_defaults() -> None:
    res = _call("search_tools", {"limit": "abc"})
    assert res["ok"] and res["count"] <= 20


def test_search_tools_no_match() -> None:
    res = _call("search_tools", {"query": "zzz-no-such-tool-zzz"})
    assert res["ok"] and res["count"] == 0


def test_search_tools_empty_description_branch() -> None:
    # Cover the no-description fallback inside _search_own_tools.
    mcp2 = FastMCP("bare")

    @mcp2.tool(description="")
    def empty_desc_tool() -> str:
        return "x"

    register_codemode_tools(mcp2)
    tool = mcp2._tool_manager.get_tool("search_tools")
    res = json.loads(tool.fn(query="empty_desc", detail="description"))
    assert res["ok"]
    hit = next(t for t in res["tools"] if t["tool"] == "empty_desc_tool")
    assert hit["description"] == ""


# ---------------------------------------------------------------------------
# execute_code validation branches (executor mocked — fast)
# ---------------------------------------------------------------------------


def test_execute_empty_code() -> None:
    res = _call("execute_code", {"code": "   "})
    assert not res["ok"] and "non-empty" in res["error"]


def test_execute_code_too_long() -> None:
    res = _call("execute_code", {"code": "x" * 50_001})
    assert not res["ok"] and "exceeds" in res["error"]


def _fake_result(**kw):
    r = MagicMock()
    r.ok = kw.get("ok", True)
    r.timed_out = False
    r.output_truncated = False
    r.tool_calls = []
    r.to_dict.return_value = {
        "ok": r.ok, "output": kw.get("output", "done"), "error": "",
        "timed_out": False, "output_truncated": False, "cleanup_pending": False,
        "tool_calls": [],
    }
    return r


def test_execute_bad_timeout_defaults() -> None:
    with patch("runtime.codemode.CodeModeExecutor") as ex_cls:
        ex_cls.return_value.execute.return_value = _fake_result()
        res = _call("execute_code", {"code": "print(1)", "timeout_s": "bad"})
    assert res["ok"]
    assert ex_cls.call_args.kwargs["timeout_s"] == 15.0


def test_execute_timeout_clamped() -> None:
    with patch("runtime.codemode.CodeModeExecutor") as ex_cls:
        ex_cls.return_value.execute.return_value = _fake_result()
        _call("execute_code", {"code": "print(1)", "timeout_s": 9999})
    assert ex_cls.call_args.kwargs["timeout_s"] == 60.0
    assert ex_cls.call_args.kwargs["strict_results"] is True


def test_execute_payload_fields() -> None:
    with patch("runtime.codemode.CodeModeExecutor") as ex_cls:
        ex_cls.return_value.execute.return_value = _fake_result()
        res = _call("execute_code", {"code": "print('hi')"})
    assert res["ok"] and len(res["correlation"]) == 12 and len(res["code_sha256"]) == 64


def test_execute_output_truncated_at_6000() -> None:
    with patch("runtime.codemode.CodeModeExecutor") as ex_cls:
        ex_cls.return_value.execute.return_value = _fake_result(output="y" * 7000)
        res = _call("execute_code", {"code": "print('x')"})
    assert res["output_truncated"] is True and len(res["output"]) < 7000


def test_execute_audit_failure_tolerated() -> None:
    with (
        patch("runtime.codemode.CodeModeExecutor") as ex_cls,
        patch("runtime.audit.AuditLogger", side_effect=RuntimeError("audit down")),
    ):
        ex_cls.return_value.execute.return_value = _fake_result()
        res = _call("execute_code", {"code": "print(1)"})
    assert res["ok"]


# ---------------------------------------------------------------------------
# execute_code end-to-end through the real sandbox
# ---------------------------------------------------------------------------


def test_execute_end_to_end_print() -> None:
    res = _call("execute_code", {"code": "print('mcp-surface-ok')"})
    assert res["ok"] and "mcp-surface-ok" in res["output"]


def test_execute_end_to_end_recursion_blocked() -> None:
    # Enforcement runs in the parent process, so patching it here lets the
    # call past the firewall — isolating the recursion guard itself.
    with patch("runtime.enforcement.enforce_tool_call_root", return_value=None):
        res = _call("execute_code", {"code": "call_tool('aizee', 'execute_code', {'code': 'print(1)'})"})
    assert not res["ok"] and "not callable" in res["error"]


def test_execute_end_to_end_firewall_blocks_unknown() -> None:
    # Without a matching firewall rule in the test root, even aizee self-calls
    # are denied before dispatch — governance-first, exactly as designed.
    res = _call("execute_code", {"code": "call_tool('aizee', 'search_tools', {})"})
    assert not res["ok"] and "blocked" in res["error"]


# ---------------------------------------------------------------------------
# _inprocess_caller branches (direct — no subprocess)
# ---------------------------------------------------------------------------


def test_caller_recursion_blocklist() -> None:
    audit: list[dict] = []
    caller = _inprocess_caller(_mcp, "corr", audit)
    with pytest.raises(PermissionError):
        caller("aizee", "run_mcp_plan", {})
    assert audit[-1]["decision"] == "deny-recursion"


def test_caller_unknown_tool() -> None:
    audit: list[dict] = []
    caller = _inprocess_caller(_mcp, "corr", audit)
    with pytest.raises(ValueError):
        caller("aizee", "no_such_tool_xyz", {})
    assert audit[-1]["decision"] == "deny-unknown"


def test_caller_inprocess_success() -> None:
    audit: list[dict] = []
    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    caller = _inprocess_caller(_mcp, "corr", audit)
    result = caller("aizee", "search_tools", {"query": "", "detail": "name", "limit": 1})
    assert json.loads(result)["ok"]
    assert audit[-1]["decision"] == "allow-inprocess"


def test_caller_external_delegates() -> None:
    audit: list[dict] = []
    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    caller = _inprocess_caller(_mcp, "corr", audit)
    with patch("runtime.mcp_client.McpClient") as mc:
        mc.return_value.call_tool.return_value = {"content": "ext"}
        result = caller("graphify", "query_graph", {"q": "x"})
    assert result == {"content": "ext"}
    assert audit[-1]["decision"] == "allow-external"
