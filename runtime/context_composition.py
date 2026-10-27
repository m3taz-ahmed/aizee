"""Per-call context-window composition telemetry.

Adopted from DeepTutor's ``context_budget`` pattern: measure what actually
filled a provider request — the named segments that produced it — so the
readout describes material that was *sent*, not estimates derived later.
Budget tracking (``runtime/budget.py``) enforces limits; this module reports
composition — how full the window is and what is filling it.

Telemetry only: ``measure`` never raises and never blocks a call. A broken
token counter degrades a segment to 0 tokens rather than sinking the turn.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

TokenCounter = Callable[[str], int]

_CHARS_PER_TOKEN = 4


def default_token_counter(text: str) -> int:
    """Cheap heuristic counter (~4 chars/token) when no real tokenizer is wired."""
    if not text:
        return 0
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


@dataclass(slots=True)
class ContextSegment:
    """One named piece of an assembled request (system prompt, tools, memory...)."""

    name: str
    text: str


@dataclass(slots=True)
class SegmentReport:
    """One row of the composition readout."""

    name: str
    tokens: int
    share_of_total: float
    share_of_window: float


@dataclass(slots=True)
class CompositionReport:
    """What one real provider call carried, decomposed by segment."""

    window_tokens: int
    total_tokens: int
    utilization: float
    over_budget: bool
    dominant: str
    segments: list[SegmentReport] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """JSON-safe envelope for tool/audit output."""
        return {
            "window_tokens": self.window_tokens,
            "total_tokens": self.total_tokens,
            "utilization": round(self.utilization, 4),
            "over_budget": self.over_budget,
            "dominant": self.dominant,
            "segments": [
                {
                    "name": s.name,
                    "tokens": s.tokens,
                    "share_of_total": round(s.share_of_total, 4),
                    "share_of_window": round(s.share_of_window, 4),
                }
                for s in self.segments
            ],
            "degraded": list(self.degraded),
        }

    def render(self) -> str:
        """Human-readable readout: one line per segment (largest first) + total."""
        lines: list[str] = []
        for seg in self.segments:
            lines.append(
                f"  {seg.name:<24} {seg.tokens:>8,} tok"
                f"  {seg.share_of_total:>6.1%} of total"
                f"  {seg.share_of_window:>6.1%} of window"
            )
        state = "OVER" if self.over_budget else "ok"
        lines.append(
            f"  {'─' * 60}\n"
            f"  {'total':<24} {self.total_tokens:>8,} tok"
            f"  window {self.window_tokens:,} ({self.utilization:.1%}) [{state}]"
        )
        if self.degraded:
            lines.append(f"  degraded (counter failed, counted as 0): {', '.join(self.degraded)}")
        return "\n".join(lines)


def measure(
    segments: Iterable[ContextSegment | tuple[str, str]],
    *,
    window_tokens: int,
    token_counter: TokenCounter | None = None,
) -> CompositionReport:
    """Measure already-assembled request segments against the model window.

    Accepts ``ContextSegment`` items or plain ``(name, text)`` tuples. Segments
    are reported sorted by tokens descending. Never raises: a failing counter
    degrades that segment to 0 tokens and records its name in ``degraded``.
    """
    counter = token_counter or default_token_counter
    counted: list[tuple[str, int]] = []
    degraded: list[str] = []
    for seg in segments:
        name, text = (seg.name, seg.text) if isinstance(seg, ContextSegment) else seg
        try:
            counted.append((name, max(0, int(counter(text)))))
        except Exception as exc:  # telemetry must never sink a call
            logger.debug("context_composition: counter failed for %r: %s", name, exc)
            counted.append((name, 0))
            degraded.append(name)

    total = sum(tokens for _, tokens in counted)
    window = max(0, int(window_tokens))
    utilization = total / window if window > 0 else 0.0
    counted.sort(key=lambda item: item[1], reverse=True)

    reports = [
        SegmentReport(
            name=name,
            tokens=tokens,
            share_of_total=tokens / total if total > 0 else 0.0,
            share_of_window=tokens / window if window > 0 else 0.0,
        )
        for name, tokens in counted
    ]
    return CompositionReport(
        window_tokens=window,
        total_tokens=total,
        utilization=utilization,
        over_budget=window > 0 and total > window,
        dominant=counted[0][0] if counted else "",
        segments=reports,
        degraded=degraded,
    )
