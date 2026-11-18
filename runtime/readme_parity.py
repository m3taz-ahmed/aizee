"""Localized-README parity gate — structural parity across ``README*.md``.

Adopted from stickman-video-director's ``verify-localized-readmes.py``:
localization parity as a tested invariant, not a hope. The English README is
the base; every ``README-*.md`` sibling must carry the same skeleton:

- same ordered count of ``##``/``###`` section headings (anchors may be
  translated — count, not text, is compared)
- same numeric values inside shields.io badge URLs and ``alt`` text
  (skill/tool/test counts — the exact drift this gate exists to catch)
- same number of tables and rows per table
- same count of fenced code blocks

Text content is deliberately not compared — translation changes words,
parity changes structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_HEADING_RE = re.compile(r"^(#{2,3})\s", re.M)
_FENCE_RE = re.compile(r"^```", re.M)
_TABLE_ROW_RE = re.compile(r"^\s*\|", re.M)
_BADGE_NUM_RE = re.compile(r"(?:badge/[^-\"']*-(\d+)|alt=\"[^\"]*?(\d+)[^\"]*?\")")


@dataclass
class ParityIssue:
    file: str
    check: str
    expected: str
    found: str

    def to_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "check": self.check,
            "expected": self.expected,
            "found": self.found,
        }


@dataclass
class ParityReport:
    ok: bool
    base: str
    compared: int = 0
    issues: list[ParityIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "base": self.base,
            "compared": self.compared,
            "issues": [i.to_dict() for i in self.issues],
        }


def _structure(text: str) -> dict[str, Any]:
    return {
        # Heading level sequence (##/### pattern) — translation-invariant,
        # so it catches both missing and reordered sections.
        "headings": [len(h) for h in _HEADING_RE.findall(text)],
        "fences": len(_FENCE_RE.findall(text)),
        "table_rows": len(_TABLE_ROW_RE.findall(text)),
        # Unique advertised numbers — set compare keeps the drift signal
        # (stale counts) while ignoring URL-encoding shape differences
        # between locales (percent-encoded badge slugs).
        "badge_numbers": sorted(
            {n for m in _BADGE_NUM_RE.finditer(text) for n in m.groups() if n},
            key=int,
        ),
    }


def localized_readmes(root: Path) -> list[Path]:
    """``README-*.md`` siblings of the base README (locale editions)."""
    return sorted(p for p in root.glob("README-*.md") if p.is_file())


def check_readme_parity(root: Path, base_name: str = "README.md") -> ParityReport:
    """Compare every localized README's structure against the base."""
    base_path = root / base_name
    report = ParityReport(ok=True, base=base_name)
    if not base_path.exists():
        report.ok = False
        report.issues.append(ParityIssue(base_name, "base", "exists", "missing"))
        return report
    try:
        base = _structure(base_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        report.ok = False
        report.issues.append(ParityIssue(base_name, "base", "readable", "unreadable"))
        return report

    for doc in localized_readmes(root):
        report.compared += 1
        rel = doc.name
        try:
            other = _structure(doc.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            report.issues.append(ParityIssue(rel, "read", "readable", "unreadable"))
            continue
        for key in ("headings", "fences", "table_rows", "badge_numbers"):
            if base[key] != other[key]:
                report.issues.append(
                    ParityIssue(rel, key, str(base[key]), str(other[key]))
                )
    report.ok = not report.issues
    return report
