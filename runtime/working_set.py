"""Bounded working-set cache (Pencil2D ActiveFramePool adoption).

A fixed-size LRU mapping: evictions drop the least-recently-used entry,
so hot paths keep only the current "active window" of state instead of
unbounded growth. Shared primitive for the step cache, event history,
and prefetch LRU.

Usage::

    ws = WorkingSet(max_entries=64)
    ws["a"] = 1
    ws["a"]  # -> 1 (now most-recent)
    ws.evict_oldest()  # manual drop
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from typing import Any


class WorkingSet:
    """LRU cache bounded to ``max_entries`` — the active window of state.

    Inspired by Pencil2D's ``ActiveFramePool``: only frames near the
    playhead stay materialized; everything outside the window is dropped
    (and can be re-derived on demand). ``on_evict`` receives evicted
    (key, value) pairs for callers that need a spill hook.
    """

    def __init__(
        self,
        max_entries: int = 128,
        *,
        on_evict: Callable[[Any, Any], None] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries
        self.on_evict = on_evict
        self._data: OrderedDict[Any, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Any, default: Any = None) -> Any:
        """Return value, refreshing recency; tracks hit/miss stats."""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return default

    def put(self, key: Any, value: Any) -> None:
        """Insert/refresh an entry; evicts LRU when over capacity."""
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                k, v = self._data.popitem(last=False)
                if self.on_evict is not None:
                    self.on_evict(k, v)

    def evict_oldest(self, count: int = 1) -> None:
        """Drop the ``count`` least-recently-used entries."""
        with self._lock:
            for _ in range(min(count, len(self._data))):
                k, v = self._data.popitem(last=False)
                if self.on_evict is not None:
                    self.on_evict(k, v)

    def keys_recent(self, limit: int | None = None) -> list[Any]:
        """Keys ordered oldest -> newest (dope-sheet order)."""
        with self._lock:
            keys = list(self._data.keys())
            return keys if limit is None else keys[-limit:]

    def items_recent(self, limit: int | None = None) -> list[tuple[Any, Any]]:
        """(key, value) pairs ordered oldest -> newest."""
        with self._lock:
            items = list(self._data.items())
            return items if limit is None else items[-limit:]

    def take_recent(self, limit: int | None = None) -> list[tuple[Any, Any]]:
        """Atomically remove + return the newest ``limit`` items (drain op).

        A separate ``items_recent`` + ``clear`` loses entries inserted
        between the two calls — a single locked take keeps the read and
        the removal atomic (event-bus SSE drain).
        """
        with self._lock:
            items = list(self._data.items())
            kept = items if limit is None else items[-limit:]
            for key, _ in kept:
                del self._data[key]
            return kept

    def stats(self) -> dict[str, int]:
        """Size + hit/miss counters for observability."""
        with self._lock:
            return {
                "size": len(self._data),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
            }

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._data

    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys_recent())
