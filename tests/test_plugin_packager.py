"""Tests for runtime.plugin_packager - EGM-style plugin bundle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.plugin_packager import pack_plugin


@pytest.fixture()
def src_root(tmp_path: Path) -> Path:
    (tmp_path / "plugin.json").write_text(
        json.dumps({"name": "aizee", "version": "6.5.0", "description": "Sovereign AI engineering control plane.", "license": "MIT"}),
        encoding="utf-8")
    (tmp_path / "skills" / "sre").mkdir(parents=True)
    (tmp_path / "skills" / "sre" / "SKILL.md").write_text("---\nname: sre\n---\nbody", encoding="utf-8")
    (tmp_path / "resources" / "document_standards").mkdir(parents=True)
    (tmp_path / "resources" / "document_standards" / "zoom-out-standard.md").write_text("# std", encoding="utf-8")
    (tmp_path / "resources" / "goldfish_personas").mkdir(parents=True)
    (tmp_path / "resources" / "goldfish_personas" / "zoom_out.md").write_text("# persona", encoding="utf-8")
    return tmp_path


def test_pack_layout(src_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "bundle"
    r = pack_plugin(src_root, dest)
    assert r.ok, r.error
    for rel in ("plugin.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json",
                ".cursor-plugin/plugin.json", "skills/sre/SKILL.md",
                "resources/document_standards/zoom-out-standard.md",
                "agents/zoom_out.md"):
        assert (dest / rel).exists(), rel
    canonical = json.loads((dest / "plugin.json").read_text(encoding="utf-8"))
    assert canonical["name"] == "aizee"
    claude = json.loads((dest / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert claude["agents"] == "./agents/"


def test_pack_missing_plugin_json(tmp_path: Path) -> None:
    r = pack_plugin(tmp_path, tmp_path / "out")
    assert r.ok
    m = json.loads((tmp_path / "out" / "plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "aizee"


def test_pack_replaces_bundle_dest(src_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "b"
    dest.mkdir()
    (dest / "stale.txt").write_text("x", encoding="utf-8")
    (dest / "plugin.json").write_text("{}", encoding="utf-8")  # bundle-shaped
    r = pack_plugin(src_root, dest)
    assert r.ok
    assert not (dest / "stale.txt").exists()


def test_pack_refuses_arbitrary_nonempty_dest(src_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "precious"
    dest.mkdir()
    (dest / "keep.txt").write_text("x", encoding="utf-8")
    r = pack_plugin(src_root, dest)
    assert not r.ok
    assert "non-bundle" in r.error
    assert (dest / "keep.txt").exists()  # fail-closed: nothing deleted


def test_pack_refuses_file_dest(src_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "afile"
    dest.write_text("x", encoding="utf-8")
    r = pack_plugin(src_root, dest)
    assert not r.ok
    assert (dest).is_file()


def test_pack_result_to_dict(src_root: Path, tmp_path: Path) -> None:
    r = pack_plugin(src_root, tmp_path / "o")
    d = r.to_dict()
    assert d["ok"] and d["files"] == len(r.files) and d["error"] is None
    parent_file = tmp_path / "nonempty"
    parent_file.write_text("x", encoding="utf-8")
    bad = pack_plugin(src_root, parent_file / "x.txt")  # mkdir fails: parent is file
    assert bad.to_dict()["ok"] is False


def test_dest_is_bundle_shaped_file(tmp_path: Path) -> None:
    from runtime.plugin_packager import _dest_is_bundle_shaped

    p = tmp_path / "afile"
    p.write_text("x", encoding="utf-8")
    assert _dest_is_bundle_shaped(p) is False


def test_pack_clears_bundle_subdir(src_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "b2"
    (dest / "skills" / "old").mkdir(parents=True)
    (dest / "plugin.json").write_text("{}", encoding="utf-8")
    r = pack_plugin(src_root, dest)
    assert r.ok
    assert not (dest / "skills" / "old").exists()
    assert (dest / "skills" / "sre" / "SKILL.md").exists()


def test_pack_manifest_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "plugin.json").write_text("{bad json", encoding="utf-8")
    r = pack_plugin(tmp_path, tmp_path / "out")
    assert not r.ok and r.error


def test_pack_max_files_guard(src_root: Path, tmp_path: Path) -> None:
    r = pack_plugin(src_root, tmp_path / "o", max_files=2)
    assert not r.ok and "too large" in r.error
