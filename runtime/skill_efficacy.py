"""Skill-efficacy evidence: before/after A/B verdicts with an audit trail.

Adopted from the 2026-11-25 ecosystem scan — converging evidence from
microsoft/SkillOpt (NeurIPS 2026: skills trained with validation gates,
epochs and batch sizes in text space), nodegenie/usethisskill (proven-skill
badges recording model+commit), and the animate-ecosystem study backlog
row 20 (``docs/studies/study-animate-skill-ecosystem-2026-11-15.md``).

Doctrine: no skill may *claim* efficacy without recorded before/after
evidence. A/B verdicts are append-only receipts: the scenario, the verdict
with the skill loaded, the verdict without it, the model, the commit, and
a rig fingerprint — enough for a third party to ask "says who, on what rig?"

This module is the measurement scaffold. It records verdicts produced by
humans, harness runs, or live-model evaluators; it does not itself call an
LLM. Aggregation derives a badge per skill:

- ``proven``   — net-positive deltas, zero regressions, evidence on 1+ scenarios
- ``flat``     — measured, but the skill changed nothing
- ``harmful``  — any recorded regression (skill made a pass into a fail)
- ``unmeasured`` — no evidence at all (the default state of every skill)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from runtime.schemas import ValidationError

VALID_VERDICTS = frozenset({"pass", "fail", "skip"})


class Badge(str, Enum):
    """Aggregate efficacy verdict for one skill."""

    PROVEN = "proven"
    FLAT = "flat"
    HARMFUL = "harmful"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class EfficacyRecord:
    """One A/B receipt: same scenario, same rig, skill on vs off."""

    skill: str
    scenario: str
    verdict_with: str
    verdict_without: str
    model: str
    commit: str
    rig: str
    ts: str
    notes: str = ""

    @property
    def delta(self) -> int:
        """+1 skill helped, -1 skill hurt, 0 no measurable difference."""
        if self.verdict_with == "skip" or self.verdict_without == "skip":
            return 0
        if self.verdict_with == self.verdict_without:
            return 0
        return 1 if self.verdict_with == "pass" else -1

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "delta": self.delta}


def rig_fingerprint(model: str, scenario: str, extra: str = "") -> str:
    """Stable fingerprint of the comparison rig — fair A/B needs one rig."""
    payload = json.dumps({"model": model, "scenario": scenario, "extra": extra}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def current_commit(root: Path) -> str:
    """Best-effort git commit; empty string when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def make_record(
    skill: str,
    scenario: str,
    verdict_with: str,
    verdict_without: str,
    model: str,
    commit: str,
    notes: str = "",
) -> EfficacyRecord:
    """Validated constructor — bad verdicts never enter the ledger."""
    if not skill.strip():
        raise ValidationError("skill name must not be empty", context={"skill": skill})
    if not scenario.strip():
        raise ValidationError("scenario must not be empty", context={"scenario": scenario})
    for label, verdict in (("verdict_with", verdict_with), ("verdict_without", verdict_without)):
        if verdict not in VALID_VERDICTS:
            raise ValidationError(
                f"{label} must be one of {sorted(VALID_VERDICTS)}",
                context={label: verdict},
            )
    return EfficacyRecord(
        skill=skill.strip(),
        scenario=scenario.strip(),
        verdict_with=verdict_with,
        verdict_without=verdict_without,
        model=model or "unspecified",
        commit=commit,
        rig=rig_fingerprint(model or "unspecified", scenario.strip()),
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        notes=notes,
    )


class SkillEfficacyStore:
    """Append-only JSONL ledger of A/B efficacy receipts."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: EfficacyRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows


def badge_for(rows: list[dict[str, Any]]) -> Badge:
    """Aggregate one skill's receipts into a badge."""
    if not rows:
        return Badge.UNMEASURED
    deltas = [int(r.get("delta", 0)) for r in rows]
    if any(d < 0 for d in deltas):
        return Badge.HARMFUL
    if any(d > 0 for d in deltas):
        return Badge.PROVEN
    return Badge.FLAT


def efficacy_report(store: SkillEfficacyStore, skill: str = "") -> dict[str, Any]:
    """Per-skill badge report; ``skill`` narrows to one skill."""
    rows = store.records()
    by_skill: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if skill and row.get("skill") != skill:
            continue
        by_skill.setdefault(str(row.get("skill", "")), []).append(row)
    skills = {
        name: {
            "badge": badge_for(skill_rows).value,
            "records": len(skill_rows),
            "helped": sum(1 for r in skill_rows if int(r.get("delta", 0)) > 0),
            "regressions": sum(1 for r in skill_rows if int(r.get("delta", 0)) < 0),
            "scenarios": sorted({str(r.get("scenario", "")) for r in skill_rows}),
            "models": sorted({str(r.get("model", "")) for r in skill_rows}),
            "last_ts": max((str(r.get("ts", "")) for r in skill_rows), default=""),
        }
        for name, skill_rows in sorted(by_skill.items())
    }
    counts = {b.value: 0 for b in Badge}
    for info in skills.values():
        badge_value = str(info["badge"])
        counts[badge_value] += 1
    return {"skills": skills, "badges": counts, "ledger": str(store.path)}
