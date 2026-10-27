"""Configurable verification depth for governed actions.

Adopted from google/artemis `verification_level` (off/final/checkpoints/strict).
The dial controls OPTIONAL extra verification layered on top of the mandatory
gate order ``Probity -> Guardian -> Policy -> LoopDetector -> Budget -> Audit``.
Those six gates are never disabled by any verify level (fail-closed, SEC-13).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from runtime.schemas import ValidationError


class VerificationLevel(str, Enum):
    """Depth of post-policy verification for a governed action."""

    OFF = "off"
    FINAL = "final"
    CHECKPOINTS = "checkpoints"
    STRICT = "strict"


DEFAULT_LEVEL = VerificationLevel.FINAL


def resolve_verify(value: str | VerificationLevel | None) -> VerificationLevel:
    """Parse a verify argument. None -> FINAL; unknown values are rejected."""
    if value is None:
        return DEFAULT_LEVEL
    if isinstance(value, VerificationLevel):
        return value
    try:
        return VerificationLevel(str(value).strip().lower())
    except ValueError:
        raise ValidationError(  # noqa: B904 - context carries the bad value
            f"unknown verification level {value!r}",
            context={"allowed": [lv.value for lv in VerificationLevel]},
        )


def run_verification(
    level: VerificationLevel,
    action_type: str,
    action_data: dict[str, Any],
    project_root: Any,
) -> dict[str, Any] | None:
    """Run optional extra checks implied by ``level``.

    Returns ``None`` when the action passes, or an ``observe``-shaped dict
    describing the violation. ``OFF`` and ``FINAL`` add nothing here (the
    mandatory gates + finalize already cover them); ``CHECKPOINTS`` adds
    plan-diff validation when a plan/diff payload is present; ``STRICT``
    additionally scans new imports against the supply-chain policy.
    """
    if level in (VerificationLevel.OFF, VerificationLevel.FINAL):
        return None
    diff_text = _extract_diff(action_data)
    if level in (VerificationLevel.CHECKPOINTS, VerificationLevel.STRICT) and diff_text:
        from pathlib import Path

        from runtime.plan_diff_validator import PlanDiffValidator

        result = PlanDiffValidator(Path(project_root)).validate_diff(diff_text)
        if not result.ok:
            errors = [f.to_dict() for f in result.errors]
            return _violation("plan_diff", errors, level)
    if level == VerificationLevel.STRICT and diff_text:
        chain_findings = _check_supply_chain(diff_text, project_root)
        if chain_findings:
            return _violation("supply_chain", chain_findings, level)
    return None


def _extract_diff(action_data: dict[str, Any]) -> str:
    diff = action_data.get("diff") or action_data.get("patch") or ""
    return diff if isinstance(diff, str) else ""


def _check_supply_chain(diff_text: str, project_root: Any) -> list[dict[str, Any]]:
    """Run supply-chain import checks over added lines of a diff."""
    added = [ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    code = "\n".join(added)
    if not code.strip():
        return []
    # Derive the diff's target filename so the guard picks the right
    # ecosystem extractor (a bare "<source>" has no suffix -> no findings).
    filename = "scan.py"
    for ln in diff_text.splitlines():
        if ln.startswith("+++ b/"):
            filename = ln[6:].strip() or filename
            break
    try:
        from pathlib import Path

        from runtime.supply_chain_guard import SupplyChainGuard

        findings = SupplyChainGuard(Path(project_root)).scan_source(code, filename=filename)
        return [
            {"module": f.module, "file": f.file, "ecosystem": f.ecosystem.value, "line": f.line}
            for f in findings
        ]
    except Exception:
        # Supply-chain tooling absent -> no opinion; mandatory gates still run.
        return []


def _violation(kind: str, violations: Any, level: VerificationLevel) -> dict[str, Any]:
    return {
        "observe": True,
        "verdict": "block",
        "verify": level.value,
        "violation": kind,
        "violations": violations,
        "error": {
            "code": "VERIFY_FAILED",
            "message": f"verification level '{level.value}' rejected the action ({kind})",
        },
    }
