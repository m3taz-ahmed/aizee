#!/usr/bin/env python3
"""Goldfish review planner - deterministic parts of the EGM review protocol.

Ported concepts from google/elephant-goldfish-model (Apache-2.0, see
resources/LICENSE-EGM): semantic split discovery, the five-stage reviewer
pipeline, pipeline presets, severity triage, and traceability consolidation.

This module never calls an LLM. It plans the review (which reviewers read
which line ranges, in which order, writing to which artifacts) and
consolidates findings afterwards. Spawning the fresh-context subagents is
the agent harness's job - see workflows/65-goldfish-review.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# Boundary headers the protocol recognizes as the spec/plan seam, in
# priority order (first unambiguous match wins).
_SPLIT_HEADERS: tuple[str, ...] = (
    "## detailed implementation plan",
    "## implementation plan",
    "## work breakdown",
    "## implementation steps",
)

_MAX_FINDINGS = 200  # consolidation guard, mirrors spec analysis cap


class ReviewPreset(str, Enum):
    """Curated pipeline presets (EGM Step 2 gate)."""

    INTERACTIVE = "interactive"
    UNINTERRUPTED = "uninterrupted"
    FEATURE_SPEC = "feature_spec"
    IMPLEMENTATION = "implementation"


class ReviewScope(str, Enum):
    """Which document range a stage reads."""

    FULL = "full"
    FEATURE = "feature"
    DETAILED = "detailed"
    FEATURE_AND_DETAILED = "feature_and_detailed"


class FindingSeverity(str, Enum):
    """EGM finding severities."""

    BLOCKER = "blocker"
    MAJOR = "major"
    NIT = "nit"


@dataclass(frozen=True)
class SemanticSplit:
    """Discovered feature-spec vs implementation-plan boundary.

    Line numbers are 1-based and inclusive. ``detailed_start`` is 0 when the
    document carries no implementation-plan section.
    """

    boundary_line: int
    feature_start: int
    feature_end: int
    detailed_start: int
    detailed_end: int
    total_lines: int

    @property
    def has_plan(self) -> bool:
        return self.boundary_line > 0

    def lines_for(self, scope: ReviewScope) -> tuple[int, int] | None:
        """Resolve a scope to its (start, end) line range, or None if absent."""
        if scope == ReviewScope.FULL:
            return (1, self.total_lines)
        if scope == ReviewScope.FEATURE:
            return (self.feature_start, self.feature_end)
        if scope == ReviewScope.DETAILED:
            if not self.has_plan:
                return None
            return (self.detailed_start, self.detailed_end)
        return (self.feature_start, self.detailed_end) if self.has_plan else (1, self.total_lines)


@dataclass(frozen=True)
class ReviewStage:
    """One stage of the Goldfish pipeline."""

    number: int
    name: str
    reviewers: tuple[str, ...]
    scope: ReviewScope
    artifact: str
    context_files: bool  # whether GoldfishContext files are passed


# The five stages, in execution order (EGM numbering 5-9 kept for fidelity).
STAGES: tuple[ReviewStage, ...] = (
    ReviewStage(
        5, "Initial Zoom Out",
        ("zoom_out", "inventive_catalyst"),
        ReviewScope.FULL, "zoom_out_report.md", True,
    ),
    ReviewStage(
        6, "Comprehension Test",
        ("comprehension",),
        ReviewScope.FEATURE_AND_DETAILED, "comprehension_report.md", False,
    ),
    ReviewStage(
        7, "Design Critique",
        ("design_critic", "structural", "style"),
        ReviewScope.FEATURE, "critic_report.md", True,
    ),
    ReviewStage(
        8, "Intermediate Zoom Out",
        ("zoom_out",),
        ReviewScope.FULL, "intermediate_zoom_out_report.md", True,
    ),
    ReviewStage(
        9, "Implementation Readiness",
        ("implementation_readiness", "codebase_details", "style"),
        ReviewScope.DETAILED, "implementation_readiness_report.md", True,
    ),
)

_PRESET_STAGES: dict[ReviewPreset, tuple[int, ...]] = {
    ReviewPreset.INTERACTIVE: (5, 6, 7, 8, 9),
    ReviewPreset.UNINTERRUPTED: (5, 6, 7, 8, 9),
    ReviewPreset.FEATURE_SPEC: (5, 6, 7, 8),
    ReviewPreset.IMPLEMENTATION: (9,),
}

_CONSOLIDATED_ARTIFACT = "consolidated_review_report.md"


def discover_semantic_split(text: str) -> SemanticSplit:
    """Locate the spec/plan boundary header in a design document.

    Returns boundary_line=0 with the whole document as the feature range
    when no implementation-plan section exists.
    """
    lines = text.splitlines()
    boundary = 0
    for i, line in enumerate(lines, start=1):
        if line.strip().lower() in _SPLIT_HEADERS:
            boundary = i
            break
    if boundary == 0:
        return SemanticSplit(
            boundary_line=0, feature_start=1, feature_end=len(lines),
            detailed_start=0, detailed_end=0, total_lines=len(lines),
        )
    return SemanticSplit(
        boundary_line=boundary, feature_start=1, feature_end=boundary - 1,
        detailed_start=boundary, detailed_end=len(lines), total_lines=len(lines),
    )


def _stage_plan(stage: ReviewStage, split: SemanticSplit) -> dict[str, Any]:
    rng = split.lines_for(stage.scope)
    return {
        "stage": stage.number,
        "name": stage.name,
        "reviewers": list(stage.reviewers),
        "scope": stage.scope.value,
        "lines": list(rng) if rng else None,
        "artifact": stage.artifact,
        "context_files": stage.context_files,
    }


def plan_review(text: str, preset: ReviewPreset) -> dict[str, Any]:
    """Build the full review plan for *text* under *preset*.

    FEATURE_SPEC bypasses split discovery (FeatureRange = 1..End) exactly as
    the EGM preset requires; IMPLEMENTATION jumps to Stage 9 and is a no-op
    plan when no implementation section exists.
    """
    if preset == ReviewPreset.FEATURE_SPEC:
        split = SemanticSplit(
            boundary_line=0, feature_start=1,
            feature_end=len(text.splitlines()), detailed_start=0,
            detailed_end=0, total_lines=len(text.splitlines()),
        )
    else:
        split = discover_semantic_split(text)
    wanted = _PRESET_STAGES[preset]
    stages = [_stage_plan(s, split) for s in STAGES if s.number in wanted]
    skipped = [s["name"] for s in stages if s["lines"] is None]
    stages = [s for s in stages if s["lines"] is not None]
    return {
        "preset": preset.value,
        "interactive": preset != ReviewPreset.UNINTERRUPTED,
        "consolidated": preset == ReviewPreset.UNINTERRUPTED,
        "consolidated_artifact": _CONSOLIDATED_ARTIFACT,
        "split": {
            "boundary_line": split.boundary_line,
            "feature": [split.feature_start, split.feature_end],
            "detailed": [split.detailed_start, split.detailed_end] if split.has_plan else None,
            "total_lines": split.total_lines,
        },
        "stages": stages,
        "skipped_stages": skipped,
        "personas_dir": "resources/goldfish_personas",
        "standards_dir": "resources/document_standards",
        "max_reaudits": 1,
    }


_SEVERITY_RE = re.compile(
    r"(?:\*\*)?severity(?:\*\*)?\s*[:=\-]?\s*\[?\s*(blocker|major|nit|critical|high|medium|low)",
    re.IGNORECASE,
)
_EMOJI_SEVERITY = {"🔴": FindingSeverity.BLOCKER, "🟠": FindingSeverity.MAJOR, "🟡": FindingSeverity.MAJOR, "🟢": FindingSeverity.NIT, "🔵": FindingSeverity.NIT}
_SEVERITY_ALIASES = {
    "blocker": FindingSeverity.BLOCKER, "critical": FindingSeverity.BLOCKER,
    "high": FindingSeverity.MAJOR, "major": FindingSeverity.MAJOR,
    "medium": FindingSeverity.MAJOR, "nit": FindingSeverity.NIT,
    "low": FindingSeverity.NIT,
}
_SCOPE_HINT_RE = re.compile(r"(`[^`]+`|[\w./\\-]+\.\w{1,6}(?::\d+(?:-\d+)?)?)")


def parse_findings(report_text: str, stage: int | None = None) -> list[dict[str, Any]]:
    """Extract severity-tagged findings from a stage report.

    Tolerant of both EGM output formats (``**Severity**: Blocker`` blocks and
    emoji-prefixed bullets). Unscored content is ignored - no invented findings.
    """
    findings: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in report_text.splitlines():
        sev = _line_severity(line)
        if sev is not None:
            current = {"severity": sev.value, "stage": stage, "text": line.strip(), "scope": ""}
            findings.append(current)
        elif current is not None and line.strip().startswith(("**", "-", "*")):
            scope_m = _SCOPE_HINT_RE.search(line)
            if scope_m and ("scope" in line.lower() or not current["scope"]):
                current["scope"] = scope_m.group(1).strip("`")
            if len(current["text"]) < 4000:
                current["text"] += "\n" + line.strip()
    return findings[:_MAX_FINDINGS]


def _line_severity(line: str) -> FindingSeverity | None:
    for emoji, sev in _EMOJI_SEVERITY.items():
        if emoji in line:
            return sev
    m = _SEVERITY_RE.search(line)
    if m:
        return _SEVERITY_ALIASES[m.group(1).lower()]
    return None


def consolidate_findings(stage_reports: dict[str, str]) -> dict[str, Any]:
    """Merge per-stage reports into a consolidated report plan.

    Input maps artifact filename -> report markdown. Produces the
    Traceability Matrix the EGM uninterrupted flow emits.
    """
    rows: list[dict[str, Any]] = []
    counts = {s.value: 0 for s in FindingSeverity}
    for artifact, text in stage_reports.items():
        stage_no = next((s.number for s in STAGES if s.artifact == artifact), None)
        for i, f in enumerate(parse_findings(text, stage=stage_no), start=1):
            counts[f["severity"]] += 1
            rows.append({
                "id": f"F{len(rows) + 1:03d}",
                "severity": f["severity"],
                "stage": f["stage"],
                "source_artifact": artifact,
                "scope": f["scope"],
                "summary": f["text"].splitlines()[0][:200],
                "finding_index": i,
            })
    rows.sort(key=lambda r: (list(FindingSeverity).index(FindingSeverity(r["severity"])), r["id"]))
    return {
        "artifact": _CONSOLIDATED_ARTIFACT,
        "total_findings": len(rows),
        "by_severity": counts,
        "traceability_matrix": rows,
    }


def load_document(path: Path, max_bytes: int = 2_000_000) -> str:
    """Read a design document with a size guard (mirrors analysis caps)."""
    data = path.read_bytes()[: max_bytes + 1]
    if len(data) > max_bytes:
        raise ValueError(f"document too large: {path} ({len(data)} bytes)")
    return data.decode("utf-8", errors="replace")
