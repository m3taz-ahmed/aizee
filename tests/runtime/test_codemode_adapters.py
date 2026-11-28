"""Tests for runtime/codemode/adapters.py — progressive adapter generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.codemode.adapters import (
    _py_type,
    _safe_ident,
    adapter_source,
    generate,
    generate_server_adapters,
    schema_hash,
)


def test_safe_ident_plain() -> None:
    assert _safe_ident("query") == "query"


def test_safe_ident_special_chars() -> None:
    assert _safe_ident("my-arg!") == "my_arg_"


def test_safe_ident_leading_digit() -> None:
    assert _safe_ident("9lives") == "_9lives"


def test_safe_ident_keyword() -> None:
    assert _safe_ident("class") == "class_"


def test_safe_ident_empty() -> None:
    assert _safe_ident("") == "_"
    assert _safe_ident("!!!") == "___"


def test_py_type_mapping() -> None:
    assert _py_type({"type": "string"}) == "str"
    assert _py_type({"type": "integer"}) == "int"
    assert _py_type({"type": "number"}) == "float"
    assert _py_type({"type": "boolean"}) == "bool"
    assert _py_type({"type": "object"}) == "dict"
    assert _py_type({"type": "array"}) == "list"


def test_py_type_unknown_and_non_dict() -> None:
    assert _py_type({"type": "weird"}) == "Any"
    assert _py_type("not-a-dict") == "Any"  # type: ignore[arg-type]


def test_schema_hash_stable() -> None:
    assert schema_hash({"a": 1}) == schema_hash({"a": 1})
    assert len(schema_hash({})) == 16


def test_adapter_source_required_and_optional() -> None:
    schema = {
        "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["q"],
    }
    src = adapter_source("aizee", "search_memory", "Search memory.", schema)
    assert "def search_memory(q: str, limit: int | None = None) -> dict:" in src
    assert 'call_tool("aizee", "search_memory"' in src
    assert "schema_sha256" in src
    compile(src, "<adapter>", "exec")  # must be valid Python


def test_adapter_source_no_params() -> None:
    src = adapter_source("aizee", "list_all", "", {})
    assert "def list_all() -> dict:" in src
    assert "Adapter for aizee/list_all." in src
    compile(src, "<adapter>", "exec")


def test_adapter_source_docstring_escaped() -> None:
    src = adapter_source("s", "t", 'has """quotes""" inside', {"properties": {}})
    compile(src, "<adapter>", "exec")


def test_adapter_source_param_cap() -> None:
    props = {f"p{i}": {"type": "string"} for i in range(50)}
    src = adapter_source("s", "t", "", {"properties": props})
    assert "p39" in src and "p40" not in src


def test_generate_server_adapters_writes(tmp_path: Path) -> None:
    tools = [{"tool": "search_memory", "description": "s", "schema": {"properties": {"q": {"type": "string"}}, "required": ["q"]}}]
    res = generate_server_adapters(tmp_path, "aizee", tools)
    assert res["ok"] and res["written"] == 1
    out = tmp_path / "state" / "codemode" / "servers" / "aizee"
    assert (out / "search_memory.py").exists()
    index = json.loads((out / "index.json").read_text())
    assert index["count"] == 1 and index["tools"][0]["schema_sha256"]


def test_generate_server_adapters_unsafe_server(tmp_path: Path) -> None:
    res = generate_server_adapters(tmp_path, "../evil", [])
    assert not res["ok"] and "unsafe server" in res["error"]


def test_generate_server_adapters_unsafe_tool_skipped(tmp_path: Path) -> None:
    res = generate_server_adapters(tmp_path, "srv", [{"tool": "../bad", "schema": {}}])
    assert not res["ok"] and res["written"] == 0
    assert any("unsafe tool" in e for e in res["errors"])


def test_generate_server_adapters_write_error(tmp_path: Path) -> None:
    with patch.object(Path, "write_text", side_effect=OSError("ro")):
        res = generate_server_adapters(tmp_path, "srv", [{"tool": "good_tool", "schema": {}}])
    assert not res["ok"] and any("ro" in e for e in res["errors"])


def test_generate_aizee_inprocess(tmp_path: Path) -> None:
    fake = [{"tool": "x_tool", "description": "d", "schema": {}}]
    with patch("runtime.codemode.adapters.list_aizee_tools", return_value=fake):
        res = generate(tmp_path, "aizee")
    assert res["written"] == 1


def test_generate_external_success(tmp_path: Path) -> None:
    listing = {"tools": [{"name": "query_graph", "description": "q", "inputSchema": {"properties": {}}}, "not-a-dict"]}
    with patch("runtime.mcp_client.McpClient") as mc:
        mc.return_value.list_tools.return_value = listing
        res = generate(tmp_path, "graphify")
    assert res["written"] == 1 and res["server"] == "graphify"


def test_generate_external_client_error(tmp_path: Path) -> None:
    with patch("runtime.mcp_client.McpClient", side_effect=RuntimeError("down")):
        res = generate(tmp_path, "graphify")
    assert not res["ok"] and "tools/list failed" in res["error"]


def test_generate_external_bad_listing(tmp_path: Path) -> None:
    with patch("runtime.mcp_client.McpClient") as mc:
        mc.return_value.list_tools.return_value = {"nope": True}
        res = generate(tmp_path, "graphify")
    assert not res["ok"] and "no tool listing" in res["error"]


def test_list_aizee_tools_shape() -> None:
    fake_tool = MagicMock()
    fake_tool.description = "desc"
    fake_tool.parameters = {"properties": {}}
    fake_mcp = MagicMock()
    fake_mcp._tool_manager._tools = {"zeta": fake_tool}
    with patch("aizee_mcp.aizee_server.mcp", fake_mcp):
        from runtime.codemode.adapters import list_aizee_tools

        tools = list_aizee_tools()
    assert tools == [{"tool": "zeta", "description": "desc", "schema": {"properties": {}}}]
