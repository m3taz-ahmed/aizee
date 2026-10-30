"""Tests for runtime/skill_lint.py — description lint, collisions, rubric, contracts."""

from __future__ import annotations

from pathlib import Path

from runtime.skill_lint import (
    lint_contract_text,
    lint_description,
    lint_rubric,
    load_skill,
    load_skills,
    run_lint,
)

_FLAT = "---\nname: {name}\ndescription: {desc}\ntriggers:\n  - {trig}\n---\n{body}"
_CONTRACT_OK = """# x — Handoff Contract

## Inputs Required
stuff

## Outputs Produced
stuff

## Immutability Rules
stuff

## Hard Constraints (Never Violate)
stuff
"""


def _flat_skill(root: Path, name: str, body: str = "[RULES]\n1. [REQ] R.\n") -> Path:
    skills = root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    path = skills / f"{name}.md"
    path.write_text(
        _FLAT.format(
            name=name,
            desc=f"{name} does useful things — Use when testing.",
            trig=name,
            body=body,
        ),
        encoding="utf-8",
    )
    return path


def _dir_skill(root: Path, name: str, contract: str | None = None) -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        _FLAT.format(
            name=name,
            desc=f"{name} does useful things — Use when testing.",
            trig=name,
            body="[RULES]\n1. [REQ] A.\n2. [REQ] B.\n3. [PROHIBIT] C.\n",
        ),
        encoding="utf-8",
    )
    if contract is not None:
        (skill_dir / "CONTRACT.md").write_text(contract, encoding="utf-8")
    return path


class TestLintDescription:
    def test_ok_skill_has_no_issues(self, tmp_path: Path):
        meta = load_skill(_flat_skill(tmp_path, "alpha"), tmp_path)
        assert lint_description(meta) == []

    def test_short_description_flagged(self, tmp_path: Path):
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "weak.md").write_text("---\nname: weak\ndescription: short\n---\n")
        meta = load_skill(skills / "weak.md", tmp_path)
        assert any("too short" in i for i in lint_description(meta))


class TestContractLint:
    def test_valid_contract_passes(self):
        assert lint_contract_text(_CONTRACT_OK) == ()

    def test_missing_sections_flagged(self):
        issues = lint_contract_text("## Inputs Required\nx\n")
        assert len(issues) == 3
        assert any("Outputs Produced" in i for i in issues)

    def test_dir_skill_loads_contract_issues(self, tmp_path: Path):
        meta = load_skill(_dir_skill(tmp_path, "beta", "## Inputs Required\n"), tmp_path)
        assert len(meta.contract_issues) == 3

    def test_no_contract_no_issues(self, tmp_path: Path):
        meta = load_skill(_dir_skill(tmp_path, "gamma"), tmp_path)
        assert meta.contract_issues == ()


class TestLintRubric:
    def test_lord_with_enough_rules_passes(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "lordy"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: lordy\ncategory: lord\ndescription: d " + "x" * 40 + "\ntriggers:\n  - lordy\n---\n"
            "[RULES]\n1. [REQ] A.\n2. [REQ] B.\n3. [REQ] C.\n",
            encoding="utf-8",
        )
        meta = load_skill(skill_dir / "SKILL.md", tmp_path)
        assert meta.category == "lord"
        assert meta.rule_count == 3
        assert lint_rubric(meta) == []

    def test_lord_below_min_rules_flagged(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "weaklord"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: weaklord\ncategory: lord\ndescription: d " + "x" * 40 + "\ntriggers:\n  - weaklord\n---\n"
            "[RULES]\n1. [REQ] only one.\n",
            encoding="utf-8",
        )
        meta = load_skill(skill_dir / "SKILL.md", tmp_path)
        assert any("min" in i for i in lint_rubric(meta))

    def test_unknown_category_flagged(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "odd"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: odd\ncategory: wizard\ndescription: d " + "x" * 40 + "\ntriggers:\n  - odd\n---\n",
            encoding="utf-8",
        )
        meta = load_skill(skill_dir / "SKILL.md", tmp_path)
        assert any("unknown category" in i for i in lint_rubric(meta))

    def test_run_lint_includes_rubric_and_contract(self, tmp_path: Path):
        _dir_skill(tmp_path, "broken", "## Inputs Required\n")
        report = run_lint(tmp_path)
        assert not report["ok"]
        assert "broken" in report["issues"]
        assert any("contract missing" in i for i in report["issues"]["broken"])

    def test_load_skills_ignores_templates_dir_files(self, tmp_path: Path):
        _dir_skill(tmp_path, "clean")
        metas = load_skills(tmp_path)
        assert len(metas) == 1
        assert metas[0].name == "clean"
