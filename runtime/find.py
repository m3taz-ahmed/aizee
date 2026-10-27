"""Natural-language discovery over skills, workflows, and tech-stack.

Adopted from Z4nzu/hackingtool ``find``/``goal`` concepts: given a free-text
query, score every catalog descriptor by token overlap on name + triggers +
frontmatter keywords, and return ranked matches. ``goal`` maps an objective
to the best-matching workflow and prints its step list.

Uses ``runtime.service_catalog.ServiceCatalog`` for indexing and
``runtime.kernel.Kernel`` for workflow step loading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.service_catalog import ServiceCatalog, build_catalog_from_directory


@dataclass(frozen=True)
class FindResult:
    name: str
    kind: str
    score: float
    file_path: str = ""
    matched_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "score": round(self.score, 3),
            "file": self.file_path,
            "matched": self.matched_tokens,
        }


@dataclass(frozen=True)
class GoalResult:
    objective: str
    workflow: str | None
    steps: list[str]
    match_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "workflow": self.workflow,
            "match_score": round(self.match_score, 3),
            "steps": self.steps,
        }


_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_MIN_SCORE = 0.05


def find(query: str, os_root: Path, limit: int = 10) -> list[FindResult]:
    """Rank skills/workflows/tech-stack by NL query relevance."""
    catalog = _build_full_catalog(os_root)
    tokens = _tokenize(query)
    if not tokens:
        return []
    results: list[FindResult] = []
    for desc in catalog.all():
        score, matched = _score(desc, tokens)
        if score >= _MIN_SCORE:
            results.append(FindResult(
                name=desc.name, kind=desc.kind, score=score,
                file_path=desc.file_path, matched_tokens=matched,
            ))
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


def goal(objective: str, os_root: Path, project_root: Path) -> GoalResult:
    """Map a free-text objective to the best workflow and extract its steps."""
    catalog = _build_full_catalog(os_root)
    tokens = _tokenize(objective)
    best_score = 0.0
    best_desc = None
    for desc in catalog.by_kind("workflow"):
        score, _ = _score(desc, tokens)
        if score > best_score:
            best_score = score
            best_desc = desc
    if best_desc is None or best_score < _MIN_SCORE:
        return GoalResult(objective=objective, workflow=None, steps=[], match_score=0.0)
    steps = _extract_workflow_steps(Path(best_desc.file_path))
    return GoalResult(
        objective=objective,
        workflow=best_desc.name,
        steps=steps,
        match_score=best_score,
    )


def _build_full_catalog(os_root: Path) -> ServiceCatalog:
    descriptors: list[Any] = []
    for subdir, kind in (("skills", "skill"), ("workflows", "workflow"), ("tech-stack", "tech-stack")):
        cat = build_catalog_from_directory(os_root / subdir, kind=kind)
        descriptors.extend(cat.all())
    return ServiceCatalog(descriptors)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _score(desc: Any, tokens: list[str]) -> tuple[float, list[str]]:
    """Score a descriptor against query tokens; return (score, matched)."""
    matched: list[str] = []
    total = 0.0
    for token in tokens:
        hit = 0.0
        if token == desc.name.lower():
            hit = 3.0
        elif token in desc.name.lower():
            hit = 1.5
        elif any(token in t or t in token for t in desc.triggers):
            hit = 1.0
        elif any(token in p for p in desc.personas):
            hit = 0.5
        if hit:
            total += hit
            matched.append(token)
    return total / max(len(tokens), 1), matched


def _extract_workflow_steps(workflow_path: Path) -> list[str]:
    """Extract numbered/bulleted steps from a workflow markdown file."""
    if not workflow_path.exists():
        return []
    steps: list[str] = []
    in_steps = False
    for line in workflow_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not in_steps and any(lower.startswith(h) for h in ("## steps", "## procedure", "## workflow", "## execution")):
            in_steps = True
            continue
        if in_steps:
            if stripped.startswith("#"):
                break
            m = re.match(r"^(?:\d+[.)]\s*|[-*]\s*)(.+)", stripped)
            if m and len(steps) < 20:
                steps.append(m.group(1).strip())
    return steps
