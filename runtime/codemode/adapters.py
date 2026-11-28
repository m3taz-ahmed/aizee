#!/usr/bin/env python3
"""Progressive tool adapters for code mode.

Generates a file tree of typed Python wrappers — one per MCP tool — under
``state/codemode/servers/<server>/<tool>.py``. The model reads only the
adapters it needs (progressive disclosure, per Anthropic's code-execution
pattern) instead of loading every tool schema into context up front.

Each wrapper body is a thin ``call_tool(server, tool, args)`` forwarder —
it is only meaningful *inside* the code-mode sandbox, where ``call_tool``
exists. The files are documentation-typed shims, not importable runtime
code, so they carry no imports and no side effects.

Every generated file embeds the sha256 of the source tool's input schema:
a drifted schema produces a drifted hash, which the manifest lock / freeze
tooling can detect.
"""

from __future__ import annotations

import hashlib
import json
import keyword
import re
from pathlib import Path
from typing import Any

_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "array": "list",
}

_IDENT_RE = re.compile(r"[^0-9a-zA-Z_]")
_MAX_PARAMS = 40


def _safe_ident(name: str) -> str:
    """Sanitize a schema property/tool name into a valid Python identifier."""
    ident = _IDENT_RE.sub("_", name) or "_"
    if ident[0].isdigit():
        ident = "_" + ident
    if keyword.iskeyword(ident):
        ident += "_"
    return ident


def _py_type(prop: dict[str, Any]) -> str:
    if not isinstance(prop, dict):
        return "Any"
    return _TYPE_MAP.get(str(prop.get("type", "")), "Any")


def schema_hash(schema: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True, default=str).encode()).hexdigest()[:16]


def adapter_source(server: str, tool: str, description: str, schema: dict[str, Any]) -> str:
    """Render one typed adapter module for a single MCP tool."""
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    params: list[str] = []
    optional: list[str] = []
    for raw_name in list(props)[:_MAX_PARAMS]:
        ident = _safe_ident(str(raw_name))
        anno = _py_type(props[raw_name])
        if raw_name in required:
            params.append(f"{ident}: {anno}")
        else:
            optional.append(f"{ident}: {anno} | None = None")
    sig = ", ".join(params + optional)
    fn_name = _safe_ident(tool)
    doc = (description or "").replace('"""', "'''").strip().splitlines()
    doc_first = doc[0][:200] if doc else f"Adapter for {server}/{tool}."
    lines = [
        '"""Auto-generated code-mode adapter — do not edit.',
        "",
        f"server: {server}",
        f"tool: {tool}",
        f"schema_sha256: {schema_hash(schema)}",
        '"""',
        "",
        "",
        f"def {fn_name}({sig}) -> dict:",
        f'    """{doc_first}"""',
        f'    return call_tool("{server}", "{tool}", {{k: v for k, v in locals().items() if v is not None}})',
        "",
    ]
    return "\n".join(lines)


def generate_server_adapters(
    root: Path,
    server: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write adapter files for one server. Returns the written manifest."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", server):
        return {"ok": False, "error": f"unsafe server name {server!r}"}
    out_dir = root / "state" / "codemode" / "servers" / server
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    errors: list[str] = []
    for entry in tools:
        name = str(entry.get("tool") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
            errors.append(f"skipped unsafe tool name {name!r}")
            continue
        schema = entry.get("schema") or {}
        source = adapter_source(server, name, str(entry.get("description") or ""), schema)
        path = out_dir / f"{_safe_ident(name)}.py"
        try:
            path.write_text(source, encoding="utf-8", newline="\n")
        except OSError as exc:
            errors.append(f"{name}: {exc}")
            continue
        written.append({"tool": name, "file": path.name, "schema_sha256": schema_hash(schema)})
    index = {"server": server, "count": len(written), "tools": written, "errors": errors}
    try:
        (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    except OSError as exc:
        errors.append(f"index.json: {exc}")
    return {"ok": not errors, "server": server, "written": len(written), "errors": errors, "dir": str(out_dir)}


def list_aizee_tools() -> list[dict[str, Any]]:
    """Snapshot aiZee's own MCP surface as adapter inputs."""
    from aizee_mcp.aizee_server import mcp

    tools: list[dict[str, Any]] = []
    for name, tool in sorted(getattr(mcp._tool_manager, "_tools", {}).items()):
        tools.append({
            "tool": name,
            "description": (getattr(tool, "description", "") or "").strip(),
            "schema": getattr(tool, "parameters", None) or {},
        })
    return tools


def generate(root: Path, server: str = "aizee") -> dict[str, Any]:
    """Generate adapters for one server.

    ``aizee`` is introspected in-process; anything else is queried live
    through the governed MCP client (tools/list).
    """
    if server in ("aizee", "aizee_mcp", ""):
        return generate_server_adapters(root, "aizee", list_aizee_tools())
    try:
        from runtime.mcp_client import McpClient

        listing = McpClient(server, root).list_tools()
    except Exception as exc:
        return {"ok": False, "error": f"tools/list failed for {server}: {exc}"}
    raw_tools = listing.get("tools") if isinstance(listing, dict) else None
    if not isinstance(raw_tools, list):
        return {"ok": False, "error": f"no tool listing for {server}: {listing!r}"[:200]}
    tools = [
        {"tool": t.get("name", ""), "description": t.get("description", ""), "schema": t.get("inputSchema") or {}}
        for t in raw_tools
        if isinstance(t, dict)
    ]
    return generate_server_adapters(root, server, tools)
