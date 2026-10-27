"""Skill authoring toolchain (anthropic-cybersecurity-skills adoption).

Three checks that keep a large skill library routable:

- ``lint_description`` — every skill description must carry what-it-does +
  trigger phrases ("Use when ..." equivalents) + keywords, matching the
  agentskills.io authoring contract.
- ``detect_collisions`` — finds skill pairs that compete for the same
  trigger tokens; the fix is a negative trigger in the weaker description
  ("Do not use for X — use ``other-skill``").
- ``generate_index`` — writes ``skills/index.json`` (generated manifest,
  never hand-edited) so discovery tools read one file instead of parsing
  140 frontmatters.
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MIN_DESCRIPTION_LEN = 30
_COLLISION_TOKEN_OVERLAP = 0.6
_WORD_RE = re.compile(r"[a-z0-9]+")
_USE_WHEN_RE = re.compile(r"(?i)\b(use when|use for|triggers?|عند|عندما)\b")
_NEGATIVE_RE = re.compile(r"(?i)\b(do not use|don't use|not for|avoid when)\b")
# Family suffixes/markers that recur across a skill family — sharing one is
# not competition (ai-ml-lord vs ai-redteam-lord target different domains).
_FAMILY_TOKENS = frozenset(
    {
        "ai", "lord", "skill", "agent", "agents", "expert", "master",
        "patterns", "templates", "development", "design", "pro", "driven",
        "the", "and", "for",
        # role nouns — same reasoning: api-architect vs flutter-architect
        # do not compete, they are different domains sharing a job title.
        "architect", "engineer", "developer", "auditor", "manager",
        "designer", "analyst", "specialist", "writer", "coach",
        "consultant", "strategist", "reviewer", "producer", "advisor",
    }
)
_NON_SKILL_FILES = {"README.md", "index.json", "CONTRIBUTING.md", "CHANGELOG.md"}
# Single-word triggers too generic to signal competition — "engineer" or
# "design" shared by two skills does not make them ambiguous; a shared
# multi-word phrase does.
_GENERIC_TOKENS = frozenset(
    {
        "architect", "engineer", "engineering", "auditor", "expert",
        "developer", "design", "designer", "specialist", "master",
        "manager", "senior", "principal", "elite", "authority", "mastery",
        "deep", "level", "code", "guard", "quality", "web", "data",
        "api", "backend", "frontend", "development", "automation",
        "documentation", "accessibility", "security", "review", "audit",
        "debt", "gain", "help", "solution", "forces", "skill", "lord",
        "agent", "agents", "ai", "pro", "writer", "analyst", "coach",
        "consultant", "strategist", "reviewer", "producer", "advisor",
    }
)


@dataclass(frozen=True)
class SkillMeta:
    """Frontmatter of one skill file."""

    name: str
    path: str
    description: str
    triggers: tuple[str, ...] = ()
    personas: tuple[str, ...] = ()
    issues: tuple[str, ...] = field(default=())


def _as_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return ()


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter (never regex — the batch-2 lesson)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    data = yaml.safe_load(text[3:end])
    return data if isinstance(data, dict) else {}


def load_skill(path: Path, root: Path) -> SkillMeta:
    meta = parse_frontmatter(path.read_text(encoding="utf-8"))
    return SkillMeta(
        name=str(meta.get("name") or path.stem),
        path=str(path.relative_to(root)).replace("\\", "/"),
        description=str(meta.get("description") or ""),
        triggers=_as_tuple(meta.get("triggers")),
        personas=_as_tuple(meta.get("personas")),
    )


def load_skills(root: Path) -> list[SkillMeta]:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    paths = sorted(skills_dir.glob("*.md")) + sorted(
        skills_dir.glob("*/SKILL.md")
    )
    paths = [p for p in paths if p.name not in _NON_SKILL_FILES]
    metas: list[SkillMeta] = []
    for path in paths:
        try:
            metas.append(load_skill(path, root))
        except (OSError, yaml.YAMLError) as exc:
            warnings.warn(f"Skipping unreadable skill {path}: {exc}", stacklevel=2)
    return metas


def lint_description(meta: SkillMeta) -> list[str]:
    """agentskills-style description lint for one skill."""
    issues: list[str] = []
    desc = meta.description.strip()
    if not meta.name.strip():
        issues.append("missing name")
    if len(desc) < MIN_DESCRIPTION_LEN:
        issues.append(f"description too short ({len(desc)} < {MIN_DESCRIPTION_LEN})")
    if not meta.triggers:
        issues.append("no triggers — skill is unreachable by routing")
    if desc and not (_USE_WHEN_RE.search(desc) or meta.triggers):
        issues.append("description lacks trigger phrasing ('Use when …')")
    return issues


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def detect_collisions(metas: list[SkillMeta]) -> list[dict[str, str]]:
    """Find skill pairs competing for the same trigger space.

    A collision = shared explicit trigger, or name-token overlap >= 0.6.
    Skills already carrying a negative trigger naming the rival are exempt.
    """
    collisions: list[dict[str, str]] = []
    for i, a in enumerate(metas):
        for b in metas[i + 1 :]:
            reason = _collision_reason(a, b)
            if reason:
                collisions.append(
                    {"a": a.name, "b": b.name, "reason": reason}
                )
    return collisions


def _collision_reason(a: SkillMeta, b: SkillMeta) -> str:
    if _has_negative_trigger(a, b.name) or _has_negative_trigger(b, a.name):
        return ""
    name_tokens = _tokens(a.name) | _tokens(b.name)
    shared = {
        t
        for t in set(a.triggers) & set(b.triggers)
        if not _trivial_trigger(t, name_tokens)
    }
    if shared:
        return f"shared trigger: {sorted(shared)[0]}"
    ta = _tokens(a.name) - _FAMILY_TOKENS
    tb = _tokens(b.name) - _FAMILY_TOKENS
    if ta and tb and len(ta & tb) / min(len(ta), len(tb)) >= _COLLISION_TOKEN_OVERLAP:
        return "name token overlap"
    return ""


def _trivial_trigger(trigger: str, name_tokens: set[str]) -> bool:
    """Single-word triggers that are name tokens (family namespace) or
    generic role/domain words carry no routing ambiguity."""
    if " " in trigger:
        return False
    return trigger.lower() in name_tokens or trigger.lower() in _GENERIC_TOKENS


def _has_negative_trigger(meta: SkillMeta, rival: str) -> bool:
    desc = meta.description
    return bool(_NEGATIVE_RE.search(desc)) and rival in desc


def generate_index(metas: list[SkillMeta]) -> dict[str, Any]:
    """Generated manifest — discovery tools read this, not frontmatters."""
    return {
        "generated": True,
        "count": len(metas),
        "skills": [
            {
                "name": m.name,
                "path": m.path,
                "description": m.description,
                "triggers": list(m.triggers),
                "personas": list(m.personas),
            }
            for m in metas
        ],
    }


def write_index(root: Path, metas: list[SkillMeta]) -> Path:
    index_path = root / "skills" / "index.json"
    index_path.write_text(
        json.dumps(generate_index(metas), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return index_path


def run_lint(root: Path, write: bool = False) -> dict[str, Any]:
    """Full lint report: per-skill issues + collisions + optional index."""
    metas = load_skills(root)
    issue_map = {m.name: lint_description(m) for m in metas}
    issue_map = {k: v for k, v in issue_map.items() if v}
    collisions = detect_collisions(metas)
    index_path = str(write_index(root, metas)) if write else ""
    return {
        "ok": not issue_map and not collisions,
        "skills": len(metas),
        "issues": issue_map,
        "collisions": collisions,
        "index": index_path,
    }
