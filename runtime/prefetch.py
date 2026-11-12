"""Predictive prefetch during plan execution (OpenToonz adoption).

OpenToonz's ``TPredictiveCacheManager`` speculatively renders nodes the
graph is likely to need next. Applied here: while the current plan step
runs, a background worker warms resources the *upcoming* steps will need
— file paths referenced in args are pre-read into a bounded LRU
(``WorkingSet``) so the real step pays less I/O, and tool names are
resolved against the registry ahead of time.

Guarantees kept:

- **Read-only**: prefetching never executes a tool or mutates state.
- **Bounded**: lookahead window, queue depth, and LRU size are all capped.
- **Fail-soft**: any prefetch error is dropped silently — speculation
  must never break the real run.

Usage::

    prefetcher = Prefetcher(tools=registry, max_queue=32)
    prefetcher.start()
    prefetcher.suggest(next_steps)   # called by PlanRunner lookahead
    ...                              # run step
    text = prefetcher.read(path)     # warm hit -> instant, cold -> read
    prefetcher.stop()
"""

from __future__ import annotations

import contextlib
import os
import queue
import threading
from pathlib import Path
from typing import Any

from runtime.working_set import WorkingSet

_MAX_PREFETCH_FILE = 512 * 1024  # don't buffer huge blobs — 512KB cap


class Prefetcher:
    """Background warm-up worker for plan look-ahead."""

    def __init__(
        self,
        *,
        tools: dict[str, Any] | None = None,
        max_queue: int = 32,
        cache_entries: int = 64,
    ) -> None:
        self._tools = tools if tools is not None else {}
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max_queue)
        self._seen: set[str] = set()
        self._files = WorkingSet(max_entries=cache_entries)
        self._tool_warm: set[str] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.warmed = 0

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="aizee-prefetch")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(None)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> Prefetcher:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- API --------------------------------------------------------------

    def suggest(self, steps: list[dict[str, Any]]) -> int:
        """Enqueue upcoming steps for warming. Returns count queued."""
        if self._stop.is_set():
            return 0
        queued = 0
        for step in steps:
            key = repr(step)[:256]
            if key in self._seen:
                continue
            self._seen.add(key)
            try:
                self._queue.put_nowait(step)
                queued += 1
            except queue.Full:
                break  # bounded: speculation never blocks the real run
        return queued

    def read(self, path: Path) -> str | None:
        """Read a file, served from the warm window when prefetched."""
        cached = self._files.get(str(path), None)
        if cached is not None:
            return str(cached)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        self._files.put(str(path), text)
        return text

    def stats(self) -> dict[str, Any]:
        return {
            "warmed": self.warmed,
            "tool_warm": sorted(self._tool_warm),
            "files": self._files.stats(),
            "queued": self._queue.qsize(),
        }

    # -- worker -----------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                step = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if step is None:
                return
            try:
                self._warm_step(step)
            except Exception:  # speculation must never crash the worker
                continue

    def _warm_step(self, step: dict[str, Any]) -> None:
        if step.get("op") != "call":
            return
        tool = step.get("tool")
        if isinstance(tool, str) and tool in self._tools:
            self._tool_warm.add(tool)
            self.warmed += 1
        for value in (step.get("args") or {}).values():
            if not isinstance(value, str) or value.startswith("$"):
                continue
            path = Path(os.path.expandvars(value))
            try:
                if (
                    path.is_file()
                    and path.stat().st_size <= _MAX_PREFETCH_FILE
                    and self.read(path) is not None
                ):
                    self.warmed += 1
            except OSError:
                continue
