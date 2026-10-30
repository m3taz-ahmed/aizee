"""Per-project config files (CCGS project.yaml adoption).

Two layered YAML files at the project root:

- ``aizee.yaml`` — committed, team-wide defaults
- ``aizee.local.yaml`` — gitignored, per-person overrides (wins)

``defaults.verify`` feeds ``Kernel.act(verify=...)`` when the caller does not
pass a dial explicitly — the project sets the floor, the caller can still
raise it. ``modes`` is a free-form process-weight block (mirroring CCGS
``modes.rigor`` as one front door over named knobs); ``system_overrides``
raises one named system's rigor above the project default. Unknown keys are
kept verbatim so workflows can read their own namespaced settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_TEAM_FILE = "aizee.yaml"
_LOCAL_FILE = "aizee.local.yaml"
_VALID_VERIFY = frozenset({"off", "final", "checkpoints", "strict"})


@dataclass(frozen=True)
class ProjectConfig:
    """Merged team + local project settings."""

    defaults: dict[str, Any] = field(default_factory=dict)
    modes: dict[str, Any] = field(default_factory=dict)
    system_overrides: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    loaded_from: tuple[str, ...] = ()

    @property
    def verify_default(self) -> str | None:
        """Project's default verification dial, or None when unset/invalid."""
        value = self.defaults.get("verify")
        if isinstance(value, str) and value in _VALID_VERIFY:
            return value
        return None

    @property
    def rigor(self) -> str:
        """Process-weight tier (minimal|standard|full); minimal by default."""
        value = self.modes.get("rigor", "minimal")
        return str(value) if isinstance(value, str) else "minimal"

    def rigor_for(self, system: str) -> str:
        """Rigor for one named system — system_overrides beats the default."""
        override = self.system_overrides.get(system)
        if isinstance(override, dict) and isinstance(override.get("rigor"), str):
            return str(override["rigor"])
        if isinstance(override, str):
            return override
        return self.rigor

    def to_dict(self) -> dict[str, Any]:
        return {
            "defaults": self.defaults,
            "modes": self.modes,
            "system_overrides": self.system_overrides,
            "extra": self.extra,
            "loaded_from": list(self.loaded_from),
        }


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge overlay onto base (per top-level section)."""
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def load_project_config(project_root: Path) -> ProjectConfig:
    """Read ``aizee.yaml`` + ``aizee.local.yaml``; missing files are empty."""
    merged: dict[str, Any] = {}
    loaded: list[str] = []
    for name in (_TEAM_FILE, _LOCAL_FILE):
        path = project_root / name
        if not path.is_file():
            continue
        merged = _merge(merged, _read_yaml(path))
        loaded.append(name)
    return ProjectConfig(
        defaults=dict(merged.get("defaults") or {}),
        modes=dict(merged.get("modes") or {}),
        system_overrides=dict(merged.get("system_overrides") or {}),
        extra={
            k: v
            for k, v in merged.items()
            if k not in {"defaults", "modes", "system_overrides"}
        },
        loaded_from=tuple(loaded),
    )
