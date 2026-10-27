"""Inventory facts rendered for prompt injection.

Adopted from DeepTutor's ``manifest`` pattern: retrieval answers "what does
the material say" but cannot answer "how many skills exist", "which memory
banks are populated", or "list the workflows". Those are questions about the
*inventory*, and no amount of passage similarity produces them.

This module reads the inventory as plain facts off disk (+ a bounded SQLite
count for memory), so the two consumers cannot disagree:

* ``render_inventory_note`` embeds counts in agent context, making inventory
  questions answerable with no tool round-trip — the failure mode where a
  weaker model simply never calls the tool;
* ``render_inventory_report`` enumerates on demand for tools that want the
  full breakdown.

Deliberately NOT reported: per-file index freshness — confidently wrong
counts are worse than no counts.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Inventory:
    """Plain-fact counts of what the OS install contains."""

    skills: int = 0
    skills_always: int = 0
    workflows: int = 0
    tech_stack_refs: int = 0
    runtime_modules: int = 0
    memory_banks: int = 0
    memory_entries: int = 0
    plugins: int = 0
    plugins_enabled: int = 0
    bank_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """JSON-safe shape for tool envelopes."""
        return {
            "skills": self.skills,
            "skills_always": self.skills_always,
            "workflows": self.workflows,
            "tech_stack_refs": self.tech_stack_refs,
            "runtime_modules": self.runtime_modules,
            "memory_banks": self.memory_banks,
            "memory_entries": self.memory_entries,
            "plugins": self.plugins,
            "plugins_enabled": self.plugins_enabled,
            "bank_names": list(self.bank_names),
        }


def _count_files(directory: Path, pattern: str) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.glob(pattern) if p.is_file())


def _skill_counts(root: Path) -> tuple[int, int]:
    """(total, always-on) skill counts; flat ``*.md`` + ``*/SKILL.md`` dirs."""
    skills_dir = root / "skills"
    total = always = 0
    for md in skills_dir.glob("*.md") if skills_dir.is_dir() else ():
        if md.name.lower() in ("readme.md", "license.md"):
            continue
        total += 1
        if "always: true" in md.read_text(encoding="utf-8", errors="replace")[:2000]:
            always += 1
    for skill_md in skills_dir.glob("*/SKILL.md") if skills_dir.is_dir() else ():
        total += 1
        if "always: true" in skill_md.read_text(encoding="utf-8", errors="replace")[:2000]:
            always += 1
    return total, always


def _memory_counts(root: Path) -> tuple[int, int, list[str]]:
    """(banks, live entries, bank names) from the SQLite store."""
    db = root / "memory" / "store.db"
    if not db.is_file():
        return 0, 0, []
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "SELECT bank, COUNT(*) FROM memories WHERE deleted_at IS NULL GROUP BY bank"
            ).fetchall()
    except (OSError, sqlite3.Error):
        return 0, 0, []
    banks = sorted(str(r[0]) for r in rows)
    return len(banks), sum(int(r[1]) for r in rows), banks


def _plugin_counts(root: Path) -> tuple[int, int]:
    """(declared, enabled) plugin counts from plugins.yaml (regex-free parse)."""
    cfg = root / "plugins.yaml"
    if not cfg.is_file():
        return 0, 0
    try:
        import yaml
    except ImportError:
        return 0, 0
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return 0, 0
    plugins = data.get("plugins", {})
    if not isinstance(plugins, dict):
        return 0, 0
    enabled = sum(1 for v in plugins.values() if isinstance(v, dict) and v.get("enabled"))
    return len(plugins), enabled


def collect_inventory(root: Path) -> Inventory:
    """Walk the install and return plain-fact inventory counts."""
    skills, always = _skill_counts(root)
    banks, entries, bank_names = _memory_counts(root)
    plugins, plugins_enabled = _plugin_counts(root)
    return Inventory(
        skills=skills,
        skills_always=always,
        workflows=_count_files(root / "workflows", "[0-9]*.md"),
        tech_stack_refs=_count_files(root / "tech-stack", "*.md"),
        runtime_modules=_count_files(root / "runtime", "*.py"),
        memory_banks=banks,
        memory_entries=entries,
        plugins=plugins,
        plugins_enabled=plugins_enabled,
        bank_names=bank_names,
    )


def render_inventory_note(inv: Inventory) -> str:
    """Compact facts block (~6 lines) for prompt injection — counts only."""
    return (
        "[inventory]\n"
        f"skills: {inv.skills} ({inv.skills_always} always-on) | "
        f"workflows: {inv.workflows} | tech-stack: {inv.tech_stack_refs} | "
        f"runtime modules: {inv.runtime_modules}\n"
        f"memory: {inv.memory_entries} entries across {inv.memory_banks} bank(s)\n"
        f"plugins: {inv.plugins_enabled}/{inv.plugins} enabled\n"
        "Inventory questions (counts, lists, 'what exists') are answerable from "
        "these facts or the inventory_report tool — do not guess from retrieved passages."
    )


def render_inventory_report(inv: Inventory) -> str:
    """Full multi-line inventory for tool output — includes bank names."""
    lines = [
        "Inventory report",
        "----------------",
        f"skills           : {inv.skills} total, {inv.skills_always} always-on",
        f"workflows        : {inv.workflows} numbered protocols",
        f"tech-stack refs  : {inv.tech_stack_refs} version-locked files",
        f"runtime modules  : {inv.runtime_modules} governance modules",
        f"memory           : {inv.memory_entries} live entries, {inv.memory_banks} bank(s)",
        f"plugins          : {inv.plugins_enabled} enabled of {inv.plugins} declared",
    ]
    if inv.bank_names:
        lines.append(f"banks            : {', '.join(inv.bank_names)}")
    return "\n".join(lines)
