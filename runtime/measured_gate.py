"""Measured-gate: deliverable checks that return metrics, not impressions.

Adopted from the animate-ecosystem study (``docs/studies/
study-animate-skill-ecosystem-2026-11-15.md``): animate's ``review.mjs``,
scroll-world's SSIM seam gate, and reanimate's compare loop all share one
doctrine — completion is *measured*, not eyeballed. This module gives that
doctrine a runtime home:

- :class:`MetricResult` — one measured value, its threshold/direction, and
  the evidence (command/artifact) that produced it.
- :class:`MeasuredGate` — registry + runner producing a :class:`GateReport`
  whose ``passed`` is derived from metrics, never from prose.
- :func:`rig_fingerprint` — stable fingerprint of the comparison rig
  (``[EVAL-01]``): identical rigs are a precondition for fair A/B checks.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from runtime.schemas import ValidationError

CheckFn = Callable[[dict[str, Any]], list["MetricResult"]]


@dataclass(frozen=True)
class MetricResult:
    """One measured value with its pass contract and evidence.

    ``direction`` interprets ``threshold``: ``"max"`` fails when
    ``value > threshold`` (e.g. loudness ceilings), ``"min"`` fails when
    ``value < threshold`` (e.g. SSIM floors). ``threshold=None`` marks the
    metric informational — recorded but never failing.
    """

    name: str
    value: float
    threshold: float | None = None
    direction: str = "max"
    unit: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.direction not in ("max", "min"):
            raise ValidationError(
                f"unknown direction {self.direction!r}",
                context={"allowed": ["max", "min"], "metric": self.name},
            )

    @property
    def passed(self) -> bool:
        if self.threshold is None:
            return True
        if self.direction == "max":
            return self.value <= self.threshold
        return self.value >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "direction": self.direction,
            "unit": self.unit,
            "passed": self.passed,
            "evidence": self.evidence,
        }


@dataclass
class GateReport:
    """The measured outcome of one gate run — cite this, not adjectives."""

    metrics: list[MetricResult] = field(default_factory=list)
    rig: str = ""

    @property
    def passed(self) -> bool:
        # Fail-closed: an empty gate is not a pass — a gate with no metrics
        # measured nothing, so it cannot certify the deliverable.
        return bool(self.metrics) and all(m.passed for m in self.metrics)

    @property
    def failures(self) -> list[MetricResult]:
        return [m for m in self.metrics if not m.passed]

    def summary(self) -> str:
        parts = [
            f"{m.name}={m.value:g}{m.unit} ({'ok' if m.passed else 'FAIL'})"
            for m in self.metrics
        ]
        verdict = "PASS" if self.passed else "FAIL"
        return f"{verdict} [{self.rig or 'no-rig'}] " + ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "rig": self.rig,
            "metrics": [m.to_dict() for m in self.metrics],
        }


class MeasuredGate:
    """Registry of metric checks evaluated against one context dict."""

    def __init__(self, rig: dict[str, Any] | None = None) -> None:
        self._checks: list[tuple[str, CheckFn]] = []
        self.rig = rig_fingerprint(rig) if rig else ""

    def register(self, name: str, fn: CheckFn) -> None:
        if any(n == name for n, _ in self._checks):
            raise ValidationError(
                f"duplicate check {name!r}", context={"check": name}
            )
        self._checks.append((name, fn))

    def run(self, context: dict[str, Any]) -> GateReport:
        report = GateReport(rig=self.rig)
        for _, fn in self._checks:
            report.metrics.extend(fn(context))
        return report


def rig_fingerprint(rig: dict[str, Any] | None = None, **params: Any) -> str:
    """Stable fingerprint of a comparison rig.

    Two measurements are comparable only when their rig fingerprints match
    (``[EVAL-01]``): seed, clock, viewport, model, capture flags — whatever
    the caller declares, hashed deterministically. Returns a short hex tag
    like ``rig:3fa2c1b0``; ``{}``/``None`` -> ``""`` (no declared rig).
    """
    merged: dict[str, Any] = dict(rig or {})
    merged.update(params)
    if not merged:
        return ""
    canonical = json.dumps(merged, sort_keys=True, default=str)
    return "rig:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
