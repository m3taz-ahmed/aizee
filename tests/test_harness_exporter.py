"""Tests for runtime.harness_exporter — skill install into agent harnesses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.harness_exporter import (
    harnesses,
    install_skill,
    resolve_harness_dir,
)


@pytest.fixture()
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    (root / "dirskill").mkdir(parents=True)
    (root / "dirskill" / "SKILL.md").write_text("---\nname: dirskill\n---\nbody", encoding="utf-8")
    (root / "dirskill" / "extra.txt").write_text("x", encoding="utf-8")
    (root / "flatskill.md").write_text("---\nname: flatskill\n---\nbody", encoding="utf-8")
    return root


def test_harnesses_resolve_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    hs = harnesses()
    assert hs["cursor"] == str(tmp_path / ".cursor" / "skills")
    assert set(hs) == {"agents", "cursor", "claude", "codex", "opencode"}


def test_resolve_harness_dir_path_and_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_harness_dir("path", str(tmp_path / "x")) == tmp_path / "x"
    monkeypatch.chdir(tmp_path)
    assert resolve_harness_dir("project") == tmp_path / ".agents" / "skills"
    with pytest.raises(ValueError):
        resolve_harness_dir("path", "")
    with pytest.raises(ValueError):
        resolve_harness_dir("bogus")


def test_install_dir_skill_recursive(skills_root: Path, tmp_path: Path) -> None:
    r = install_skill(skills_root, "dirskill", "path", str(tmp_path / "out"))
    assert r.ok
    assert set(r.files) == {"SKILL.md", "extra.txt"}
    assert (Path(r.dest) / "extra.txt").exists()


def test_install_flat_skill(skills_root: Path, tmp_path: Path) -> None:
    r = install_skill(skills_root, "flatskill", "path", str(tmp_path / "out"))
    assert r.ok and r.files == ["flatskill.md"]
    assert (tmp_path / "out" / "flatskill.md").exists()


def test_install_refuses_overwrite_then_force(skills_root: Path, tmp_path: Path) -> None:
    dest = str(tmp_path / "out")
    install_skill(skills_root, "dirskill", "path", dest)
    r = install_skill(skills_root, "dirskill", "path", dest)
    assert not r.ok and "force" in r.error
    r2 = install_skill(skills_root, "dirskill", "path", dest, force=True)
    assert r2.ok and r2.overwritten


def test_install_missing_skill_errors(skills_root: Path, tmp_path: Path) -> None:
    r = install_skill(skills_root, "nope", "path", str(tmp_path / "out"))
    assert not r.ok and "not found" in r.error


def test_main_list_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    from runtime.harness_exporter import main

    assert main(["--list"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "cursor" in out


def test_result_to_dict(skills_root: Path, tmp_path: Path) -> None:
    r = install_skill(skills_root, "flatskill", "path", str(tmp_path / "out"))
    d = r.to_dict()
    assert d["skill"] == "flatskill" and d["ok"] is True
    assert d["files"] == ["flatskill.md"]


def test_resolve_known_harness_uses_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert resolve_harness_dir("cursor") == tmp_path / ".cursor" / "skills"


def test_flat_skill_existing_target_requires_force(
    skills_root: Path, tmp_path: Path
) -> None:
    dest = str(tmp_path / "out")
    install_skill(skills_root, "flatskill", "path", dest)
    r = install_skill(skills_root, "flatskill", "path", dest)
    assert not r.ok and "force" in r.error


def test_main_installs_skill(
    skills_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from runtime.harness_exporter import main

    rc = main([
        "flatskill", "--harness", "path",
        "--dest", str(tmp_path / "o"),
        "--skills-root", str(skills_root),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_resolve_devin_project_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_harness_dir("devin") == tmp_path / ".devin" / "skills"


def _skill_with_fm(root: Path, name: str, desc: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\nbody", encoding="utf-8"
    )
    return d


class TestOpenAIBinding:
    def test_payload_shape(self) -> None:
        from runtime.harness_exporter import openai_binding

        b = openai_binding("my-cool_skill", "Does things.  Lots of them.")
        i = b["interface"]
        assert i["display_name"] == "My Cool Skill"
        assert i["default_prompt"] == "Use $my-cool_skill to help with this task."
        assert i["short_description"] == "Does things. Lots of them."

    def test_special_characters_yaml_safe(self) -> None:
        import yaml

        from runtime.harness_exporter import openai_binding

        desc = 'quotes "inside" & ampersand: colon — 100% legit <tag>'
        b = openai_binding("s", desc)
        dumped = yaml.safe_dump(b, sort_keys=False, allow_unicode=True)
        assert yaml.safe_load(dumped) == b

    def test_emit_writes_manifest(self, skills_root: Path) -> None:
        import yaml

        from runtime.harness_exporter import emit_openai_binding

        _skill_with_fm(skills_root, "vids", "Make videos fast")
        r = emit_openai_binding(skills_root, "vids")
        assert r.ok
        target = skills_root / "vids" / "agents" / "openai.yaml"
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert data["interface"]["display_name"] == "Vids"
        assert "$vids" in data["interface"]["default_prompt"]

    def test_emit_flat_skill_errors(self, skills_root: Path) -> None:
        from runtime.harness_exporter import emit_openai_binding

        r = emit_openai_binding(skills_root, "flatskill")
        assert not r.ok and "flat" in r.error

    def test_emit_missing_skill_errors(self, skills_root: Path) -> None:
        from runtime.harness_exporter import emit_openai_binding

        r = emit_openai_binding(skills_root, "ghost")
        assert not r.ok

    def test_emit_existing_requires_force(self, skills_root: Path) -> None:
        from runtime.harness_exporter import emit_openai_binding

        _skill_with_fm(skills_root, "vids", "d")
        emit_openai_binding(skills_root, "vids")
        r = emit_openai_binding(skills_root, "vids")
        assert not r.ok and "force" in r.error
        r2 = emit_openai_binding(skills_root, "vids", force=True)
        assert r2.ok and r2.overwritten

    def test_emit_deterministic(self, skills_root: Path) -> None:
        from runtime.harness_exporter import emit_openai_binding

        _skill_with_fm(skills_root, "vids", "Same desc")
        emit_openai_binding(skills_root, "vids")
        first = (skills_root / "vids" / "agents" / "openai.yaml").read_bytes()
        emit_openai_binding(skills_root, "vids", force=True)
        second = (skills_root / "vids" / "agents" / "openai.yaml").read_bytes()
        assert first == second


def test_emit_openai_no_frontmatter_description(skills_root: Path) -> None:
    from runtime.harness_exporter import emit_openai_binding

    r = emit_openai_binding(skills_root, "dirskill")  # fixture has no description
    assert r.ok
    target = skills_root / "dirskill" / "agents" / "openai.yaml"
    import yaml

    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["interface"]["display_name"] == "Dirskill"
    assert data["interface"]["short_description"] == ""


# ---------------------------------------------------------------------------
# detect_installed / install_auto (agents-matrix expansion)
# ---------------------------------------------------------------------------


def test_detect_installed_partial(tmp_path):
    from runtime.harness_exporter import detect_installed

    (tmp_path / ".cursor").mkdir()
    scan = detect_installed(home=tmp_path)
    assert "cursor" in scan["detected"]
    assert "agents" in scan["detected"]  # shared standard always present
    assert "claude" in scan["skipped"] and "codex" in scan["skipped"]


def test_detect_installed_empty_home(tmp_path):
    from runtime.harness_exporter import detect_installed

    scan = detect_installed(home=tmp_path)
    assert list(scan["detected"]) == ["agents"]
    assert set(scan["skipped"]) == {"cursor", "claude", "codex", "opencode"}


def test_install_auto(tmp_path):
    from runtime.harness_exporter import install_auto

    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    result = install_auto(skills, "demo", home=home)
    assert result["ok"] and result["installed"] == 2
    harnesses_hit = {r["harness"] for r in result["results"]}
    assert harnesses_hit == {"agents", "cursor"}
    assert (home / ".agents" / "skills" / "demo" / "SKILL.md").exists()
    assert (home / ".cursor" / "skills" / "demo" / "SKILL.md").exists()


def test_install_auto_missing_skill(tmp_path):
    from runtime.harness_exporter import install_auto

    home = tmp_path / "home"
    home.mkdir()
    skills = tmp_path / "skills"
    skills.mkdir()
    result = install_auto(skills, "ghost", home=home)
    assert not result["ok"] and result["installed"] == 0
