"""Artifact-aware pipeline catalogs (CCGS workflow-catalog.yaml adoption).

A workflow file may embed one fenced ``yaml`` block containing a pipeline
catalog: ``phases`` (ordered ladder) and/or ``paths`` (alternate routes such
as ``minimal``). Each step declares an ``artifact`` check — a file ``glob``
with optional ``pattern``/``min_count``, alternative ``any_of`` specs, or a
``note``-only fallback — so position in the pipeline is detected from files
on disk instead of being asked.

``pipeline_status`` reports per-step status (done / missing / manual), the
current phase, and the next required step. Gate verdicts stay advisory —
this module answers "where am I", never "may I proceed".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)
_CATALOG_KEYS = ("phases", "paths", "steps")
_STATES = ("done", "missing", "manual")


@dataclass(frozen=True)
class StepStatus:
    id: str
    name: str
    required: bool
    repeatable: bool
    status: str  # done | missing | manual
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "required": self.required,
            "repeatable": self.repeatable,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PhaseStatus:
    id: str
    label: str
    done: bool
    current: bool
    steps: tuple[StepStatus, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "done": self.done,
            "current": self.current,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass(frozen=True)
class PipelineStatus:
    workflow: str
    label: str
    route: str
    phases: tuple[PhaseStatus, ...]
    current_phase: str
    next_step: str
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "label": self.label,
            "route": self.route,
            "current_phase": self.current_phase,
            "next_step": self.next_step,
            "complete": self.complete,
            "phases": [p.to_dict() for p in self.phases],
        }


def _load_catalog_block(workflow_path: Path) -> dict[str, Any]:
    """Extract the first fenced yaml block holding pipeline keys."""
    try:
        text = workflow_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for match in _YAML_BLOCK_RE.finditer(text):
        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and any(k in data for k in _CATALOG_KEYS):
            return data
    return {}


def list_catalogs(os_root: Path) -> list[str]:
    """Workflow ids that embed a pipeline catalog."""
    workflows_dir = os_root / "workflows"
    found: list[str] = []
    for path in sorted(workflows_dir.glob("*.md")):
        if _load_catalog_block(path):
            found.append(path.stem)
    return found


def _glob_files(project_root: Path, pattern: str) -> list[Path]:
    try:
        return [p for p in project_root.glob(pattern) if p.is_file()]
    except (OSError, ValueError):
        return []


def _translate_pattern(pattern: str) -> str:
    """Accept POSIX-ish classes CCGS specs use (`[[:space:]]` -> `\\s`)."""
    return pattern.replace("[[:space:]]", r"\s")


def _spec_satisfied(project_root: Path, spec: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate one artifact spec against the project tree."""
    glob_pat = spec.get("glob")
    if not glob_pat:
        return False, str(spec.get("note", "manual check"))
    files = _glob_files(project_root, str(glob_pat))
    min_count = int(spec.get("min_count", 1) or 1)
    if len(files) < min_count:
        return False, f"{glob_pat}: {len(files)}/{min_count} file(s)"
    text_pat = spec.get("pattern")
    if text_pat:
        try:
            rx = re.compile(_translate_pattern(str(text_pat)))
        except re.error:
            rx = None
        if rx is None:
            return False, f"bad pattern: {text_pat}"
        if not any(
            rx.search(p.read_text(encoding="utf-8", errors="ignore"))
            for p in files[:50]
        ):
            return False, f"pattern not found in {glob_pat}"
    return True, str(glob_pat)


def check_artifact(project_root: Path, artifact: dict[str, Any] | None) -> tuple[str, str]:
    """Tri-state a step's artifact: done / missing / manual (undetectable)."""
    if not artifact:
        return "manual", "no artifact check"
    any_of = artifact.get("any_of")
    if not artifact.get("glob") and not any_of:
        return "manual", str(artifact.get("note", "manual check"))
    if isinstance(any_of, list) and any_of:
        details: list[str] = []
        for spec in any_of:
            if not isinstance(spec, dict):
                continue
            ok, detail = _spec_satisfied(project_root, spec)
            details.append(detail)
            if ok:
                return "done", detail
        return "missing", "; ".join(details)
    ok, detail = _spec_satisfied(project_root, artifact)
    return ("done" if ok else "missing"), detail


def _resolve_route(catalog: dict[str, Any], path: str | None) -> tuple[str, list[dict[str, Any]]]:
    """Pick the route: explicit path name, else the phases ladder."""
    paths = catalog.get("paths") or {}
    if path:
        route = paths.get(path) or {}
        return path, _phases_from_route(route)
    if path is None and "phases" in catalog:
        return "phases", _phases_from_ladder(catalog.get("phases") or {})
    # No phases ladder: fall back to first declared path.
    for name, route in paths.items():
        return str(name), _phases_from_route(route)
    return "", []


def _phases_from_route(route: dict[str, Any]) -> list[dict[str, Any]]:
    steps = route.get("steps") or []
    return [{"id": route.get("label", "path"), "label": route.get("label", ""), "steps": steps}]


def _phases_from_ladder(phases: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = sorted(
        phases.items(),
        key=lambda kv: list(phases).index(kv[0]),
    )
    return [
        {"id": str(pid), "label": str(p.get("label", pid)), "steps": p.get("steps") or []}
        for pid, p in ordered
        if isinstance(p, dict)
    ]


def pipeline_status(
    os_root: Path,
    project_root: Path,
    workflow_id: str,
    path: str | None = None,
) -> PipelineStatus | None:
    """Compute pipeline position for one cataloged workflow."""
    wf_path = os_root / "workflows" / f"{workflow_id}.md"
    if not wf_path.exists():
        return None
    catalog = _load_catalog_block(wf_path)
    if not catalog:
        return None
    route_name, phase_specs = _resolve_route(catalog, path)
    statuses: list[PhaseStatus] = []
    current_phase = ""
    next_step = ""
    saw_current = False
    for spec in phase_specs:
        step_statuses: list[StepStatus] = []
        for step in spec["steps"]:
            if not isinstance(step, dict):
                continue
            state, detail = check_artifact(project_root, step.get("artifact"))
            step_statuses.append(StepStatus(
                id=str(step.get("id", "")),
                name=str(step.get("name", step.get("id", ""))),
                required=bool(step.get("required", False)),
                repeatable=bool(step.get("repeatable", False)),
                status=state,
                detail=detail,
            ))
        required_steps = [s for s in step_statuses if s.required]
        phase_done = bool(required_steps) and all(
            s.status == "done" for s in required_steps
        )
        is_current = not phase_done and not saw_current
        if is_current:
            saw_current = True
            current_phase = str(spec["id"])
            for s in required_steps:
                if s.status != "done":
                    next_step = s.id or s.name
                    break
        statuses.append(PhaseStatus(
            id=str(spec["id"]),
            label=str(spec.get("label", spec["id"])),
            done=phase_done,
            current=is_current,
            steps=tuple(step_statuses),
        ))
    return PipelineStatus(
        workflow=workflow_id,
        label=str(catalog.get("label", workflow_id)),
        route=route_name,
        phases=tuple(statuses),
        current_phase=current_phase,
        next_step=next_step,
        complete=bool(statuses) and all(p.done for p in statuses),
    )
