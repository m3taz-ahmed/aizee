"""Audit timeline replay (Theatre.js dope-sheet adoption).

The audit log is already an append-only, HMAC-chained recording of every
gate decision — the same shape as Theatre.js's recorded sequence. This
module gives it a *player*: frames on a timeline, grouped into tracks,
scrubbed forward/back, rendered as a text dope sheet for the CLI
(`aizee replay`) or as dicts for the dashboard.

Read-only guarantee: replay only parses entries — nothing re-executes.

Usage::

    frames = load_frames(root / "state" / "audit.log")
    track = ReplayTrack(frames)
    print(track.render())           # text dope sheet
    track.scrub(0.5).head_frame()   # middle of the session
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Frame:
    """One moment on the timeline — an audit entry normalized."""

    idx: int
    ts: str
    type: str
    details: dict[str, Any] = field(default_factory=dict)
    hash: str = ""

    @property
    def label(self) -> str:
        d = self.details
        return (
            str(d.get("action") or d.get("name") or d.get("op") or self.type)
        )[:48]

    @property
    def verdict(self) -> str:
        d = self.details
        for key in ("decision", "verdict", "status", "result"):
            if key in d:
                return str(d[key])[:16]
        return ""


def load_frames(
    log_path: Path | str,
    *,
    event_type: str | None = None,
    limit: int | None = None,
) -> list[Frame]:
    """Parse audit JSONL into chronological frames (oldest -> newest)."""
    path = Path(log_path)
    if not path.exists():
        return []
    frames: list[Frame] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_type and entry.get("type") != event_type:
                continue
            details = entry.get("details") or {}
            frames.append(
                Frame(
                    idx=idx,
                    ts=str(entry.get("ts", "")),
                    type=str(entry.get("type", "event")),
                    details=details if isinstance(details, dict) else {"value": details},
                    hash=str(entry.get("hash", "")),
                )
            )
    if limit is not None:
        frames = frames[-limit:]
    return frames


class ReplayTrack:
    """A scrubbable view over ordered frames — the playback head."""

    def __init__(self, frames: list[Frame]) -> None:
        self.frames = frames
        self._head = len(frames)  # head = past-the-end == played to now

    # -- playhead ---------------------------------------------------------

    @property
    def head(self) -> int:
        return self._head

    def scrub(self, pos: float | int) -> ReplayTrack:
        """Move the playhead: float [0,1] fraction or int frame index."""
        if isinstance(pos, float):
            self._head = max(0, min(len(self.frames), round(pos * len(self.frames))))
        else:
            self._head = max(0, min(len(self.frames), int(pos)))
        return self

    def played(self) -> list[Frame]:
        """Frames before the head — the 'current state' of the replay."""
        return self.frames[: self._head]

    def upcoming(self) -> list[Frame]:
        return self.frames[self._head :]

    def head_frame(self) -> Frame | None:
        return self.frames[self._head - 1] if 0 < self._head <= len(self.frames) else None

    # -- summaries --------------------------------------------------------

    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.frames:
            counts[f.type] = counts.get(f.type, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def span(self) -> tuple[str, str]:
        return (self.frames[0].ts, self.frames[-1].ts) if self.frames else ("", "")

    def to_dict(self, *, with_frames: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "count": len(self.frames),
            "head": self._head,
            "span": self.span(),
            "by_type": self.by_type(),
        }
        if with_frames:
            d["frames"] = [
                {"i": f.idx, "ts": f.ts, "type": f.type, "label": f.label, "verdict": f.verdict}
                for f in self.frames
            ]
        return d

    # -- text render ------------------------------------------------------

    def render(self, *, width: int = 60, tail: int | None = None) -> str:
        """Dope-sheet render — one line per frame, ▸ marks the playhead."""
        rows = self.frames if tail is None else self.frames[-tail:]
        offset = len(self.frames) - len(rows)  # head is global; rows may be a tail slice
        head_in_rows = self._head - offset  # 1-based position inside `rows`
        start, _end = self.span()
        lines = [f"replay: {len(self.frames)} frames  span {start} — {_end}".rstrip(" —")]
        types = ", ".join(f"{k} x {v}" for k, v in self.by_type().items())
        if types:
            lines.append(f"  tracks: {types}")
        bar_every = max(1, len(rows) // width) if rows else 1
        bar = "".join(
            "▮" if i == head_in_rows - 1 or (head_in_rows >= len(rows) and i == len(rows) - 1) else "·"
            for i in range(0, len(rows), bar_every)
        )
        if rows:
            lines.append(f"  [{bar}]")
        for f in rows:
            mark = (
                "▸"
                if f.idx == (rows[head_in_rows - 1].idx if 0 < head_in_rows <= len(rows) else -1)
                else " "
            )
            verdict = f"  → {f.verdict}" if f.verdict else ""
            lines.append(f" {mark} {_fmt_ts(f.ts)}  {f.type:16} {f.label}{verdict}")
        return "\n".join(lines)


def _fmt_ts(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return ts[:8]
