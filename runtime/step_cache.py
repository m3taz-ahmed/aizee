"""Content-hash step memoization (Natron render-cache adoption).

Every compositing node in Natron hashes its inputs + params into a cache
key; unchanged nodes replay from the cache instead of re-rendering. The
same applies to plan steps: a ``call`` step's result is keyed by
``sha256(tool + resolved args)`` so a re-run with edited args skips only
the steps whose inputs actually changed — across runs, not just within
one suspend/resume cycle.

Storage: JSON files under ``<root>/state/step-cache/`` with an in-memory
``WorkingSet`` index so eviction is bounded (LRU window, not unbounded
growth — see ``runtime/working_set.py``).

Usage::

    cache = StepCache(root / "state" / "step-cache")
    key = cache.key_for("dns.lookup", {"name": "example.com"})
    hit = cache.get(key)          # -> cached result or _MISSING
    cache.put(key, result)
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any

from runtime.schemas import ValidationError
from runtime.working_set import WorkingSet

MISSING = object()

_MAX_INDEX = 512  # LRU window over cache keys; files stay on disk

# Keys become filenames — path-safe chars only, same convention as
# task_farm._ID_RE (blocks separators and dot-dot traversal).
_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class StepCache:
    """Per-step result cache keyed by content hash of (tool, args)."""

    def __init__(self, cache_dir: Path, *, max_index: int = _MAX_INDEX) -> None:
        self._dir = cache_dir
        self._index = WorkingSet(max_entries=max_index)
        self._lock = threading.Lock()
        self.hits = 0
        self.stores = 0

    @staticmethod
    def key_for(tool: str, args: dict[str, Any]) -> str:
        """Content hash of tool name + fully-resolved args (Natron getHash)."""
        blob = json.dumps(
            {"tool": tool, "args": args},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def _check_key(self, key: str) -> None:
        if not _KEY_RE.fullmatch(key):
            raise ValidationError(
                f"invalid cache key {key!r}", context={"key": key}
            )

    def _path(self, key: str) -> Path:
        self._check_key(key)
        return self._dir / f"{key}.json"

    def get(self, key: str) -> Any:
        """Return cached result or ``MISSING``."""
        self._check_key(key)
        hit = self._index.get(key, MISSING)
        if hit is not MISSING:
            self.hits += 1
            return hit
        path = self._path(key)
        with self._lock:
            try:
                if not path.exists():
                    return MISSING
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return MISSING
        self._index.put(key, data.get("value"))
        self.hits += 1
        return data.get("value")

    def put(self, key: str, value: Any, *, tool: str = "") -> None:
        """Persist a result (atomic write) + index it."""
        self._check_key(key)  # before ANY path is built from it
        if not isinstance(value, (dict, list, str, int, float, bool, type(None))):
            return  # non-serializable results are not cacheable
        record = {"key": key, "tool": tool, "value": value}
        with self._lock:
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                tmp = self._dir / f".{key}.tmp"
                tmp.write_text(json.dumps(record, default=str, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self._path(key))
            except OSError:
                return  # cache is best-effort; never break a run for it
        self._index.put(key, value)
        self.stores += 1

    def stats(self) -> dict[str, Any]:
        files = len(list(self._dir.glob("*.json"))) if self._dir.exists() else 0
        return {
            "dir": str(self._dir),
            "files": files,
            "hits": self.hits,
            "stores": self.stores,
            "index": self._index.stats(),
        }

    def clear(self) -> int:
        """Delete all cached step files (+ stray tmp). Returns count removed."""
        removed = 0
        if self._dir.exists():
            for pattern in ("*.json", ".*.tmp"):
                for path in self._dir.glob(pattern):
                    try:
                        path.unlink()
                        removed += 1
                    except OSError:
                        continue
        self._index.clear()
        return removed
