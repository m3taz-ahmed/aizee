"""Schema-driven UI concepts (Theatre.js prop-types + OpenToonz params).

Theatre.js studio never hand-writes editors: a prop declares its type
(`t.number({range})`, `t.string()`, `t.enum`) and the studio renders the
right control — slider, text field, dropdown — automatically. This
module gives aiZee the same contract: declare a prop schema once, get a
control descriptor any frontend (dashboard, CLI wizard, MCP UI) can
render consistently.

Two sources:

- **Pydantic models** — `model_concepts(Model)` walks `model_fields` and
  maps annotations + `Field(json_schema_extra=)` hints to controls.
- **YAML frontmatter** — `frontmatter_concepts(path)` turns skill/rule
  metadata into editable controls (for the settings panes).

Output is a *data* pane (no HTML) — renderers stay free.

Usage::

    pane = model_concepts(SettingsModel, title="Kernel Settings")
    pane["controls"]  # [{"key": "x", "control": "slider", "range": [0,1], ...}]
"""

from __future__ import annotations

import enum
import json
import re
import types
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import yaml

# Control vocabulary — renderers map these to widgets.
CONTROLS = frozenset(
    {"number", "slider", "text", "textarea", "boolean", "enum", "list", "json", "color", "path"}
)


def _control_for(annotation: Any, hints: dict[str, Any]) -> dict[str, Any]:
    """Map a type + hints to a control descriptor (Theatre t.* mapping)."""
    if "control" in hints:
        base: dict[str, Any] = {"control": hints["control"]}
    elif isinstance(hints.get("options"), (list, tuple)):
        return {"control": "enum", "options": list(hints["options"])}
    elif _is_bool(annotation):
        base = {"control": "boolean"}
    elif isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return {"control": "enum", "options": [e.value for e in annotation]}
    elif _is_literal(annotation):
        return {"control": "enum", "options": list(get_args(annotation))}
    elif _is_number(annotation):
        base = {"control": "slider" if "range" in hints else "number"}
    elif _is_seq(annotation):
        base = {"control": "list"}
    elif _is_mapping(annotation):
        base = {"control": "json"}
    elif annotation is Path or hints.get("format") == "path":
        base = {"control": "path"}
    else:
        base = {"control": "text"}
    for hint_key in ("range", "step", "options", "placeholder", "format", "min", "max"):
        if hint_key in hints:
            base[hint_key] = hints[hint_key]
    return base


def _is_bool(a: Any) -> bool:
    return a is bool


def _is_number(a: Any) -> bool:
    return a in (int, float)



def _is_literal(a: Any) -> bool:
    return get_origin(a) is Literal


def _is_seq(a: Any) -> bool:
    return get_origin(a) in (list, tuple, set, frozenset) or a in (list, tuple, set)


def _is_mapping(a: Any) -> bool:
    return get_origin(a) is dict or a is dict


def _unwrap(annotation: Any) -> Any:
    """Unwrap Optional[X]/Union[X,None] to X for control selection."""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return args[0] if len(args) == 1 else annotation
    return annotation


def model_concepts(model: Any, *, title: str | None = None) -> dict[str, Any]:
    """Pydantic model -> control pane. Supports v2 ``model_fields`` + v1."""
    fields = getattr(model, "model_fields", None) or getattr(model, "__fields__", {})
    controls: list[dict[str, Any]] = []
    for name, f in fields.items():
        annotation = _unwrap(getattr(f, "annotation", Any))
        hints: dict[str, Any] = dict(getattr(f, "json_schema_extra", None) or {})
        if getattr(f, "ge", None) is not None or getattr(f, "le", None) is not None:
            hints.setdefault("range", [f.ge, f.le])
        ctl = _control_for(annotation, hints)
        ctl.update(
            {
                "key": name,
                "label": str(getattr(f, "title", None) or name.replace("_", " ")),
                "description": str(getattr(f, "description", "") or ""),
                "required": bool(getattr(f, "is_required", lambda: False)())
                if callable(getattr(f, "is_required", None))
                else False,
                "default": _default_of(f),
            }
        )
        controls.append(ctl)
    return {
        "kind": "concepts",
        "title": title or getattr(model, "__name__", "pane"),
        "controls": controls,
    }


def _default_of(f: Any) -> Any:
    d = getattr(f, "default", None)
    try:
        json.dumps(d)
        return d
    except (TypeError, ValueError):
        return None


def frontmatter_concepts(path: Path | str) -> dict[str, Any]:
    """YAML frontmatter of a md file -> editable control pane."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    data = yaml.safe_load(m.group(1)) if m else {}
    if not isinstance(data, dict):
        data = {}
    controls = []
    for key, value in data.items():
        ctl = _control_for(type(value), {})
        ctl.update({"key": key, "label": key.replace("_", " "), "default": value})
        controls.append(ctl)
    return {
        "kind": "concepts",
        "title": str(data.get("name") or data.get("title") or Path(path).stem),
        "source": str(path),
        "controls": controls,
    }


def pane_for(title: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Explicit ``{key: {"type": ..., "options"/"range": ...}}`` -> pane."""
    controls = []
    for key, spec in schema.items():
        if not isinstance(spec, dict):
            spec = {"type": type(spec).__name__, "default": spec}
        declared = spec.get("type")
        hints = {k: v for k, v in spec.items() if k != "type"}
        # Control-vocabulary names that have no scalar-type meaning map
        # straight through ({"type": "color"} -> color picker, not a plain
        # text field); type-bearing names keep the annotation path.
        if isinstance(declared, str) and declared in CONTROLS and _ann(declared) is str:
            hints.setdefault("control", declared)
        annotation = type(spec.get("default")) if declared is None else _ann(declared)
        ctl = _control_for(annotation, hints)
        ctl.update(
            {
                "key": key,
                "label": spec.get("label", key.replace("_", " ")),
                "description": spec.get("description", ""),
                "default": spec.get("default"),
            }
        )
        controls.append(ctl)
    return {"kind": "concepts", "title": title, "controls": controls}


def _ann(type_name: Any) -> Any:
    return {
        "number": float,
        "slider": float,
        "boolean": bool,
        "list": list,
        "json": dict,
        "enum": str,
        "select": str,
        "path": Path,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "str": str,
    }.get(str(type_name), str)
