"""Config operations — masked ``show`` and ``apply --check`` dry-run.

Adopted from HKUDS/DeepTutor: ``config show`` redacts secrets before
display, and ``config apply <file> --check`` validates a settings file
against the schema without writing — operators can review a config change
before it lands.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from runtime.schemas import ValidationError
from runtime.settings import SettingsManager, _deep_merge, _validate_section, default_settings

_SECRET_RE = re.compile(r"key|secret|token|password|credential", re.IGNORECASE)
MASK = "********"


def show_config(
    mgr: SettingsManager,
    section: str | None = None,
    redact: bool = True,
) -> dict[str, Any]:
    """Return settings with secret-looking values masked."""
    data = {section: mgr.get_section(section)} if section else mgr.get_all()
    return _redact(data) if redact else data


def apply_config(
    mgr: SettingsManager,
    path: Path,
    check: bool = False,
) -> dict[str, Any]:
    """Validate (and optionally apply) a settings file.

    ``check=True`` is a pure dry-run: validates every section and returns the
    diff that WOULD be applied, without touching ``settings.json``.
    """
    if not path.exists():
        raise ValidationError(f"config file not found: {path}", context={"path": str(path)})
    raw = _load_file(path)
    if not isinstance(raw, dict):
        raise ValidationError("config file must be a mapping of section -> data")

    known_sections = set(default_settings().keys())
    errors: list[str] = []
    changes: dict[str, dict[str, Any]] = {}
    for section, data in raw.items():
        if section not in known_sections:
            errors.append(f"unknown section {section!r}")
            continue
        if not isinstance(data, dict):
            errors.append(f"section {section!r} must be an object")
            continue
        try:
            _validate_section(section, data)
        except ValidationError as exc:
            errors.append(f"{section}: {exc}")
            continue
        current = mgr.get_section(section)
        changes[section] = _diff(current, _deep_merge(current, data))

    result: dict[str, Any] = {
        "ok": not errors,
        "check_only": check,
        "sections": sorted(changes),
        "changes": changes,
        "errors": errors,
    }
    if errors or check:
        return result
    for section, data in raw.items():
        mgr.update_section(section, data)
    result["applied"] = sorted(raw)
    return result


def _load_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def _redact(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: (MASK if _SECRET_RE.search(str(k)) and isinstance(v, str) and v else _redact(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact(v) for v in data]
    return data


def _diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in new.items():
        if key not in old:
            out[key] = {"added": value}
        elif isinstance(value, dict) and isinstance(old[key], dict):
            nested = _diff(old[key], value)
            if nested:
                out[key] = nested
        elif value != old[key]:
            out[key] = {"from": old[key], "to": value}
    for key in old:
        if key not in new:
            out[key] = {"removed": True}
    return out
