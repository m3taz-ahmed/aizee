"""Tests for runtime/bootstrap.py — PyPI bootstrap path (P2.5)."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import runtime.bootstrap as bs
from runtime.bootstrap import bootstrap


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "new-root"
    res = bootstrap(target, dry_run=True, mcp_sync=False)
    assert res.ok and not target.exists()
    assert "skills/" in res.created_dirs
    assert "runtime/policies/default.yaml" in res.written_files


def test_apply_creates_layout(tmp_path: Path) -> None:
    target = tmp_path / "root"
    res = bootstrap(target, mcp_sync=False)
    assert res.ok
    for d in ("skills", "workflows", "rules", "tech-stack", "state", "brain", "runtime/policies"):
        assert (target / d).is_dir(), d
    assert (target / ".aizee-version").exists()
    assert (target / ".env.example").exists()
    for name in ("default.yaml", "guardian.yaml", "probity.yaml", "mcp_firewall.yaml"):
        assert (target / "runtime" / "policies" / name).exists(), name


def test_policies_copied_from_source(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "runtime" / "policies").mkdir(parents=True)
    (src / "runtime" / "policies" / "default.yaml").write_text("name: custom\nrules: []\n")
    target = tmp_path / "dst"
    bootstrap(target, source_root=src, mcp_sync=False)
    assert "name: custom" in (target / "runtime" / "policies" / "default.yaml").read_text()


def test_idempotent_no_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "root"
    bootstrap(target, mcp_sync=False)
    (target / ".aizee-version").write_text("CUSTOM\n")
    res = bootstrap(target, mcp_sync=False)
    assert ".aizee-version" in res.skipped_existing
    assert (target / ".aizee-version").read_text() == "CUSTOM\n"


def test_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "root"
    bootstrap(target, mcp_sync=False)
    (target / ".aizee-version").write_text("CUSTOM\n")
    res = bootstrap(target, force=True, mcp_sync=False)
    assert ".aizee-version" in res.written_files
    assert (target / ".aizee-version").read_text() != "CUSTOM\n"


def test_embedded_defaults_without_source(tmp_path: Path) -> None:
    target = tmp_path / "root"
    bootstrap(target, source_root=tmp_path / "nonexistent", mcp_sync=False)
    text = (target / "runtime" / "policies" / "default.yaml").read_text()
    assert "default_action" in text and "allow-reads" in text


def test_result_to_dict(tmp_path: Path) -> None:
    res = bootstrap(tmp_path / "r", mcp_sync=False)
    d = res.to_dict()
    assert d["ok"] is True and d["target"] == str(tmp_path / "r")


def test_mcp_sync_script_missing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    res = bootstrap(tmp_path / "r", source_root=src, mcp_sync=True)
    assert any("mcp_global_sync.py not found" in n for n in res.notes)


def _make_bundle(path: Path, files: dict[str, str]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_osroot_bundle_extracts(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "_osroot.tar.gz"
    _make_bundle(bundle, {"skills/demo/SKILL.md": "---\nname: demo\n---\n", "AGENTS.md": "agents"})
    monkeypatch.setattr(bs, "_OSROOT_ARCHIVE", bundle)
    target = tmp_path / "root"
    res = bootstrap(target, mcp_sync=False)
    assert res.osroot_files == 2
    assert (target / "skills" / "demo" / "SKILL.md").read_text() == "---\nname: demo\n---\n"
    assert (target / "AGENTS.md").read_text() == "agents"
    assert any("osroot bundle" in n for n in res.notes)


def test_osroot_bundle_idempotent_and_force(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "_osroot.tar.gz"
    _make_bundle(bundle, {"AGENTS.md": "new"})
    monkeypatch.setattr(bs, "_OSROOT_ARCHIVE", bundle)
    target = tmp_path / "root"
    bootstrap(target, mcp_sync=False)
    (target / "AGENTS.md").write_text("custom")
    res = bootstrap(target, mcp_sync=False)
    assert res.osroot_files == 0
    assert (target / "AGENTS.md").read_text() == "custom"
    res2 = bootstrap(target, force=True, mcp_sync=False)
    assert res2.osroot_files == 1
    assert (target / "AGENTS.md").read_text() == "new"


def test_osroot_bundle_missing_is_note(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bs, "_OSROOT_ARCHIVE", tmp_path / "nope.tar.gz")
    res = bootstrap(tmp_path / "root", mcp_sync=False)
    assert res.osroot_files == 0
    assert any("minimal install" in n for n in res.notes)


def test_osroot_bundle_dry_run(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "_osroot.tar.gz"
    _make_bundle(bundle, {"a.txt": "x", "b.txt": "y"})
    monkeypatch.setattr(bs, "_OSROOT_ARCHIVE", bundle)
    target = tmp_path / "root"
    res = bootstrap(target, dry_run=True, mcp_sync=False)
    assert res.osroot_files == 2
    assert not target.exists()


def test_mcp_sync_runs_script(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import MagicMock

    import runtime.bootstrap as bs

    src = tmp_path / "src"
    (src / "scripts").mkdir(parents=True)
    (src / "scripts" / "mcp_global_sync.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(bs.subprocess, "run", lambda *a, **k: MagicMock(returncode=0, stderr=""))
    res = bootstrap(tmp_path / "r1", source_root=src, mcp_sync=True)
    assert res.mcp_synced
    monkeypatch.setattr(bs.subprocess, "run", lambda *a, **k: MagicMock(returncode=1, stderr="boom"))
    res2 = bootstrap(tmp_path / "r2", source_root=src, mcp_sync=True)
    assert not res2.mcp_synced
    assert any("mcp sync failed" in n for n in res2.notes)

def test_extract_skips_write_when_extractfile_none(tmp_path: Path, monkeypatch) -> None:
    """Member whose extractfile returns None is counted but not written (48->39)."""
    class _Member:
        name = "x.md"

        def isfile(self) -> bool:
            return True

    class _Tar:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def getmembers(self):
            return [_Member()]

        def extractfile(self, m):
            return None

    archive = tmp_path / "fake.tar.gz"
    archive.write_bytes(b"x")
    monkeypatch.setattr(bs, "_OSROOT_ARCHIVE", archive)
    monkeypatch.setattr(bs.tarfile, "open", lambda *a, **k: _Tar())
    extracted, skipped = bs._extract_osroot(tmp_path / "out", force=False, dry_run=False)
    assert extracted == 1
    assert skipped == 0
    assert not (tmp_path / "out" / "x.md").exists()
