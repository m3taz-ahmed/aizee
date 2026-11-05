"""Tests for runtime.spec.review - Goldfish review planner."""

from __future__ import annotations

from runtime.spec.review import (
    ReviewPreset,
    ReviewScope,
    consolidate_findings,
    discover_semantic_split,
    parse_findings,
    plan_review,
)

DOC = """# Feature Spec

Some design text.

## Detailed Implementation Plan

- task A
- task B
"""

NO_PLAN = "# Spec\n\njust a spec\n"


def test_split_finds_boundary() -> None:
    s = discover_semantic_split(DOC)
    assert s.boundary_line == 5
    assert s.has_plan
    assert (s.feature_start, s.feature_end) == (1, 4)
    assert (s.detailed_start, s.detailed_end) == (5, 8)


def test_split_synonym_headers() -> None:
    for header in ("## Implementation Plan", "## Work Breakdown", "## Implementation Steps"):
        assert discover_semantic_split(f"# X\n\n{header}\n\n- t\n").boundary_line == 3


def test_split_absent() -> None:
    s = discover_semantic_split(NO_PLAN)
    assert not s.has_plan
    assert s.lines_for(ReviewScope.DETAILED) is None
    assert s.lines_for(ReviewScope.FEATURE) == (1, 3)


def test_plan_interactive_all_stages() -> None:
    plan = plan_review(DOC, ReviewPreset.INTERACTIVE)
    assert [s["stage"] for s in plan["stages"]] == [5, 6, 7, 8, 9]
    assert plan["interactive"] and not plan["consolidated"]
    critic = plan["stages"][2]
    assert critic["reviewers"] == ["design_critic", "structural", "style"]
    assert critic["lines"] == [1, 4]
    stage9 = plan["stages"][4]
    assert stage9["lines"] == [5, 8]
    assert plan["max_reaudits"] == 1


def test_plan_feature_spec_bypasses_split() -> None:
    plan = plan_review(DOC, ReviewPreset.FEATURE_SPEC)
    assert plan["split"]["boundary_line"] == 0
    assert [s["stage"] for s in plan["stages"]] == [5, 6, 7, 8]
    assert plan["stages"][2]["lines"] == [1, 8]


def test_plan_implementation_only_and_no_plan_doc() -> None:
    plan = plan_review(DOC, ReviewPreset.IMPLEMENTATION)
    assert [s["stage"] for s in plan["stages"]] == [9]
    plan2 = plan_review(NO_PLAN, ReviewPreset.IMPLEMENTATION)
    assert plan2["stages"] == []
    assert "Implementation Readiness" in plan2["skipped_stages"]


def test_parse_findings_and_consolidate() -> None:
    report = """Findings:
1. **Severity**: Blocker
   **Affected Scope**: `plan.md:12-20`
   **Finding**: missing rollback path
2. **Severity**: Nit
   wording unclear
"""
    findings = parse_findings(report, stage=7)
    assert [f["severity"] for f in findings] == ["blocker", "nit"]
    out = consolidate_findings({"critic_report.md": report})
    assert out["total_findings"] == 2
    assert out["by_severity"]["blocker"] == 1
    assert out["traceability_matrix"][0]["severity"] == "blocker"  # sorted first
    assert out["artifact"] == "consolidated_review_report.md"


def test_load_document_size_guard(tmp_path) -> None:
    from runtime.spec.review import load_document

    f = tmp_path / "d.md"
    f.write_text("x" * 100)
    assert len(load_document(f, max_bytes=200)) == 100
    with __import__("pytest").raises(ValueError):
        load_document(f, max_bytes=50)


def test_parse_findings_ignores_pre_severity_lines() -> None:
    report = "intro line\n- a bullet before any severity\n1. **Severity**: Major\n   detail\n"
    findings = parse_findings(report)
    assert len(findings) == 1 and findings[0]["severity"] == "major"


def test_parse_findings_text_cap() -> None:
    report = "1. **Severity**: Major\n- " + "x" * 5000 + "\n- another bullet\n"
    findings = parse_findings(report)
    assert len(findings) == 1
    assert len(findings[0]["text"]) < 5000 + 4000  # else-branch skipped the last append


def test_consolidate_unknown_artifact_stage() -> None:
    out = consolidate_findings({"custom_report.md": "1. **Severity**: Nit\n"})
    assert out["traceability_matrix"][0]["stage"] is None


def test_emoji_severity() -> None:
    assert parse_findings("- 🔴 outage risk\n- 🟢 typo") == [
        {"severity": "blocker", "stage": None, "text": "- 🔴 outage risk", "scope": ""},
        {"severity": "nit", "stage": None, "text": "- 🟢 typo", "scope": ""},
    ]
