"""Sensitive-data vault (browser-use ``sensitive_data`` adoption).

Credentials are *injected at call time*, never embedded in prompts or
action args: the agent references ``{NAME}`` placeholders, the executor
swaps real values in at the boundary, and anything that reaches audit,
logs, or policy gates is masked first.

Usage::

    vault = SensitiveVault({"GITHUB_TOKEN": "ghp_..."})
    url = vault.inject("https://api.github.com?key={GITHUB_TOKEN}")
    safe_args = vault.mask_obj({"note": "token is {GITHUB_TOKEN}"})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]{0,40})\}")


@dataclass
class SensitiveVault:
    """Holds named secrets; injects at call time, masks at audit time."""

    values: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: object) -> SensitiveVault:
        """Normalize ``kernel.act(sensitive_data={...})`` payloads."""
        if not isinstance(mapping, dict):
            return cls({})
        return cls({str(k): str(v) for k, v in mapping.items()})

    def inject(self, text: str) -> str:
        """Replace ``{NAME}`` placeholders with real values."""
        return _PLACEHOLDER.sub(lambda m: self.values.get(m.group(1), m.group(0)), text)

    def mask(self, text: str) -> str:
        """Replace *real values* (and unresolved placeholders) with tokens."""
        for name, value in self.values.items():
            if value and value in text:
                text = text.replace(value, f"[SENSITIVE:{name}]")
        return _PLACEHOLDER.sub(
            lambda m: f"[SENSITIVE:{m.group(1)}]" if m.group(1) in self.values else m.group(0),
            text,
        )

    def mask_dict(self, obj: dict[str, object]) -> dict[str, object]:
        """Mask a kwargs dict, preserving the dict type for callers."""
        return {k: self.mask_obj(v) for k, v in obj.items()}

    def mask_obj(self, obj: object) -> object:
        """Recursively mask strings inside dicts/lists."""
        if isinstance(obj, str):
            return self.mask(obj)
        if isinstance(obj, dict):
            return self.mask_dict(obj)
        if isinstance(obj, (list, tuple)):
            masked = [self.mask_obj(v) for v in obj]
            return type(obj)(masked) if isinstance(obj, tuple) else masked
        return obj
