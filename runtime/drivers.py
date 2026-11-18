"""Driver patches — declarative machine-fingerprint config overlays.

Adopted from ApkStart's ``apkstart-driver/1`` format (``src/drivers/*.json``):
a patch is a JSON file declaring ``match`` conditions on the machine profile
and a whitelisted ``effect`` on config keys. When the machine matches, the
effect applies — no code, no manual settings. Patches are auditable and can
be imported/exported between machines.

Format::

    {
      "format": "aizee-driver/1",
      "id": "low-ram",
      "name": "Low-RAM box",
      "enabled": true,
      "priority": 10,
      "match": {"platform": ["win32", "linux"], "ram_gb_max": 8, "gpu": "none"},
      "effect": {"embedder": "fastembed", "xdist_workers": 4}
    }

Match semantics: every declared key must match (AND); a scalar/list value is
equality/IN on the profile field; ``*_min``/``*_max`` suffixed keys are range
bounds on the numeric field named by the prefix. Unknown match keys fail
closed (patch never applies). Unknown effect keys are dropped — effects can
only set whitelisted config names.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.machine_profile import MachineProfile, detect

logger = logging.getLogger(__name__)

DRIVER_FORMAT = "aizee-driver/1"

# Effects may only touch these config surfaces — anything else is dropped.
EFFECT_WHITELIST = frozenset({"embedder", "xdist_workers", "gpu_enabled"})

# Scalar match keys compared against MachineProfile fields.
_SCALAR_KEYS = frozenset({"platform", "gpu"})
# Range match keys: "<field>_<min|max>" over numeric profile fields.
_RANGE_FIELDS = frozenset({"ram_gb", "cpu_count", "python"})


@dataclass(frozen=True)
class DriverPatch:
    """One loaded driver patch."""

    id: str
    name: str
    match: dict[str, Any]
    effect: dict[str, Any]
    enabled: bool = True
    priority: int = 10
    path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str = "") -> DriverPatch | None:
        if data.get("format") != DRIVER_FORMAT or not isinstance(data.get("match"), dict):
            return None
        raw_effect = data.get("effect") or {}
        effect = {k: v for k, v in raw_effect.items() if k in EFFECT_WHITELIST}
        dropped = set(raw_effect) - set(effect)
        if dropped:
            logger.warning("driver %s: dropped non-whitelisted effects %s", data.get("id"), dropped)
        try:
            priority = int(data.get("priority", 10))
        except (TypeError, ValueError):
            logger.warning("driver %s: invalid priority — skipped", data.get("id"))
            return None
        return cls(
            id=str(data.get("id") or Path(path).stem),
            name=str(data.get("name") or data.get("id") or ""),
            match=data["match"],
            effect=effect,
            enabled=bool(data.get("enabled", True)),
            priority=priority,
            path=path,
        )


def load_drivers(drivers_dir: Path) -> list[DriverPatch]:
    """Load every ``*.json`` patch in ``drivers_dir``, sorted by priority."""
    out: list[DriverPatch] = []
    if not drivers_dir.is_dir():
        return out
    for p in sorted(drivers_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("driver %s unreadable: %s", p.name, exc)
            continue
        patch = DriverPatch.from_dict(data, str(p)) if isinstance(data, dict) else None
        if patch is None:
            logger.warning("driver %s: not a %s patch — skipped", p.name, DRIVER_FORMAT)
            continue
        out.append(patch)
    return sorted(out, key=lambda d: d.priority)


def _scalar_matches(actual: Any, cond: Any) -> bool:
    if isinstance(cond, list):
        return bool(actual in cond)
    return bool(actual == cond)


def _version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(v).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _range_matches(actual: float | int | str, field_name: str, bound: str, cond: Any) -> bool:
    try:
        if field_name == "python":
            actual_v = _version_tuple(str(actual))
            cond_v = _version_tuple(str(cond))
            return actual_v >= cond_v if bound == "min" else actual_v <= cond_v
        return float(actual) >= float(cond) if bound == "min" else float(actual) <= float(cond)
    except (TypeError, ValueError):
        return False


def matches(patch: DriverPatch, profile: MachineProfile) -> bool:
    """True iff every declared condition holds. Unknown keys fail closed."""
    fields = profile.to_dict()
    for key, cond in patch.match.items():
        if key in _SCALAR_KEYS:
            if not _scalar_matches(fields.get(key), cond):
                return False
            continue
        if "_" in key:
            field_name, _, bound = key.rpartition("_")
            if field_name in _RANGE_FIELDS and bound in ("min", "max"):
                if not _range_matches(fields[field_name], field_name, bound, cond):
                    return False
                continue
        return False  # unknown key: fail closed
    return True


def active_patches(drivers_dir: Path, profile: MachineProfile | None = None) -> list[DriverPatch]:
    """Enabled patches whose match holds on ``profile`` (detect() if absent)."""
    profile = profile or detect()
    return [d for d in load_drivers(drivers_dir) if d.enabled and matches(d, profile)]


def active_effects(drivers_dir: Path, profile: MachineProfile | None = None) -> dict[str, Any]:
    """Merged effect dict of all active patches; higher priority wins."""
    merged: dict[str, Any] = {}
    for patch in active_patches(drivers_dir, profile):
        merged.update(patch.effect)
    return merged


def embedder_preference(drivers_dir: Path, profile: MachineProfile | None = None) -> str | None:
    """Driver-declared embedder override for ``auto`` mode, if any."""
    value = active_effects(drivers_dir, profile).get("embedder")
    if value in ("st", "sentence-transformers", "fastembed"):
        return "st" if value == "sentence-transformers" else str(value)
    return None


def xdist_workers_cap(drivers_dir: Path, profile: MachineProfile | None = None) -> int | None:
    """Driver-declared ceiling on pytest-xdist workers, if any."""
    value = active_effects(drivers_dir, profile).get("xdist_workers")
    try:
        cap = int(value)  # type: ignore[arg-type]
        return cap if cap >= 1 else None
    except (TypeError, ValueError):
        return None


def gpu_enabled(drivers_dir: Path, profile: MachineProfile | None = None) -> bool | None:
    """Driver-declared GPU toggle (``True``/``False``) or ``None`` if unset."""
    value = active_effects(drivers_dir, profile).get("gpu_enabled")
    return value if isinstance(value, bool) else None
