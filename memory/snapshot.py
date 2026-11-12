"""Compact, immutable memory snapshots (OpenVDB/NanoVDB adoption).

OpenVDB ships two forms of the same volume: the mutable ``Grid`` and the
baked ``NanoVDB`` — a read-only, compacted copy for fast lookup. Same
need here: the live ``memory/*.db`` mutates constantly, but tools that
just *read* memory should open a snapshot — immutable, checksummed,
transportable.

``export_snapshot`` produces:

- ``memory.sdb`` — a compacted SQLite copy (``VACUUM INTO``).
- ``manifest.json`` — {created, source_sha256, table counts, version}.
- ``SHA256SUMS`` — per-file checksums so a snapshot can't silently drift.

``open_snapshot`` returns a read-only connection (``mode=ro&immutable=1``).

Usage::

    manifest = export_snapshot(root / "memory" / "aizee.db", out_dir)
    conn = open_snapshot(out_dir)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.schemas import StorageError

logger = logging.getLogger(__name__)

SNAP_DB = "memory.sdb"
MANIFEST = "manifest.json"
SUMS = "SHA256SUMS"

_TABLES = ("memories", "memories_fts", "edges", "meta")


def _ro_uri(path: Path, params: str = "mode=ro") -> str:
    """SQLite read-only URI — POSIX separators + quoting so any path works."""
    from urllib.parse import quote

    return f"file:{quote(path.resolve().as_posix(), safe='/:')}?{params}"


@dataclass
class SnapshotInfo:
    dir: Path
    created_at: float
    source_sha256: str
    tables: dict[str, int]
    aizee_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dir": str(self.dir),
            "created_at": self.created_at,
            "source_sha256": self.source_sha256,
            "tables": self.tables,
            "aizee_version": self.aizee_version,
        }


def export_snapshot(
    src_db: Path | str,
    out_dir: Path | str,
    *,
    aizee_version: str = "",
) -> SnapshotInfo:
    """Bake an immutable, compacted copy of the memory DB."""
    src = Path(src_db)
    out = Path(out_dir)
    if not src.exists():
        raise StorageError(f"source memory db missing: {src}", context={"path": str(src)})
    out.mkdir(parents=True, exist_ok=True)
    snap_path = out / SNAP_DB

    try:
        with contextlib.closing(sqlite3.connect(_ro_uri(src), uri=True)) as reader:
            # VACUUM INTO needs a writer; open the snapshot target fresh.
            # `with connect()` only commits — it never closes — so use
            # closing() or WAL sidecars (-wal/-shm) leak into the snapshot
            # dir and the .sdb alone is an incomplete copy.
            with contextlib.closing(sqlite3.connect(snap_path)) as writer:
                reader.backup(writer)  # consistent copy under the live DB
                # backup() inherits the source journal mode (WAL) — fold the
                # WAL into the main file and downgrade so the snapshot is
                # self-contained (SHA256SUMS covers every byte that matters).
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                writer.execute("PRAGMA journal_mode=DELETE")
            with contextlib.closing(sqlite3.connect(snap_path)) as compacter:
                compacter.execute("VACUUM")
                compacter.execute("PRAGMA optimize")
    except sqlite3.Error as exc:
        raise StorageError(f"snapshot export failed: {exc}") from exc
    for sidecar in out.glob(f"{SNAP_DB}-*"):
        with contextlib.suppress(OSError):
            sidecar.unlink()

    info = SnapshotInfo(
        dir=out,
        created_at=time.time(),
        source_sha256=_sha256(src),
        tables=_table_counts(snap_path),
        aizee_version=aizee_version,
    )
    (out / MANIFEST).write_text(json.dumps(info.to_dict(), indent=2) + "\n", encoding="utf-8")
    _write_sums(out)
    return info


def open_snapshot(out_dir: Path | str) -> sqlite3.Connection:
    """Open a snapshot read-only + immutable (safe to hand to anything)."""
    path = Path(out_dir) / SNAP_DB
    if not path.exists():
        raise StorageError(f"no snapshot at {path}", context={"path": str(path)})
    try:
        return sqlite3.connect(_ro_uri(path, "mode=ro&immutable=1"), uri=True)
    except sqlite3.Error as exc:
        raise StorageError(f"snapshot open failed: {exc}") from exc


def verify_snapshot(out_dir: Path | str) -> dict[str, Any]:
    """Re-hash snapshot files against SHA256SUMS — catches tampering."""
    out = Path(out_dir)
    sums = out / SUMS
    if not sums.exists():
        return {"ok": False, "reason": "no SHA256SUMS"}
    report: dict[str, Any] = {"ok": True, "files": {}}
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        expected, name = line.split("  ", 1)
        actual = _sha256(out / name)
        report["files"][name] = actual == expected
        if actual != expected:
            report["ok"] = False
    return report


def load_manifest(out_dir: Path | str) -> dict[str, Any]:
    path = Path(out_dir) / MANIFEST
    if not path.exists():
        raise StorageError(f"no manifest at {path}", context={"path": str(path)})
    return dict(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _table_counts(db: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        with contextlib.closing(sqlite3.connect(_ro_uri(db), uri=True)) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for (name,) in rows:
                try:
                    safe = name.replace('"', '""')
                    (n,) = conn.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()
                    counts[name] = int(n)
                except sqlite3.Error:
                    counts[name] = -1
    except sqlite3.Error as exc:
        logger.debug("table count scan failed on %s: %s", db, exc)
    return counts


def _write_sums(out: Path) -> None:
    lines = []
    for name in (SNAP_DB, MANIFEST):
        p = out / name
        if p.exists():
            lines.append(f"{_sha256(p)}  {name}")
    (out / SUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")
