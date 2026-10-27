"""Memory ingest consume-rules — watch folders, match, tag, route to banks.

Adopted from paperless-ngx consume pipeline: a rules file maps path globs to
target memory banks, kinds, and tags so ``aizee memory ingest`` routes each
matched file without manual classification.

Rules file: ``rules/ingest.yaml`` (os_root), format::

    rules:
      - match: "tech-stack/*.md"
        bank: tech-stack
        kind: reference
        tags: [stack]
      - match: "workflows/*.md"
        bank: workflows
        kind: workflow
        tags: [process]

Files matching no rule fall back to the caller's default bank/kind.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class IngestRule:
    match: str
    bank: str = "default"
    kind: str = "note"
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IngestDecision:
    bank: str
    kind: str
    tags: tuple[str, ...]
    rule: str | None  # pattern that matched, or None for defaults


def load_rules(os_root: Path, rules_path: Path | None = None) -> list[IngestRule]:
    """Load ingest rules from ``rules/ingest.yaml`` (or explicit path)."""
    path = rules_path or (os_root / "rules" / "ingest.yaml")
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules: list[IngestRule] = []
    for raw in data.get("rules", []) or []:
        if not isinstance(raw, dict) or "match" not in raw:
            continue
        rules.append(IngestRule(
            match=str(raw["match"]),
            bank=str(raw.get("bank", "default")),
            kind=str(raw.get("kind", "note")),
            tags=tuple(str(t) for t in (raw.get("tags") or [])),
        ))
    return rules


def match_file(
    rel_path: str,
    rules: list[IngestRule],
    default_bank: str = "default",
    default_kind: str = "note",
) -> IngestDecision:
    """Match a relative path against rules; first match wins."""
    normalized = rel_path.replace("\\", "/").lstrip("./")
    for rule in rules:
        if fnmatch.fnmatch(normalized, rule.match):
            return IngestDecision(
                bank=rule.bank,
                kind=rule.kind,
                tags=rule.tags,
                rule=rule.match,
            )
    return IngestDecision(bank=default_bank, kind=default_kind, tags=(), rule=None)


def scan_folder(
    folder: Path,
    rules: list[IngestRule],
    base: Path | None = None,
) -> list[tuple[Path, IngestDecision]]:
    """Walk a folder and pair each file with its ingest decision.

    Used by ``aizee memory ingest --watch`` to dry-run the consume pipeline.
    """
    base = base or folder
    results: list[tuple[Path, IngestDecision]] = []
    if not folder.is_dir():
        return results
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = str(path.relative_to(base))
        except ValueError:
            rel = path.name
        results.append((path, match_file(rel, rules)))
    return results
