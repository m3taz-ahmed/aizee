#!/usr/bin/env python3
"""Code Mode MCP tools: ``execute_code`` + ``search_tools``.

This is the progressive-disclosure surface described in Anthropic's
code-execution-with-MCP pattern: instead of loading every tool schema into
context, the model searches for the tools it needs (``search_tools``) and
then composes them inside a sandboxed Python snippet (``execute_code``),
returning only the final distilled output.

Security posture:
  * The snippet runs in the subprocess-isolated ``CodeModeExecutor`` with
    strict result enforcement (fail-closed) — never the lenient CLI default.
  * ``call_tool`` inside the snippet is brokered here: aiZee's own tools are
    dispatched in-process through the same RBAC-wrapped callables the MCP
    server exposes; external servers go through the governed MCP client.
  * Recursion is blocked: a snippet cannot call ``execute_code`` again,
    directly or transitively, because the dispatcher refuses the tool name.
  * Every execution and every broached tool call is audit-logged with a
    correlation id; the snippet source is logged as a sha256 hash only.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from aizee_mcp._compat import FastMCP

from .common import root, truncate

_MAX_CODE_BYTES = 50_000
_MAX_TIMEOUT_S = 60.0
_DEFAULT_TIMEOUT_S = 15.0
_RECURSION_BLOCKLIST = {"execute_code", "run_mcp_plan"}
_DETAIL_LEVELS = ("name", "description", "schema")


def _audit_event(kind: str, payload: dict[str, Any]) -> None:
    """Best-effort audit write — audit failure must never break execution."""
    try:
        from runtime.audit import AuditLogger

        AuditLogger(root()).log(kind, payload)
    except Exception:
        pass


def _inprocess_caller(mcp: FastMCP, correlation: str, audit: list[dict[str, Any]]) -> Any:
    """Build a tool caller that dispatches aiZee tools in-process.

    Returns None for the recursion-blocked tools so the executor records a
    denial instead of spawning a nested execution loop.
    """

    def caller(server: str, tool: str, args: dict[str, Any]) -> Any:
        entry: dict[str, Any] = {"server": server, "tool": tool, "correlation": correlation}
        if tool in _RECURSION_BLOCKLIST:
            entry["decision"] = "deny-recursion"
            audit.append(entry)
            raise PermissionError(f"tool {tool!r} is not callable from inside execute_code")
        if server not in ("aizee", "aizee_mcp", ""):
            # External servers: governed MCP client path (pooled, env-allowlist).
            from runtime.mcp_client import McpClient

            result = McpClient(server, root()).call_tool(tool, args)
            entry["decision"] = "allow-external"
            audit.append(entry)
            return result
        tool_obj = mcp._tool_manager.get_tool(tool)
        if tool_obj is None:
            entry["decision"] = "deny-unknown"
            audit.append(entry)
            raise ValueError(f"unknown aizee tool {tool!r}")
        result = tool_obj.fn(**args)
        entry["decision"] = "allow-inprocess"
        audit.append(entry)
        return result

    return caller


def _search_own_tools(mcp: FastMCP, query: str, detail: str, limit: int) -> list[dict[str, Any]]:
    q = query.lower()
    out: list[dict[str, Any]] = []
    tools = getattr(mcp._tool_manager, "_tools", {})
    for name in sorted(tools):
        tool = tools[name]
        desc = (getattr(tool, "description", "") or "").strip()
        if q and q not in name.lower() and q not in desc.lower():
            continue
        hit: dict[str, Any] = {"server": "aizee", "tool": name}
        if detail in ("description", "schema"):
            hit["description"] = truncate(desc.splitlines()[0] if desc else "", 200)
        if detail == "schema":
            schema = getattr(tool, "parameters", None) or {}
            hit["schema"] = schema
            hit["schema_sha256"] = hashlib.sha256(
                json.dumps(schema, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
        out.append(hit)
        if len(out) >= limit:
            break
    return out


def register_codemode_tools(mcp: FastMCP) -> None:
    """Register the Code Mode execution and discovery tools."""

    @mcp.tool()
    def execute_code(code: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> str:
        """Run a Python snippet in the governed code-mode sandbox.

        Inside the snippet, ``call_tool(server, tool, args)`` invokes MCP
        tools through the enforcement pipeline, ``print(...)`` is the only
        output channel, and ``workspace_read/write/list`` persist files under
        the governed workspace. No filesystem, network, or import access
        beyond the AST-scanned allowlist. Returns JSON with ok/output/error/
        tool_calls/timed_out/output_truncated.
        """
        if not code or not code.strip():
            return json.dumps({"ok": False, "error": "code must be non-empty"})
        if len(code) > _MAX_CODE_BYTES:
            return json.dumps({"ok": False, "error": f"code exceeds {_MAX_CODE_BYTES} bytes"})
        try:
            timeout = min(max(float(timeout_s), 1.0), _MAX_TIMEOUT_S)
        except (TypeError, ValueError):
            timeout = _DEFAULT_TIMEOUT_S

        correlation = uuid.uuid4().hex[:12]
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        audit: list[dict[str, Any]] = []

        from runtime.codemode import CodeModeExecutor

        executor = CodeModeExecutor(
            root(),
            tool_caller=_inprocess_caller(mcp, correlation, audit),
            timeout_s=timeout,
            strict_results=True,
        )
        result = executor.execute(code)
        payload = result.to_dict()
        payload["correlation"] = correlation
        payload["code_sha256"] = code_hash
        _audit_event("codemode.execute", {
            "correlation": correlation,
            "code_sha256": code_hash,
            "ok": result.ok,
            "timed_out": result.timed_out,
            "output_truncated": result.output_truncated,
            "tool_calls": [
                {"server": c.server, "tool": c.tool, "decision": c.decision, "ok": c.ok, "detail": c.detail}
                for c in result.tool_calls
            ],
            "dispatch": audit,
        })
        if len(payload["output"]) > 6000:
            payload["output"] = truncate(payload["output"], 6000)
            payload["output_truncated"] = True
        return json.dumps(payload, indent=2, default=str)

    @mcp.tool()
    def search_tools(query: str = "", detail: str = "description", limit: int = 20) -> str:
        """Search aiZee MCP tools progressively — the discovery half of code mode.

        ``detail`` controls payload size: ``name`` (cheapest), ``description``
        (default), or ``schema`` (full input schema + integrity hash — use
        only for the tools you are about to call).
        """
        if detail not in _DETAIL_LEVELS:
            return json.dumps({"ok": False, "error": f"detail must be one of {_DETAIL_LEVELS}"})
        if len(query) > 500:
            return json.dumps({"ok": False, "error": "query too long"})
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20
        results = _search_own_tools(mcp, query, detail, limit)
        return json.dumps({"ok": True, "count": len(results), "tools": results}, indent=2, default=str)
