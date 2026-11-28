"""Tests for aizee_mcp/skills_ext.py — skills-over-MCP extension."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from aizee_mcp._compat import FastMCP

pytestmark = pytest.mark.mcp

_ROOT = tempfile.mkdtemp(prefix="aizee_skext_test_")
os.environ["AIZEE_ROOT"] = _ROOT
ROOT = Path(_ROOT)

SKILL = ROOT / "skills" / "demo-skill"
(SKILL / "references").mkdir(parents=True)
(SKILL / "scripts").mkdir(parents=True)
(SKILL / "SKILL.md").write_text(
    '---\nname: demo-skill\ndescription: "Demo skill for tests"\n---\n# Demo\nBody text.\n',
    encoding="utf-8",
)
(SKILL / "references" / "deep.md").write_text("# Deep reference\n", encoding="utf-8")
(SKILL / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")

FLAT = ROOT / "skills" / "nofront"
FLAT.mkdir(parents=True)
(FLAT / "SKILL.md").write_text("# No frontmatter\nplain body\n", encoding="utf-8")

# Non-qualifying children: exercise the skip branches of _skill_dirs.
(ROOT / "skills" / "stray.txt").write_text("not a skill\n", encoding="utf-8")
(ROOT / "skills" / "incomplete").mkdir()
(ROOT / "skills" / "__pycache__").mkdir()
(ROOT / "skills" / "__pycache__" / "SKILL.md").write_text("# cached\n", encoding="utf-8")

from aizee_mcp.skills_ext import (  # noqa: E402
    _parse_frontmatter,
    register_skills_extension,
)
from aizee_mcp.tools.common import reset_state  # noqa: E402

_mcp = FastMCP("test-skills-ext")
register_skills_extension(_mcp)


def _fn(name: str):
    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    tool = _mcp._tool_manager.get_tool(name)
    assert tool is not None
    return tool.fn


def _resource_fn(uri_part: str):
    """Find a registered resource template function by uri fragment."""
    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    templates = getattr(_mcp, "_resource_manager", None)
    found = None
    for tmpl in getattr(templates, "_templates", {}).values():
        if uri_part in str(getattr(tmpl, "uri_template", "")):
            found = tmpl
            break
    assert found is not None, f"template {uri_part} not registered"
    return found.fn


# ---------------------------------------------------------------------------
# frontmatter parsing
# ---------------------------------------------------------------------------


def test_frontmatter_parsed() -> None:
    meta = _parse_frontmatter('---\nname: x\ndescription: "quoted"\n---\nbody\n')
    assert meta == {"name": "x", "description": "quoted"}


def test_frontmatter_absent() -> None:
    assert _parse_frontmatter("# no frontmatter\n") == {}


def test_frontmatter_skips_nested_and_list_lines() -> None:
    meta = _parse_frontmatter("---\nkey: v\n  nested: no\n- item: no\n---\n")
    assert meta == {"key": "v"}


# ---------------------------------------------------------------------------
# skills_list / skills_get
# ---------------------------------------------------------------------------


def test_skills_list() -> None:
    res = json.loads(_fn("skills_list")())
    assert res["ok"] and res["count"] == 2
    demo = next(s for s in res["skills"] if s["name"] == "demo-skill")
    assert demo["description"] == "Demo skill for tests"
    assert demo["skill_sha256"] and demo["files"] == 3


def test_skills_list_empty_root() -> None:
    empty = tempfile.mkdtemp(prefix="aizee_skext_empty_")
    os.environ["AIZEE_ROOT"] = empty
    reset_state()
    res = json.loads(_mcp._tool_manager.get_tool("skills_list").fn())
    assert res["ok"] and res["count"] == 0


def test_skills_get_ok() -> None:
    res = json.loads(_fn("skills_get")(name="demo-skill"))
    assert res["ok"] and res["frontmatter"]["name"] == "demo-skill"
    paths = [f["path"] for f in res["files"]]
    assert "references/deep.md" in paths and "scripts/run.py" in paths
    assert "# Demo" in res["content"]


def test_skills_get_unknown() -> None:
    res = json.loads(_fn("skills_get")(name="nope"))
    assert not res["ok"]


def test_skills_get_unsafe() -> None:
    res = json.loads(_fn("skills_get")(name="../x"))
    assert not res["ok"]


# ---------------------------------------------------------------------------
# skill:// resources
# ---------------------------------------------------------------------------


def test_resource_main() -> None:
    content = _resource_fn("SKILL.md")(name="demo-skill")
    assert "# Demo" in content


def test_resource_main_unknown_raises() -> None:
    with pytest.raises(ValueError):
        _resource_fn("SKILL.md")(name="nope")


def test_resource_nested() -> None:
    content = _resource_fn("{path}")(name="demo-skill", path="references/deep.md")
    assert "Deep reference" in content


def test_resource_nested_traversal_blocked() -> None:
    with pytest.raises(ValueError):
        _resource_fn("{path}")(name="demo-skill", path="../demo-skill/SKILL.md")


def test_resource_nested_missing_file() -> None:
    with pytest.raises(ValueError):
        _resource_fn("{path}")(name="demo-skill", path="references/absent.md")


def test_resource_nested_empty_path() -> None:
    with pytest.raises(ValueError):
        _resource_fn("{path}")(name="demo-skill", path="")


def test_resource_nested_unknown_skill() -> None:
    with pytest.raises(ValueError):
        _resource_fn("{path}")(name="nope", path="references/deep.md")


def test_resource_oversize_capped() -> None:
    big = SKILL / "references" / "big.md"
    big.write_text("x" * 200_001, encoding="utf-8")
    try:
        content = _resource_fn("{path}")(name="demo-skill", path="references/big.md")
        assert "exceeds" in content
    finally:
        big.unlink()


def test_frontmatter_unclosed() -> None:
    meta = _parse_frontmatter("---\nname: x\nbody without close\n")
    assert meta["name"] == "x"


def test_skill_dirs_listing_cap() -> None:
    from unittest.mock import patch

    from aizee_mcp import skills_ext

    os.environ["AIZEE_ROOT"] = _ROOT
    reset_state()
    with patch.object(skills_ext, "_MAX_LISTING", 1):
        res = json.loads(_mcp._tool_manager.get_tool("skills_list").fn())
    assert res["count"] == 1


def test_resolve_skill_symlink_escape_blocked() -> None:
    from unittest.mock import patch as _patch

    from aizee_mcp.skills_ext import _resolve_skill

    real_resolve = Path.resolve

    def fake_resolve(self, *a, **kw):
        if self.name == "linkskill":
            return Path(tempfile.mkdtemp())
        return real_resolve(self, *a, **kw)

    with _patch.object(Path, "resolve", fake_resolve):
        assert _resolve_skill(ROOT, "linkskill") is None


def test_resolve_nested_resolve_escape() -> None:
    from unittest.mock import patch as _patch

    from aizee_mcp.skills_ext import _resolve_nested

    base = SKILL.resolve()
    real_resolve = Path.resolve

    def fake_resolve(self, *a, **kw):
        if self.name == "deep.md":
            return Path(tempfile.mkdtemp()) / "deep.md"
        return real_resolve(self, *a, **kw)

    with _patch.object(Path, "resolve", fake_resolve):
        assert _resolve_nested(base, "references/deep.md") is None


def test_manifest_cap() -> None:
    from unittest.mock import patch

    from aizee_mcp import skills_ext
    from aizee_mcp.skills_ext import _manifest

    with patch.object(skills_ext, "_MAX_MANIFEST_ENTRIES", 1):
        entries = _manifest(SKILL)
    assert len(entries) == 1


def test_manifest_stat_oserror() -> None:
    # Deterministic cross-platform: patch rglob to a precomputed list (no
    # internal stat calls — Linux pathlib stats during rglob iteration) and
    # is_file to True, so the ONLY stat that runs is the one inside the
    # manifest try-block — where the injected OSError must be swallowed.
    from unittest.mock import patch as _patch

    from aizee_mcp.skills_ext import _manifest

    real_stat = Path.stat
    precomputed = sorted(SKILL.rglob("*"))

    def fake_stat(self, *a, **kw):
        if self.name == "deep.md":
            raise OSError("gone")
        return real_stat(self, *a, **kw)

    with (
        _patch.object(Path, "rglob", lambda self, pat: iter(precomputed)),
        _patch.object(Path, "is_file", lambda self: True),
        _patch.object(Path, "stat", fake_stat),
    ):
        entries = _manifest(SKILL)
    assert all(e["path"] != "references/deep.md" for e in entries)
    assert any(e["path"] == "SKILL.md" for e in entries)
