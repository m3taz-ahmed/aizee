"""Agent-harness hooks (agentmemory adoption).

Hooks let aiZee capture and inject context *inside* the agent loop of
other harnesses — the hook config stays tiny and calls back into
``aizee hooks fire <event>`` so behavior lives here, versioned.

Event map (agentmemory's taxonomy, aiZee's handlers):

- ``session_start``  — context-injecting: print an L0 briefing to stdout.
- ``post_tool_failure`` — telemetry: append the failure to memory (bank=global).
- ``pre_compact`` — checkpoint: store a session-checkpoint memory.
- ``session_end`` — telemetry: audit-log the close + store a brief.

Two hook styles (kept from agentmemory): context-injecting handlers run
synchronously and print to stdout; telemetry handlers are fire-and-forget
— they must never block or break the agent loop, so they swallow errors
and always exit 0.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENTS = ("session_start", "post_tool_failure", "pre_compact", "session_end")
_TELEMETRY_EVENTS = frozenset({"post_tool_failure", "pre_compact", "session_end"})
_HOOK_FIRE = "aizee hooks fire {event}"

# Harness adapters: how each host registers our events.
_CLAUDE_EVENTS = {
    "session_start": "SessionStart",
    "post_tool_failure": "PostToolUseFailure",
    "pre_compact": "PreCompact",
    "session_end": "SessionEnd",
}
SUPPORTED_HARNESSES = ("claude-code", "generic")


def _memory_note(root: Path, kind: str, text: str) -> bool:
    """Best-effort memory append. Never raises — telemetry must not break."""
    try:
        from memory.store import MemoryStore
        from runtime.secret_scrub import scrub_text

        store = MemoryStore(root)
        scrubbed = scrub_text(text)
        store.add(
            kind=kind,
            content=scrubbed.text,
            source="hooks",
            bank="global",
        )
        return True
    except Exception:  # fire-and-forget: never propagate into the agent loop
        return False


def _briefing(root: Path) -> str:
    """L0 session briefing: counts + active context head."""
    lines = ["[aizee] session context:"]
    try:
        from runtime.service_catalog import build_catalog_from_directory

        catalog = build_catalog_from_directory(root / "skills")
        counts = catalog.stats()
        lines.append(
            f"  catalog: {counts.get('total', 0)} services, "
            f"{counts.get('enabled', 0)} enabled"
        )
    except Exception:
        lines.append("  catalog: unavailable")
    active = root / "ACTIVE_CONTEXT.md"
    if active.exists():
        head = "\n".join(active.read_text(encoding="utf-8").splitlines()[:15])
        lines.append(f"  ACTIVE_CONTEXT:\n{head}")
    return "\n".join(lines)


def fire(event: str, root: Path, stdin_text: str = "") -> int:
    """Run one hook event. Returns a process exit code.

    Telemetry events are fire-and-forget (always 0); context-injecting
    events print their payload to stdout.
    """
    if event not in EVENTS:
        print(f"unknown hook event: {event}", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc).isoformat()
    if event == "session_start":
        print(_briefing(root))
        return 0
    if event == "post_tool_failure":
        detail = stdin_text[:2000] or "(no payload)"
        _memory_note(root, "episodic", f"[hook:tool-failure] {now}\n{detail}")
        return 0
    if event == "pre_compact":
        _memory_note(root, "episodic", f"[hook:pre-compact] {now} checkpoint before context compaction")
        return 0
    _memory_note(root, "episodic", f"[hook:session-end] {now}")
    return 0


def _claude_settings(hooks_root: Path, root: Path) -> Path:
    """Merge aiZee hooks into project .claude/settings.json."""
    settings_path = root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    hooks = data.setdefault("hooks", {})
    for event, claude_event in _CLAUDE_EVENTS.items():
        entry = {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": _HOOK_FIRE.format(event=event),
                    "timeout": 5 if event in _TELEMETRY_EVENTS else 10,
                }
            ],
        }
        bucket = hooks.setdefault(claude_event, [])
        if not any(_is_aizee_hook(e) for e in bucket):
            bucket.append(entry)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return settings_path


def _is_aizee_hook(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return any(
        isinstance(h, dict) and "aizee hooks fire" in str(h.get("command", ""))
        for h in entry.get("hooks", [])
    )


def _generic_scripts(hooks_root: Path, root: Path) -> Path:
    """Portable POSIX hook scripts any harness can call."""
    hooks_root.mkdir(parents=True, exist_ok=True)
    for event in EVENTS:
        script = hooks_root / f"{event}.sh"
        script.write_text(
            "#!/usr/bin/env sh\n"
            f"# aiZee {event} hook — generated by `aizee hooks install`\n"
            f"aizee hooks fire {event} || true\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
    return hooks_root


def install(root: Path, harness: str = "claude-code") -> dict[str, Any]:
    """Register aiZee hooks with *harness* under *root*."""
    if harness not in SUPPORTED_HARNESSES:
        return {"ok": False, "error": f"unsupported harness: {harness}"}
    hooks_root = root / ".aizee" / "hooks"
    written: list[str] = [str(_generic_scripts(hooks_root, root))]
    if harness == "claude-code":
        written.append(str(_claude_settings(hooks_root, root)))
    return {"ok": True, "harness": harness, "written": written}


def status(root: Path) -> dict[str, Any]:
    """Which harnesses currently have aiZee hooks wired."""
    claude = root / ".claude" / "settings.json"
    generic = root / ".aizee" / "hooks"
    wired: list[str] = []
    if claude.exists():
        try:
            data = json.loads(claude.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        flat = json.dumps(data.get("hooks", {}))
        if "aizee hooks fire" in flat:
            wired.append("claude-code")
    if generic.is_dir() and any(generic.glob("*.sh")):
        wired.append("generic")
    return {"ok": True, "wired": wired, "supported": list(SUPPORTED_HARNESSES)}
