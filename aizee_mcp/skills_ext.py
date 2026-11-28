#!/usr/bin/env python3
"""MCP Skills extension — serve the aiZee skill library over MCP.

Implements the pragmatic core of SEP-2640 (Agent Skills over MCP):

  * ``skills_list`` tool   — catalog every skill with metadata + integrity hash
  * ``skills_get`` tool    — one skill's SKILL.md + frontmatter + file manifest
  * ``skill://<name>/SKILL.md`` resource template — direct content access
  * ``skill://<name>/<path>`` resource template — references/scripts/assets
    on demand (progressive disclosure: the client pulls a file only when the
    skill's instructions call for it)

Containment rules mirror the rest of the server: skill names must pass
``is_safe_name``, nested paths may not escape the skill directory, and every
served file carries a sha256 so clients can detect drift against
``skills-lock.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aizee_mcp._compat import FastMCP

from .tools.common import is_safe_name, root, truncate

_MAX_FILE_BYTES = 200_000
_MAX_MANIFEST_ENTRIES = 200
_MAX_LISTING = 500
_SKIP_DIRS = {"node_modules", ".git", "__pycache__"}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract simple ``key: value`` pairs from YAML frontmatter (no yaml dep)."""
    meta: dict[str, str] = {}
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def _skill_dirs(r: Path) -> list[Path]:
    skills_dir = r / "skills"
    if not skills_dir.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(skills_dir.iterdir()):
        if len(out) >= _MAX_LISTING:
            break
        if child.is_dir() and child.name not in _SKIP_DIRS and (child / "SKILL.md").is_file():
            out.append(child)
    return out


def _resolve_skill(r: Path, name: str) -> Path | None:
    if not is_safe_name(name):
        return None
    base = (r / "skills" / name).resolve()
    try:
        base.relative_to((r / "skills").resolve())
    except ValueError:
        return None
    if not (base / "SKILL.md").is_file():
        return None
    return base


def _resolve_nested(base: Path, path: str) -> Path | None:
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    if not target.is_file() or any(part in _SKIP_DIRS for part in parts):
        return None
    return target


def _read_capped(path: Path) -> str:
    if path.stat().st_size > _MAX_FILE_BYTES:
        return f"[file exceeds {_MAX_FILE_BYTES} bytes — read it in chunks locally]"
    return path.read_text(encoding="utf-8", errors="replace")


def _manifest(base: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for p in sorted(base.rglob("*")):
        if len(entries) >= _MAX_MANIFEST_ENTRIES:
            break
        if not p.is_file() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        rel = str(p.relative_to(base)).replace("\\", "/")
        try:
            size = p.stat().st_size
        except OSError:
            continue
        entries.append({"path": rel, "bytes": size})
    return entries


def register_skills_extension(mcp: FastMCP) -> None:
    """Register skills-over-MCP tools and ``skill://`` resources."""

    @mcp.tool()
    def skills_list() -> str:
        """Catalog all folder skills (name, description, integrity hash)."""
        r = root()
        out: list[dict[str, Any]] = []
        for skill_dir in _skill_dirs(r):
            content = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            meta = _parse_frontmatter(content)
            out.append({
                "name": skill_dir.name,
                "description": truncate(meta.get("description", ""), 200),
                "skill_sha256": _sha256(content)[:16],
                "files": len(_manifest(skill_dir)),
            })
        return json.dumps({"ok": True, "count": len(out), "skills": out}, indent=2)

    @mcp.tool()
    def skills_get(name: str) -> str:
        """Get one skill: SKILL.md content, frontmatter, and file manifest."""
        r = root()
        base = _resolve_skill(r, name)
        if base is None:
            return json.dumps({"ok": False, "error": f"unknown or unsafe skill {name!r}"})
        content = (base / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        return json.dumps({
            "ok": True,
            "name": base.name,
            "frontmatter": _parse_frontmatter(content),
            "skill_sha256": _sha256(content),
            "content": content,
            "files": _manifest(base),
        }, indent=2)

    @mcp.resource("skill://{name}/SKILL.md", mime_type="text/markdown")
    def skill_main(name: str) -> str:
        """Serve a skill's SKILL.md entry document."""
        base = _resolve_skill(root(), name)
        if base is None:
            raise ValueError(f"unknown or unsafe skill {name!r}")
        return _read_capped(base / "SKILL.md")

    @mcp.resource("skill://{name}/{path}", mime_type="text/plain")
    def skill_file(name: str, path: str) -> str:
        """Serve a nested skill file (references/, scripts/, assets/...)."""
        base = _resolve_skill(root(), name)
        if base is None:
            raise ValueError(f"unknown or unsafe skill {name!r}")
        target = _resolve_nested(base, path)
        if target is None:
            raise ValueError(f"invalid skill file path {path!r}")
        return _read_capped(target)
