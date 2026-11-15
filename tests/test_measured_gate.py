"""Tests for runtime.measured_gate."""

from __future__ import annotations

import pytest

from runtime.measured_gate import (
    GateReport,
    MeasuredGate,
    MetricResult,
    rig_fingerprint,
)
from runtime.schemas import ValidationError


def test_metric_max_direction() -> None:
    assert MetricResult("lufs", -14.0, threshold=-13.0, direction="max").passed
    assert not MetricResult("lufs", -10.0, threshold=-13.0, direction="max").passed


def test_metric_min_direction() -> None:
    assert MetricResult("ssim", 0.95, threshold=0.9, direction="min").passed
    assert not MetricResult("ssim", 0.7, threshold=0.9, direction="min").passed


def test_informational_metric_never_fails() -> None:
    assert MetricResult("duration", 15.0).passed


def test_bad_direction_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricResult("x", 1.0, direction="sideways")


def test_gate_runs_registered_checks() -> None:
    gate = MeasuredGate()
    gate.register(
        "audio",
        lambda ctx: [
            MetricResult("peak_dbfs", ctx["peak"], threshold=-3.0, direction="max")
        ],
    )
    gate.register(
        "frames",
        lambda ctx: [
            MetricResult("flat_frames", ctx["flats"], threshold=0, direction="max")
        ],
    )
    report = gate.run({"peak": -8.0, "flats": 0})
    assert report.passed
    assert len(report.metrics) == 2


def test_gate_report_failures() -> None:
    gate = MeasuredGate()
    gate.register(
        "seam", lambda ctx: [MetricResult("ssim", 0.5, threshold=0.9, direction="min")]
    )
    report = gate.run({})
    assert not report.passed
    assert [m.name for m in report.failures] == ["ssim"]
    assert "FAIL" in report.summary()


def test_duplicate_check_rejected() -> None:
    gate = MeasuredGate()
    gate.register("a", lambda ctx: [])
    with pytest.raises(ValidationError):
        gate.register("a", lambda ctx: [])


def test_gate_report_serialization() -> None:
    report = GateReport(
        metrics=[MetricResult("x", 1.0, threshold=2.0, evidence="tool/out.json")],
        rig="rig:abc123",
    )
    d = report.to_dict()
    assert d["passed"] and d["rig"] == "rig:abc123"
    assert d["metrics"][0]["evidence"] == "tool/out.json"


def test_rig_fingerprint_deterministic() -> None:
    a = rig_fingerprint({"seed": 7, "viewport": "360x800"})
    b = rig_fingerprint({"viewport": "360x800", "seed": 7})
    assert a == b
    assert a.startswith("rig:")


def test_rig_fingerprint_distinguishes_rigs() -> None:
    assert rig_fingerprint({"seed": 7}) != rig_fingerprint({"seed": 8})
    assert rig_fingerprint() == ""


def test_gate_carries_rig() -> None:
    gate = MeasuredGate(rig={"seed": 1, "clock": "virtual"})
    report = gate.run({})
    assert report.rig == rig_fingerprint({"clock": "virtual", "seed": 1})


def test_empty_gate_is_not_a_pass() -> None:
    """Fail-closed: a gate that measured nothing cannot certify (S1)."""
    report = MeasuredGate().run({})
    assert report.passed is False
    assert report.metrics == []
