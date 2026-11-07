"""MCP tool-surface freeze + drift detection (mcp-to-ai-sdk adoption).

Snapshot-locking an MCP server's tool definitions prevents three silent
failures the upstream server can introduce:

- new tools appearing that the agent was never expected to call,
- existing tool schemas changing (prompt-injection / arg drift),
- tools disappearing that policies or prompts still reference.

``freeze`` writes ``aizee_mcp/tool-lock.json``; ``check`` diffs the live
surface against it and returns a verdict — the mcp_firewall equivalent of
"no surprise tools".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_VERSION = 1
DEFAULT_LOCK = "aizee_mcp/tool-lock.json"


def tool_fingerprint(tool: dict[str, Any]) -> str:
    """Stable hash of a tool's name + input schema + annotations."""
    payload = {
        "name": tool.get("name", ""),
        "schema": tool.get("inputSchema", tool.get("input_schema", {})),
        "description": tool.get("description", ""),
        "annotations": tool.get("annotations", {}),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def snapshot(tools: list[dict[str, Any]]) -> dict[str, str]:
    """tool name -> fingerprint map."""
    return {str(t.get("name", "")): tool_fingerprint(t) for t in tools if t.get("name")}


def write_lock(path: Path, server: str, tools: list[dict[str, Any]]) -> Path:
    """Persist the current tool surface for ``server`` into ``path``."""
    data: dict[str, Any] = {"version": LOCK_VERSION, "servers": {}}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("version") == LOCK_VERSION:
                data = existing
        except (OSError, json.JSONDecodeError):
            pass
    data.setdefault("servers", {})[server] = {
        "frozen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools": snapshot(tools),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_lock(path: Path, server: str) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entry = data.get("servers", {}).get(server, {})
    tools = entry.get("tools", {})
    return {str(k): str(v) for k, v in tools.items()} if isinstance(tools, dict) else {}


@dataclass
class FreezeReport:
    ok: bool
    server: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    frozen_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "server": self.server,
            "frozen_count": self.frozen_count,
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
        }


def check_surface(
    server: str,
    live_tools: list[dict[str, Any]],
    path: Path,
) -> FreezeReport:
    """Diff a live tool surface against the frozen lock."""
    frozen = read_lock(path, server)
    live = snapshot(live_tools)
    report = FreezeReport(ok=True, server=server, frozen_count=len(frozen))
    for name in sorted(set(live) - set(frozen)):
        report.added.append(name)
    for name in sorted(set(frozen) - set(live)):
        report.removed.append(name)
    for name in sorted(set(frozen) & set(live)):
        if frozen[name] != live[name]:
            report.changed.append(name)
    report.ok = not (report.added or report.removed or report.changed)
    return report
