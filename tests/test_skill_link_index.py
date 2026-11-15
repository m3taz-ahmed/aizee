"""Discovery index + windsurf target — vercel immutable-release pattern.

``aizee skill index`` emits a content-addressed index: every skill's sha256
is its release identity, so downstream harnesses can pin or drift-check a
skill without a version field.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from runtime.harness_exporter import (
    _PROJECT_DIRS,
    build_discovery_index,
    resolve_harness_dir,
)


@pytest.fixture()
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "flat-skill.md").write_text(
        "---\nname: flat-skill\ndescription: flat desc\n"
        "triggers: [alpha]\ninvoke: user\n---\n\nBody.\n",
        encoding="utf-8",
    )
    d = root / "dir-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: dir-skill\ndescription: dir desc\ntriggers: [beta]\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return root


def test_index_covers_flat_and_dir_layouts(skills_root: Path) -> None:
    index = build_discovery_index(skills_root)
    assert index["count"] == 2
    assert index["skills"]["flat-skill"]["file"] == "flat-skill.md"
    assert index["skills"]["dir-skill"]["file"] == "dir-skill/SKILL.md"


def test_index_entries_carry_metadata(skills_root: Path) -> None:
    entry = build_discovery_index(skills_root)["skills"]["flat-skill"]
    assert entry["description"] == "flat desc"
    assert entry["invoke"] == "user"
    assert "alpha" in entry["triggers"]


def test_index_hash_is_release_identity(skills_root: Path) -> None:
    index = build_discovery_index(skills_root)
    src = (skills_root / "flat-skill.md").read_bytes()
    assert index["skills"]["flat-skill"]["sha256"] == hashlib.sha256(src).hexdigest()
    # Immutable-release semantics: any edit changes the identity.
    (skills_root / "flat-skill.md").write_text("edited", encoding="utf-8")
    index2 = build_discovery_index(skills_root)
    assert index2["skills"]["flat-skill"]["sha256"] != index["skills"]["flat-skill"]["sha256"]


def test_index_survives_unreadable_file(
    skills_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(self: Path) -> bytes:
        raise OSError("denied")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    index = build_discovery_index(skills_root)
    assert index["skills"]["flat-skill"]["sha256"] == ""


def test_empty_root_yields_empty_index(tmp_path: Path) -> None:
    assert build_discovery_index(tmp_path / "nope") == {
        "kind": "skill",
        "count": 0,
        "skills": {},
    }


def test_windsurf_and_devin_project_targets() -> None:
    assert _PROJECT_DIRS["windsurf"] == ".windsurf/skills"
    assert _PROJECT_DIRS["devin"] == ".devin/skills"
    assert resolve_harness_dir("windsurf") == Path.cwd() / ".windsurf/skills"


def test_unknown_harness_still_rejected() -> None:
    with pytest.raises(ValueError, match="unknown harness"):
        resolve_harness_dir("bogus")
