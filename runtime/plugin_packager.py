#!/usr/bin/env python3
"""Plugin packager - emit a portable multi-harness plugin bundle.

Adapted from google/elephant-goldfish-model's distribution layout
(Apache-2.0): one canonical ``plugin.json`` (Agent Plugins 1.0.0 format)
plus thin per-harness manifests pointing at the shared content - no
harness gets a fork of the skill text.

Bundle layout produced by :func:`pack_plugin`::

    plugin.json                     canonical manifest
    .claude-plugin/plugin.json      Claude Code manifest
    .claude-plugin/marketplace.json Claude marketplace catalog entry
    .codex-plugin/plugin.json       Codex manifest
    .agents/plugins/marketplace.json Codex workspace-import catalog
    .cursor-plugin/plugin.json      Cursor manifest
    skills/                         copied skills dir
    resources/                      copied resources dir (personas/rubrics)
    agents/                         persona files for subagent-registering hosts
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CANONICAL_MANIFEST = "plugin.json"


@dataclass
class PackResult:
    """Outcome of a bundle pack."""

    dest: str
    files: list[str] = field(default_factory=list)
    ok: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dest": self.dest, "ok": self.ok,
            "files": len(self.files), "error": self.error or None,
        }


def _canonical_manifest(root: Path) -> dict[str, Any]:
    src = root / _CANONICAL_MANIFEST
    if src.exists():
        manifest: dict[str, Any] = json.loads(src.read_text(encoding="utf-8"))
        return manifest
    return {
        "name": "aizee",
        "description": "Sovereign AI engineering control plane.",
        "license": "MIT",
    }


def _harness_manifests(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per-harness manifests derived from the canonical one (EGM pattern)."""
    name = manifest.get("name", "aizee")
    base = {k: v for k, v in manifest.items() if k not in {"extensions", "compatibility"}}
    claude = {**base, "agents": "./agents/"}
    marketplace = {
        "name": name,
        "plugins": [{
            "name": name,
            "description": manifest.get("description", ""),
            "source": {"source": "local", "path": "."},
        }],
    }
    codex_catalog = {
        "plugins": [{
            "name": name,
            "description": manifest.get("description", ""),
            "skills": "skills",
        }],
    }
    return {
        ".claude-plugin/plugin.json": claude,
        ".claude-plugin/marketplace.json": marketplace,
        ".codex-plugin/plugin.json": base,
        ".agents/plugins/marketplace.json": codex_catalog,
        ".cursor-plugin/plugin.json": base,
    }


def _copy_tree(src: Path, dest: Path, out: list[str], prefix: str) -> None:
    if not src.is_dir():
        return
    for item in sorted(src.rglob("*")):
        if item.is_dir() or "__pycache__" in item.parts:
            continue
        rel = item.relative_to(src)
        target = dest / prefix / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        out.append(str(Path(prefix) / rel))


def _dest_is_bundle_shaped(dest: Path) -> bool:
    """Whether *dest* looks like a previously emitted plugin bundle.

    Fail-closed guard: ``pack_plugin`` clears its destination before
    writing, so it must never receive an arbitrary non-empty directory.
    """
    if not dest.is_dir():
        return False
    return (dest / _CANONICAL_MANIFEST).is_file() or (dest / ".claude-plugin").is_dir()


def pack_plugin(root: Path, dest: Path, *, max_files: int = 2000) -> PackResult:
    """Write a portable plugin bundle for aiZee into *dest*.

    Copies ``skills/`` and ``resources/`` verbatim, promotes
    ``resources/goldfish_personas`` to the bundle's ``agents/`` dir (the
    location subagent-capable harnesses scan), and emits canonical +
    per-harness manifests. *dest* must be absent, empty, or an existing
    bundle (see ``_dest_is_bundle_shaped``); other non-empty dirs fail.
    """
    result = PackResult(dest=str(dest))
    try:
        manifest = _canonical_manifest(root)
        if dest.exists():
            if not dest.is_dir():
                raise ValueError(f"pack destination is not a directory: {dest}")
            if any(dest.iterdir()) and not _dest_is_bundle_shaped(dest):
                raise ValueError(
                    f"pack destination is a non-empty non-bundle dir: {dest}"
                )
            for item in dest.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        dest.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for rel, doc in _harness_manifests(manifest).items():
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            written.append(rel)
        _copy_tree(root / "skills", dest, written, "skills")
        _copy_tree(root / "resources", dest, written, "resources")
        _copy_tree(root / "resources" / "goldfish_personas", dest, written, "agents")
        if len(written) > max_files:
            raise ValueError(f"bundle too large: {len(written)} files")
        (dest / _CANONICAL_MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        written.append(_CANONICAL_MANIFEST)
        result.files = written
        result.ok = True
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.error = str(exc)
    return result
