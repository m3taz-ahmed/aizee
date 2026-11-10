"""BMAD lifecycle phase detection for persona routing bias.

Reads the project-local ``_bmad/`` runtime (config + ``_bmad-output/``
artifact tree) and maps the current product-development phase to a
persona bias. Returns ``None`` when no BMAD initiative is active so
callers fall back to pure keyword detection — zero regression for
non-BMAD projects.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any

import config


class LifecyclePhase(str, Enum):
    """Product-development phases inferred from BMAD output artifacts."""

    DISCOVERY = "discovery"
    PRD = "prd"
    BREAKDOWN = "breakdown"
    ARCHITECTURE = "architecture"
    UX = "ux"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    RETROSPECTIVE = "retrospective"


# Filename markers scanned under the active initiative folder. Ordered by
# pipeline precedence — the most advanced marker present wins, because
# later artifacts imply earlier phases completed.
_PHASE_MARKERS: tuple[tuple[LifecyclePhase, re.Pattern[str]], ...] = (
    (LifecyclePhase.RETROSPECTIVE, re.compile(r"retro|retrospective", re.IGNORECASE)),
    (LifecyclePhase.REVIEW, re.compile(r"review|sign-?off|approval", re.IGNORECASE)),
    (LifecyclePhase.IMPLEMENTATION, re.compile(r"(^|[-_])stor(y|ies)([-_.]|$)|(^|[-_])impl", re.IGNORECASE)),
    (LifecyclePhase.BREAKDOWN, re.compile(r"epic", re.IGNORECASE)),
    (LifecyclePhase.UX, re.compile(r"(^|[-_])ux([-_.]|$)|user-?experience|wireframe|mockup", re.IGNORECASE)),
    (LifecyclePhase.ARCHITECTURE, re.compile(r"arch(itecture)?|system-?design|adr[-_.]", re.IGNORECASE)),
    (LifecyclePhase.PRD, re.compile(r"(^|[-_])(prd|srs|requirements?)([-_.]|$)", re.IGNORECASE)),
    (LifecyclePhase.DISCOVERY, re.compile(r"brief|charter|narrative|opportunity|business-?case|pitch|launch", re.IGNORECASE)),
)

# Persona bias per phase — tips close calls and routes generic
# continuation text ("continue", "كمّل") to the phase-appropriate persona
# without overriding strong keyword signals.
PHASE_PERSONA_BIAS: dict[LifecyclePhase, dict[str, float]] = {
    LifecyclePhase.DISCOVERY: {"PRODUCT": 0.4, "DOC": 0.2},
    LifecyclePhase.PRD: {"PRODUCT": 0.4},
    LifecyclePhase.BREAKDOWN: {"PRODUCT": 0.4, "QA": 0.2},
    LifecyclePhase.ARCHITECTURE: {"ARCH": 0.4},
    LifecyclePhase.UX: {"UX": 0.4},
    LifecyclePhase.IMPLEMENTATION: {"DEV": 0.4, "QA": 0.15},
    LifecyclePhase.REVIEW: {"QA": 0.4, "ARCH": 0.25},
    LifecyclePhase.RETROSPECTIVE: {"PRODUCT": 0.3, "QA": 0.25},
}

# Pipeline precedence — later phases imply earlier ones completed, so the
# most advanced marker present wins.
_PHASE_ORDER: tuple[LifecyclePhase, ...] = (
    LifecyclePhase.DISCOVERY,
    LifecyclePhase.PRD,
    LifecyclePhase.BREAKDOWN,
    LifecyclePhase.ARCHITECTURE,
    LifecyclePhase.UX,
    LifecyclePhase.IMPLEMENTATION,
    LifecyclePhase.REVIEW,
    LifecyclePhase.RETROSPECTIVE,
)

_MAX_SCAN_FILES = 500
_MAX_SCAN_DEPTH = 5


def _load_bmad_config(bmad_dir: Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        import tomli as tomllib  # type: ignore[unused-ignore]
    config_path = bmad_dir / "config.toml"
    if not config_path.is_file():
        return {}
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _initiative_dir(project_root: Path) -> Path | None:
    """Resolve ``{output_folder}/{active_initiative}`` from _bmad config."""
    bmad_dir = project_root / "_bmad"
    if not bmad_dir.is_dir():
        return None
    cfg = _load_bmad_config(bmad_dir)
    core = cfg.get("core")
    if not isinstance(core, dict):
        return None
    initiative = core.get("active_initiative")
    if not initiative or not isinstance(initiative, str):
        return None
    output_folder = core.get("output_folder", "{project-root}/_bmad-output")
    if not isinstance(output_folder, str):
        output_folder = "{project-root}/_bmad-output"
    base = Path(output_folder.replace("{project-root}", str(project_root)))
    candidate = base / initiative
    return candidate if candidate.is_dir() else None


def _classify_filename(name: str) -> LifecyclePhase | None:
    for phase, pattern in _PHASE_MARKERS:
        if pattern.search(name):
            return phase
    return None


def _scan_phase(initiative_dir: Path) -> LifecyclePhase | None:
    """Return the most advanced phase marker found in the artifact tree."""
    best: LifecyclePhase | None = None
    best_rank = -1
    scanned = 0
    for path in initiative_dir.rglob("*"):
        if scanned >= _MAX_SCAN_FILES:
            break
        if path.is_dir() or path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            continue
        if len(path.relative_to(initiative_dir).parts) > _MAX_SCAN_DEPTH:
            continue
        scanned += 1
        phase = _classify_filename(path.name)
        if phase is None:
            continue
        rank = _PHASE_ORDER.index(phase)
        if rank > best_rank:
            best, best_rank = phase, rank
    return best if best is not None else LifecyclePhase.DISCOVERY


def detect_phase(project_root: Path | None = None) -> LifecyclePhase | None:
    """Detect the current BMAD lifecycle phase for *project_root*.

    Returns ``None`` when BMAD is absent or no initiative is active —
    callers must treat that as "no bias" and keep keyword-only routing.
    """
    root = project_root or config.discover_root()
    try:
        initiative_dir = _initiative_dir(root)
    except OSError:
        return None
    if initiative_dir is None:
        return None
    try:
        return _scan_phase(initiative_dir)
    except OSError:
        return None
