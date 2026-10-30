"""Tests for runtime/project_config.py — aizee.yaml + aizee.local.yaml layering."""

from __future__ import annotations

from pathlib import Path

from runtime.project_config import load_project_config


class TestLoadProjectConfig:
    def test_missing_files_gives_empty_defaults(self, tmp_path: Path):
        cfg = load_project_config(tmp_path)
        assert cfg.verify_default is None
        assert cfg.rigor == "minimal"
        assert cfg.loaded_from == ()

    def test_team_file_loads(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text(
            "defaults:\n  verify: checkpoints\nmodes:\n  rigor: standard\n"
        )
        cfg = load_project_config(tmp_path)
        assert cfg.verify_default == "checkpoints"
        assert cfg.rigor == "standard"
        assert cfg.loaded_from == ("aizee.yaml",)

    def test_local_overrides_team(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text(
            "defaults:\n  verify: checkpoints\nmodes:\n  rigor: standard\n"
        )
        (tmp_path / "aizee.local.yaml").write_text(
            "defaults:\n  verify: strict\n"
        )
        cfg = load_project_config(tmp_path)
        assert cfg.verify_default == "strict"
        assert cfg.rigor == "standard"  # untouched section survives merge
        assert cfg.loaded_from == ("aizee.yaml", "aizee.local.yaml")

    def test_invalid_verify_returns_none(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text("defaults:\n  verify: banana\n")
        assert load_project_config(tmp_path).verify_default is None

    def test_system_overrides(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text(
            "modes:\n  rigor: minimal\n"
            "system_overrides:\n  combat:\n    rigor: full\n"
        )
        cfg = load_project_config(tmp_path)
        assert cfg.rigor_for("combat") == "full"
        assert cfg.rigor_for("ui") == "minimal"

    def test_extra_namespaced_keys_kept(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text("engine:\n  name: Godot\n  version: '4.5'\n")
        cfg = load_project_config(tmp_path)
        assert cfg.extra["engine"]["name"] == "Godot"

    def test_malformed_yaml_is_empty(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text("{{{{ not yaml")
        cfg = load_project_config(tmp_path)
        assert cfg.loaded_from == ("aizee.yaml",)
        assert cfg.defaults == {}

    def test_system_override_bare_string(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text(
            "modes:\n  rigor: minimal\nsystem_overrides:\n  combat: full\n"
        )
        cfg = load_project_config(tmp_path)
        assert cfg.rigor_for("combat") == "full"

    def test_system_override_dict_without_rigor(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text(
            "modes:\n  rigor: standard\nsystem_overrides:\n  combat:\n    note: x\n"
        )
        cfg = load_project_config(tmp_path)
        assert cfg.rigor_for("combat") == "standard"

    def test_to_dict_roundtrip(self, tmp_path: Path):
        (tmp_path / "aizee.yaml").write_text("defaults:\n  verify: strict\n")
        data = load_project_config(tmp_path).to_dict()
        assert data["defaults"]["verify"] == "strict"
        assert data["loaded_from"] == ["aizee.yaml"]
