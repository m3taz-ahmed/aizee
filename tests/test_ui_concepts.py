"""Tests for runtime/ui_concepts.py — schema-driven control panes."""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from runtime.ui_concepts import frontmatter_concepts, model_concepts, pane_for


class _Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class _Settings(BaseModel):
    name: str = Field(description="Display name")
    retries: int = Field(default=3, ge=0, le=10)
    ratio: float = 0.5
    enabled: bool = True
    color: _Color = _Color.RED
    mode: Literal["fast", "slow"] = "fast"
    tags: list[str] = []
    meta: dict = {}
    out: Path | None = None


def test_model_concepts_types() -> None:
    pane = model_concepts(_Settings)
    by_key = {c["key"]: c for c in pane["controls"]}
    assert pane["kind"] == "concepts"
    assert by_key["name"]["control"] == "text"
    assert by_key["enabled"]["control"] == "boolean"
    assert by_key["retries"]["control"] in ("slider", "number")
    assert by_key["color"]["control"] == "enum"
    assert set(by_key["color"]["options"]) == {"red", "blue"}
    assert by_key["mode"]["control"] == "enum"
    assert set(by_key["mode"]["options"]) == {"fast", "slow"}
    assert by_key["tags"]["control"] == "list"
    assert by_key["meta"]["control"] == "json"
    assert by_key["out"]["control"] == "path"


def test_model_concepts_defaults_and_labels() -> None:
    pane = model_concepts(_Settings, title="Kernel")
    by_key = {c["key"]: c for c in pane["controls"]}
    assert pane["title"] == "Kernel"
    assert by_key["retries"]["default"] == 3
    assert by_key["name"]["description"] == "Display name"
    assert by_key["retries"]["label"] == "retries"


def test_frontmatter_concepts(tmp_path: Path) -> None:
    md = tmp_path / "skill.md"
    md.write_text(
        "---\nname: demo\ncount: 3\nenabled: true\ntags: [a, b]\n---\nbody\n",
        encoding="utf-8",
    )
    pane = frontmatter_concepts(md)
    by_key = {c["key"]: c for c in pane["controls"]}
    assert pane["title"] == "demo"
    assert by_key["count"]["control"] == "number"
    assert by_key["enabled"]["control"] == "boolean"
    assert by_key["tags"]["control"] == "list"
    assert by_key["name"]["default"] == "demo"


def test_frontmatter_no_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "plain.md"
    md.write_text("no frontmatter\n", encoding="utf-8")
    pane = frontmatter_concepts(md)
    assert pane["controls"] == []


def test_pane_for_explicit_schema() -> None:
    pane = pane_for(
        "Prefs",
        {
            "level": {"type": "slider", "range": [0, 10], "default": 5},
            "kind": {"type": "enum", "options": ["a", "b"]},
            "note": {"type": "text", "description": "free text"},
        },
    )
    by_key = {c["key"]: c for c in pane["controls"]}
    assert by_key["level"]["control"] == "slider"
    assert by_key["level"]["range"] == [0, 10]
    assert by_key["kind"]["options"] == ["a", "b"]
    assert by_key["note"]["description"] == "free text"


def test_pane_for_scalar_shorthand() -> None:
    pane = pane_for("P", {"x": 5})
    assert pane["controls"][0]["control"] == "number"
    assert pane["controls"][0]["default"] == 5


def test_pydantic_basename_collision_guard() -> None:
    # pane should not raise when fields carry exotic extras
    class _M(BaseModel):
        v: int = Field(default=1, json_schema_extra={"control": "slider", "range": [0, 3]})

    pane = model_concepts(_M)
    assert pane["controls"][0]["control"] == "slider"
    assert pane["controls"][0]["range"] == [0, 3]


def test_pane_control_only_type_names() -> None:
    """REGRESSION: type:color/textarea degraded to text — they name controls."""
    pane = pane_for(
        "p",
        {
            "c": {"type": "color"},
            "t": {"type": "textarea"},
            "n": {"type": "number", "range": [0, 5]},
        },
    )
    by = {c["key"]: c for c in pane["controls"]}
    assert by["c"]["control"] == "color"
    assert by["t"]["control"] == "textarea"
    assert by["n"]["control"] == "slider"  # type-bearing names unchanged


def test_pane_options_list_maps_to_enum() -> None:
    pane = pane_for("p", {"c": {"options": ["x", "y"]}})
    assert pane["controls"][0]["control"] == "enum"
    assert pane["controls"][0]["options"] == ["x", "y"]


def test_model_concepts_ge_le_range() -> None:
    """v1-style field objects expose ge/le attrs -> range hint."""
    from types import SimpleNamespace

    model = SimpleNamespace(
        model_fields={
            "n": SimpleNamespace(
                annotation=int,
                json_schema_extra=None,
                ge=0,
                le=10,
                title=None,
                description="",
                is_required=None,
                default=5,
            )
        }
    )
    pane = model_concepts(model)
    assert pane["controls"][0]["range"] == [0, 10]


def test_frontmatter_non_dict_yaml(tmp_path: Path) -> None:
    md = tmp_path / "l.md"
    md.write_text("---\n- a\n- b\n---\nbody\n", encoding="utf-8")
    pane = frontmatter_concepts(md)
    assert pane["controls"] == []
