"""Tests for memory/snapshot.py — immutable compact export (OpenVDB)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from memory.snapshot import (
    MANIFEST,
    SNAP_DB,
    SUMS,
    export_snapshot,
    load_manifest,
    open_snapshot,
    verify_snapshot,
)
from runtime.schemas import StorageError


def _seed_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT)")
        conn.executemany(
            "INSERT INTO memories VALUES (?, ?)",
            [(f"m{i}", f"content {i}") for i in range(5)],
        )
        conn.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        conn.execute("INSERT INTO meta VALUES ('v', '1')")


def test_export_and_verify(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _seed_db(src)
    out = tmp_path / "snap"
    info = export_snapshot(src, out, aizee_version="9.9.9")
    assert (out / SNAP_DB).exists()
    assert (out / MANIFEST).exists()
    assert (out / SUMS).exists()
    assert info.tables["memories"] == 5
    assert info.aizee_version == "9.9.9"
    assert len(info.source_sha256) == 64
    assert verify_snapshot(out)["ok"] is True


def test_snapshot_is_readonly(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _seed_db(src)
    out = tmp_path / "snap"
    export_snapshot(src, out)
    conn = open_snapshot(out)
    rows = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
    assert rows[0] == 5
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO memories VALUES ('x', 'y')")
    conn.close()


def test_verify_detects_tamper(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _seed_db(src)
    out = tmp_path / "snap"
    export_snapshot(src, out)
    (out / MANIFEST).write_text('{"tampered": true}\n')
    report = verify_snapshot(out)
    assert report["ok"] is False
    assert report["files"][MANIFEST] is False


def test_load_manifest(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _seed_db(src)
    out = tmp_path / "snap"
    export_snapshot(src, out)
    m = load_manifest(out)
    assert m["tables"]["memories"] == 5


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        export_snapshot(tmp_path / "nope.db", tmp_path / "out")


def test_open_missing_snapshot_raises(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        open_snapshot(tmp_path / "nothing")


def _seed_wal_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT)")
    conn.executemany(
        "INSERT INTO memories VALUES (?, ?)",
        [(f"m{i}", f"content {i}") for i in range(5)],
    )
    conn.commit()
    conn.close()


def test_export_from_wal_source_is_self_contained(tmp_path: Path) -> None:
    """A WAL-mode source must not leak -wal/-shm sidecars into the snapshot."""
    src = tmp_path / "src.db"
    _seed_wal_db(src)
    out = tmp_path / "snap"
    export_snapshot(src, out)
    assert not list(out.glob(f"{SNAP_DB}-*"))  # no stray sidecars
    # every data byte lives in the checksummed .sdb itself
    conn = open_snapshot(out)
    try:
        assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 5
    finally:
        conn.close()


def test_export_removes_preexisting_sidecar(tmp_path: Path) -> None:
    """A stray memory.sdb-* file left in out/ is cleaned after export."""
    src = tmp_path / "src.db"
    _seed_wal_db(src)
    out = tmp_path / "snap"
    out.mkdir()
    (out / f"{SNAP_DB}-zzz").write_bytes(b"junk")  # not -wal/-shm: sqlite won't claim it
    export_snapshot(src, out)
    assert not list(out.glob(f"{SNAP_DB}-*"))


def test_export_sqlite_failure_raises_storage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src.db"
    _seed_wal_db(src)  # must exist: missing source raises before the try block

    def _boom(*a: object, **k: object) -> None:
        raise sqlite3.OperationalError("dead")

    monkeypatch.setattr(sqlite3, "connect", _boom)
    with pytest.raises(StorageError):
        export_snapshot(src, tmp_path / "out")


def test_load_manifest_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _seed_wal_db(src)
    out = tmp_path / "snap"
    export_snapshot(src, out)
    manifest = load_manifest(out)
    assert isinstance(manifest, dict) and manifest
    with pytest.raises(StorageError):
        load_manifest(tmp_path / "nothing")


def test_open_snapshot_error_paths(tmp_path: Path) -> None:
    with pytest.raises(StorageError):  # no snapshot dir
        open_snapshot(tmp_path / "nope")
    out = tmp_path / "d"
    (out / SNAP_DB).mkdir(parents=True)  # a dir named like the db -> connect fails
    with pytest.raises(StorageError):
        open_snapshot(out)


def test_verify_missing_sums_blank_lines_and_tamper(tmp_path: Path) -> None:
    assert verify_snapshot(tmp_path)["ok"] is False  # no SHA256SUMS at all
    out = tmp_path / "s"
    out.mkdir()
    (out / SUMS).write_text(
        "\n" + "0" * 64 + "  missing.db\n\n", encoding="utf-8"
    )
    rep = verify_snapshot(out)
    assert rep["ok"] is False              # missing file hashes to ""
    assert rep["files"]["missing.db"] is False


def test_table_counts_failure_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import memory.snapshot as snap

    class _Rows:
        def fetchall(self) -> list:
            return [("t1",)]

    class _Conn:
        def execute(self, sql: str, *a: object) -> object:
            if "sqlite_master" in sql:
                return _Rows()
            raise sqlite3.Error("nope")

        def close(self) -> None:
            pass

    monkeypatch.setattr(snap.sqlite3, "connect", lambda *a, **k: _Conn())
    assert snap._table_counts(tmp_path / "x") == {"t1": -1}

    def _boom(*a: object, **k: object) -> None:
        raise sqlite3.Error("down")

    monkeypatch.setattr(snap.sqlite3, "connect", _boom)
    assert snap._table_counts(tmp_path / "x") == {}


def test_write_sums_without_manifest(tmp_path: Path) -> None:
    import memory.snapshot as snap

    (tmp_path / SNAP_DB).write_bytes(b"db")
    snap._write_sums(tmp_path)
    lines = (tmp_path / SUMS).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and lines[0].endswith(SNAP_DB)
