"""Offline model catalog (vercel-labs/modelsdotdev-python adoption).

models.dev publishes an api.json of providers→models (cost, context,
capabilities). We ship a **version-locked snapshot** at
``resources/models_catalog.json`` — same philosophy as version-locked
tech-stack refs — so `aizee models` can show catalog data without network.

``load_catalog`` reads the snapshot; ``enrich_models`` merges the routing
catalog (``model_router._MODELS``) with catalog metadata for a unified view.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_FILE = "resources/models_catalog.json"


@dataclass(frozen=True)
class CatalogEntry:
    provider: str
    model_id: str
    name: str
    context: int | None
    output: int | None
    input_cost: float | None
    output_cost: float | None
    tools: bool | None
    reasoning: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "name": self.name,
            "context": self.context,
            "output_limit": self.output,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "tools": self.tools,
            "reasoning": self.reasoning,
        }


def load_catalog(root: Path) -> list[CatalogEntry]:
    """Parse the vendored snapshot; empty list when absent/malformed."""
    path = root / CATALOG_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries: list[CatalogEntry] = []
    for pid, prov in (data.get("providers") or {}).items():
        if not isinstance(prov, dict):
            continue
        for mid, m in (prov.get("models") or {}).items():
            if not isinstance(m, dict):
                continue
            entries.append(
                CatalogEntry(
                    provider=str(pid),
                    model_id=str(mid),
                    name=str(m.get("name") or mid),
                    context=m.get("ctx"),
                    output=m.get("out"),
                    input_cost=m.get("in_cost"),
                    output_cost=m.get("out_cost"),
                    tools=m.get("tools"),
                    reasoning=m.get("reasoning"),
                )
            )
    return entries


def find_model(entries: list[CatalogEntry], query: str) -> list[CatalogEntry]:
    """Case-insensitive match on model id or display name."""
    q = query.lower()
    return [e for e in entries if q in e.model_id.lower() or q in e.name.lower()]


def catalog_summary(entries: list[CatalogEntry]) -> dict[str, Any]:
    providers = sorted({e.provider for e in entries})
    return {
        "providers": providers,
        "provider_count": len(providers),
        "model_count": len(entries),
    }
