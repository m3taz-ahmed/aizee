"""Tests for the invoke:user|auto skill taxonomy (mattpocock split)."""

from __future__ import annotations

from pathlib import Path

from runtime.rule_frontmatter import parse_frontmatter
from runtime.service_catalog import (
    ServiceCatalog,
    ServiceDescriptor,
    build_catalog_from_directory,
)


def _write(tmp_path: Path, name: str, fm: str) -> Path:
    f = tmp_path / f"{name}.md"
    f.write_text(f"---\n{fm}\n---\n\n# {name}\nbody\n", encoding="utf-8")
    return f


def test_parse_invoke_user(tmp_path: Path) -> None:
    fm, _ = parse_frontmatter("---\ninvoke: user\n---\nbody")
    assert fm.invoke == "user"


def test_parse_invoke_default_auto() -> None:
    fm, _ = parse_frontmatter("---\ntriggers: [x]\n---\nbody")
    assert fm.invoke == "auto"


def test_parse_invoke_unknown_falls_back() -> None:
    fm, _ = parse_frontmatter("---\ninvoke: sideways\n---\nbody")
    assert fm.invoke == "auto"


def test_parse_invoke_case_insensitive() -> None:
    fm, _ = parse_frontmatter("---\ninvoke: USER\n---\nbody")
    assert fm.invoke == "user"


def test_catalog_by_invoke_index() -> None:
    user = ServiceDescriptor(name="g", kind="skill", invoke="user")
    auto = ServiceDescriptor(name="a", kind="skill", invoke="auto")
    cat = ServiceCatalog([user, auto])
    assert [d.name for d in cat.by_invoke("user")] == ["g"]
    assert [d.name for d in cat.by_invoke("auto")] == ["a"]
    assert cat.by_invoke("USER") == cat.by_invoke("user")


def test_catalog_reads_invoke_from_frontmatter(tmp_path: Path) -> None:
    _write(tmp_path, "grill-me", 'triggers: [grill]\ninvoke: user')
    _write(tmp_path, "auto-skill", 'triggers: [auto thing]')
    cat = build_catalog_from_directory(tmp_path)
    names = {d.name: d.invoke for d in cat.by_kind("skill")}
    assert names == {"grill-me": "user", "auto-skill": "auto"}


def test_descriptor_default_invoke_auto() -> None:
    assert ServiceDescriptor(name="x", kind="skill").invoke == "auto"


def test_frontmatter_to_dict_includes_invoke() -> None:
    fm, _ = parse_frontmatter("---\ninvoke: user\n---\nbody")
    assert fm.to_dict()["invoke"] == "user"


# --- invoke:user must never be auto-loaded (taxonomy consumer) ---


def _write_skill(root: Path, name: str, fm: str) -> Path:
    skills = root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    f = skills / f"{name}.md"
    f.write_text(f"---\n{fm}\n---\n\n# {name}\nbody\n", encoding="utf-8")
    return f


def test_resolver_invoke_for(tmp_path: Path) -> None:
    from runtime.skill_resolver import SkillResolver

    _write_skill(tmp_path, "grill-me", "invoke: user")
    _write_skill(tmp_path, "auto-skill", "invoke: auto")
    r = SkillResolver(root=tmp_path)
    assert r.invoke_for("grill-me") == "user"
    assert r.invoke_for("auto-skill") == "auto"
    assert r.invoke_for("missing-skill") == "auto"  # unresolvable defaults to auto


def test_resolve_skills_excludes_invoke_user(tmp_path: Path) -> None:
    from runtime.persona import PersonaDetector
    from runtime.skill_resolver import SkillResolver

    _write_skill(tmp_path, "grill-me", "invoke: user")
    _write_skill(tmp_path, "auto-skill", "invoke: auto")
    det = PersonaDetector(skill_resolver=SkillResolver(root=tmp_path))
    out = det.resolve_skills([], lords=["grill-me", "auto-skill", "ghost-skill"])
    assert "grill-me" not in out  # user-invoked — never auto-resolved
    assert "auto-skill" in out
    assert "ghost-skill" not in out  # still requires an on-disk file here


def test_detect_multiple_excludes_invoke_user_lords(tmp_path: Path) -> None:
    from runtime.persona import PersonaDetector
    from runtime.skill_resolver import SkillResolver

    det_probe = PersonaDetector(skill_resolver=SkillResolver(root=tmp_path))
    lord = det_probe.list_lord_skills()[0]
    keyword = det_probe.LORD_SKILLS[lord][0]
    _write_skill(tmp_path, lord, "invoke: user")

    det = PersonaDetector(skill_resolver=SkillResolver(root=tmp_path))
    out = det.detect_multiple(keyword)
    assert lord not in out["lords"]

    # same skill with invoke:auto is auto-loadable again
    _write_skill(tmp_path, lord, "invoke: auto")
    det2 = PersonaDetector(skill_resolver=SkillResolver(root=tmp_path))
    out2 = det2.detect_multiple(keyword)
    assert lord in out2["lords"]
