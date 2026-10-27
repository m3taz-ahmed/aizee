"""Token-efficient output filter for tool results.

Adopted from RTK/Headroom pattern (referenced by free-claude-code): compress
repetitive or low-signal text before it reaches the model so more context
budget goes to reasoning. Deterministic — no model calls, no data loss on
semantic lines, only structural redundancy removed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lines matching these patterns are collapsed to one representative line.
_REPEAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*$"),
    re.compile(r"^\s*[-=~]{3,}\s*$"),
    re.compile(r"^\s*\.{3,}\s*$"),
    re.compile(r"^\s*#+\s*$"),
    re.compile(r"^\s*(?:File|Requirement already satisfied)"),
)

# Truncate each line beyond this many characters.
_LINE_CAP = 400


@dataclass(frozen=True)
class FilterStats:
    original_lines: int
    filtered_lines: int
    original_chars: int
    filtered_chars: int
    collapsed_groups: int

    @property
    def saved_chars(self) -> int:
        return self.original_chars - self.filtered_chars

    @property
    def compression_ratio(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return round(self.saved_chars / self.original_chars, 3)


def filter_output(text: str, max_lines: int = 200) -> tuple[str, FilterStats]:
    """Compress tool output text; return (filtered_text, stats)."""
    original_lines = text.splitlines(keepends=True)
    original_chars = len(text)

    filtered: list[str] = []
    collapsed = 0

    for line in original_lines:
        line = _truncate_line(line)
        stripped = line.strip()

        if _is_repeat(stripped):
            collapsed += 1
            continue

        if len(filtered) >= max_lines:
            filtered.append(f"... [{len(original_lines) - len(filtered)} more lines truncated]")
            break

        filtered.append(line)

    filtered_text = "".join(filtered)
    stats = FilterStats(
        original_lines=len(original_lines),
        filtered_lines=len(filtered),
        original_chars=original_chars,
        filtered_chars=len(filtered_text),
        collapsed_groups=collapsed,
    )
    return filtered_text, stats


def _is_repeat(stripped: str) -> bool:
    """True for pure-boilerplate lines (separators, pip noise, etc.)."""
    return any(p.search(stripped) for p in _REPEAT_PATTERNS)


def _truncate_line(line: str) -> str:
    if len(line) > _LINE_CAP:
        return line[: _LINE_CAP] + " ...[truncated]\n"
    return line
