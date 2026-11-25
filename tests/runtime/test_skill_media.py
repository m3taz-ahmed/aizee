"""Tests for runtime/skill_media.py — on-demand media-light pack fetching."""

from __future__ import annotations

import gzip
import io
import json
import tarfile
import urllib.error
from pathlib import Path

import pytest

from runtime.skill_media import (
    MEDIA_KEEP,
    MEDIA_SUFFIXES,
    FetchResult,
    _download,
    _download_asset,
    _extract_pack,
    _fetch_error,
    _record_fetch,
    _sha256_file,
    _validated_members,
    fetch_many,
    fetch_pack,
    load_manifest,
    pack_status,
    release_urls,
    status_report,
    upstream_advice,
)

# ---------- fixtures helpers ----------


def _write_manifest(root: Path, packs: dict) -> Path:
    manifest = root / "skills" / "media-packs.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"version": 1, "packs": packs}), encoding="utf-8")
    return manifest


def _pack(root: Path, skill: str, files: dict[str, bytes], pack_sha: str = "") -> dict:
    entries = {}
    total = 0
    for rel, content in files.items():
        entries[rel] = {"bytes": len(content), "sha256": "x" * 64}
        total += len(content)
    return {
        "asset": f"aizee-media-{skill}.tar.gz",
        "sha256": pack_sha or "0" * 64,
        "bytes": total,
        "file_count": len(files),
        "files": entries,
    }


def _make_tarball(dest: Path, members: list[tuple[str, bytes]]) -> None:
    with dest.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for name, data in members:
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))


def _good_tarball(dest: Path, files: dict[str, bytes]) -> None:
    _make_tarball(dest, sorted(files.items()))


# ---------- load_manifest ----------


class TestLoadManifest:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert load_manifest(tmp_path) == {"version": 1, "packs": {}}

    def test_invalid_json(self, tmp_path: Path) -> None:
        manifest = tmp_path / "skills" / "media-packs.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("not json{", encoding="utf-8")
        assert load_manifest(tmp_path)["packs"] == {}

    def test_wrong_shape(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {})
        manifest = tmp_path / "skills" / "media-packs.json"
        manifest.write_text(json.dumps({"packs": [1, 2]}), encoding="utf-8")
        assert load_manifest(tmp_path)["packs"] == {}

    def test_valid(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"taste-skill": {"asset": "a"}})
        assert "taste-skill" in load_manifest(tmp_path)["packs"]


# ---------- pack_status / status_report ----------


class TestStatus:
    def test_missing(self, tmp_path: Path) -> None:
        pack = _pack(tmp_path, "s", {"skills/s/a.png": b"1"})
        st = pack_status(tmp_path, "s", pack, {"packs": {}})
        assert st.status == "missing" and st.files_present == 0

    def test_partial(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1", "skills/s/b.png": b"2"}
        pack = _pack(tmp_path, "s", files)
        (tmp_path / "skills" / "s").mkdir(parents=True)
        (tmp_path / "skills" / "s" / "a.png").write_bytes(b"1")
        st = pack_status(tmp_path, "s", pack, {"packs": {}})
        assert st.status == "partial" and st.files_present == 1

    def test_installed_with_state(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1"}
        pack = _pack(tmp_path, "s", files)
        (tmp_path / "skills" / "s").mkdir(parents=True)
        (tmp_path / "skills" / "s" / "a.png").write_bytes(b"1")
        state = {"packs": {"s": {"fetched_at": "2026-01-01"}}}
        st = pack_status(tmp_path, "s", pack, state)
        assert st.status == "installed" and st.fetched_at == "2026-01-01"

    def test_state_record_non_dict(self, tmp_path: Path) -> None:
        pack = _pack(tmp_path, "s", {"skills/s/a.png": b"1"})
        st = pack_status(tmp_path, "s", pack, {"packs": {"s": "bogus"}})
        assert st.fetched_at == ""

    def test_report_no_manifest(self, tmp_path: Path) -> None:
        report = status_report(tmp_path)
        assert not report.ok and "no media packs manifest" in report.error

    def test_report_unknown_skill(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"s": _pack(tmp_path, "s", {})})
        report = status_report(tmp_path, ["nope"])
        assert not report.ok and "unknown media pack" in report.error

    def test_report_all_and_filter(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"a": _pack(tmp_path, "a", {}), "b": _pack(tmp_path, "b", {})})
        report = status_report(tmp_path)
        assert report.ok and len(report.packs) == 2
        report = status_report(tmp_path, ["a"])
        assert report.ok and len(report.packs) == 1 and report.packs[0].skill == "a"
        assert report.packs[0].to_dict()["status"] == "missing"

    def test_report_to_dict(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"a": _pack(tmp_path, "a", {})})
        d = status_report(tmp_path).to_dict()
        assert d["ok"] is True and isinstance(d["packs"], list) and d["error"] == ""
        bad = status_report(tmp_path, ["zzz"]).to_dict()
        assert bad["ok"] is False and "unknown" in bad["error"]


# ---------- urls / advice ----------


class TestUrlsAndAdvice:
    def test_release_urls_order(self) -> None:
        urls = release_urls("o/r", "1.2.3", "a.tar.gz")
        assert urls[0] == "https://github.com/o/r/releases/download/v1.2.3/a.tar.gz"
        assert urls[1] == "https://github.com/o/r/releases/latest/download/a.tar.gz"

    def test_advice_no_skill_md(self, tmp_path: Path) -> None:
        assert upstream_advice(tmp_path, "ghost") == ""

    def test_advice_no_vendored_from(self, tmp_path: Path) -> None:
        d = tmp_path / "skills" / "s"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: s\n---\nbody", encoding="utf-8")
        assert upstream_advice(tmp_path, "s") == ""

    def test_advice_with_vendored_from(self, tmp_path: Path) -> None:
        d = tmp_path / "skills" / "s"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nvendored_from: https://github.com/x/y\nname: s\n---\n", encoding="utf-8"
        )
        assert "github.com/x/y" in upstream_advice(tmp_path, "s")

    def test_advice_read_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        d = tmp_path / "skills" / "s"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("x", encoding="utf-8")
        monkeypatch.setattr(Path, "read_text", lambda self, **kw: (_ for _ in ()).throw(OSError("boom")))
        assert upstream_advice(tmp_path, "s") == ""


# ---------- download / hashing ----------


class TestDownload:
    def test_download_writes_bytes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResponse:
            def __enter__(self):
                return io.BytesIO(b"payload")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResponse())
        dest = tmp_path / "out.bin"
        _download("https://x/y", dest)
        assert dest.read_bytes() == b"payload"

    def test_sha256_file(self, tmp_path: Path) -> None:
        import hashlib

        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        assert _sha256_file(f) == hashlib.sha256(b"abc").hexdigest()

    def test_download_asset_first_success(self, tmp_path: Path) -> None:
        dest = tmp_path / "a"
        url, err = _download_asset(["u1", "u2"], dest, lambda u, d: d.write_bytes(b"x"))
        assert url == "u1" and err == ""

    def test_download_asset_fallback(self, tmp_path: Path) -> None:
        dest = tmp_path / "a"

        def dl(u: str, d: Path) -> None:
            if u == "u1":
                raise urllib.error.URLError("nope")
            d.write_bytes(b"x")

        url, err = _download_asset(["u1", "u2"], dest, dl)
        assert url == "u2" and err == ""

    def test_download_asset_all_fail(self, tmp_path: Path) -> None:
        def dl(u: str, d: Path) -> None:
            raise OSError("dead")

        url, err = _download_asset(["u1", "u2"], tmp_path / "a", dl)
        assert url == "" and "dead" in err


# ---------- tar validation / extraction ----------


class TestTar:
    def _tar_with(self, tmp_path: Path, members: list[tuple[str, bytes]]) -> Path:
        dest = tmp_path / "p.tar.gz"
        _make_tarball(dest, members)
        return dest

    def test_valid_members(self, tmp_path: Path) -> None:
        tarball = self._tar_with(tmp_path, [("skills/s/a.png", b"1")])
        with tarfile.open(tarball, "r:gz") as tar:
            members = _validated_members(tar)
        assert len(members) == 1

    def test_reject_traversal(self, tmp_path: Path) -> None:
        tarball = self._tar_with(tmp_path, [("skills/../evil", b"1")])
        with tarfile.open(tarball, "r:gz") as tar, pytest.raises(ValueError, match="unsafe"):
            _validated_members(tar)

    def test_reject_absolute(self, tmp_path: Path) -> None:
        tarball = self._tar_with(tmp_path, [("/skills/s/a", b"1")])
        with tarfile.open(tarball, "r:gz") as tar, pytest.raises(ValueError, match="unsafe"):
            _validated_members(tar)

    def test_reject_backslash(self, tmp_path: Path) -> None:
        tarball = self._tar_with(tmp_path, [("skills\\s\\a", b"1")])
        with tarfile.open(tarball, "r:gz") as tar, pytest.raises(ValueError, match="unsafe"):
            _validated_members(tar)

    def test_reject_outside_skills(self, tmp_path: Path) -> None:
        tarball = self._tar_with(tmp_path, [("etc/passwd", b"1")])
        with tarfile.open(tarball, "r:gz") as tar, pytest.raises(ValueError, match="outside"):
            _validated_members(tar)

    def test_reject_symlink(self, tmp_path: Path) -> None:
        dest = tmp_path / "p.tar.gz"
        with dest.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w") as tar:
                    info = tarfile.TarInfo("skills/s/link")
                    info.type = tarfile.SYMTYPE
                    info.linkname = "/etc"
                    tar.addfile(info)
        with tarfile.open(dest, "r:gz") as tar, pytest.raises(ValueError, match="refused"):
            _validated_members(tar)

    def test_extract_pack(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"xx", "skills/s/deep/b.jpg": b"yy"}
        tarball = tmp_path / "p.tar.gz"
        _good_tarball(tarball, files)
        count, written = _extract_pack(tarball, tmp_path)
        assert count == 2 and written == 4
        assert (tmp_path / "skills" / "s" / "deep" / "b.jpg").read_bytes() == b"yy"

    def test_dir_members_skipped(self, tmp_path: Path) -> None:
        dest = tmp_path / "p.tar.gz"
        with dest.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w") as tar:
                    d = tarfile.TarInfo("skills/s")
                    d.type = tarfile.DIRTYPE
                    tar.addfile(d)
                    info = tarfile.TarInfo("skills/s/a.png")
                    data = b"1"
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
        with tarfile.open(dest, "r:gz") as tar:
            members = _validated_members(tar)
        assert len(members) == 1 and members[0].isfile()

    def test_extract_skips_none_stream(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = {"skills/s/a.png": b"xx"}
        tarball = tmp_path / "p.tar.gz"
        _good_tarball(tarball, files)
        monkeypatch.setattr(tarfile.TarFile, "extractfile", lambda self, m: None)
        count, _written = _extract_pack(tarball, tmp_path)
        assert count == 0


# ---------- record / error ----------


class TestRecordAndError:
    def test_record_fetch_roundtrip(self, tmp_path: Path) -> None:
        pack = {"asset": "a.tar.gz", "sha256": "ab"}
        _record_fetch(tmp_path, "s", pack, "http://u", 7)
        state = json.loads((tmp_path / "state" / "skill-media.json").read_text(encoding="utf-8"))
        rec = state["packs"]["s"]
        assert rec["file_count"] == 7 and rec["source_url"] == "http://u"

    def test_record_fetch_existing_corrupt_state(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "skill-media.json").write_text("{bad", encoding="utf-8")
        _record_fetch(tmp_path, "s", {"asset": "a", "sha256": "x"}, "u", 1)
        state = json.loads((state_dir / "skill-media.json").read_text(encoding="utf-8"))
        assert state["packs"]["s"]["file_count"] == 1

    def test_load_state_wrong_shape(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "skill-media.json").write_text(json.dumps({"packs": [1]}), encoding="utf-8")
        _record_fetch(tmp_path, "s", {"asset": "a", "sha256": "x"}, "u", 1)
        assert (state_dir / "skill-media.json").exists()

    def test_fetch_error_includes_advice(self, tmp_path: Path) -> None:
        d = tmp_path / "skills" / "s"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("vendored_from: https://x/y\n", encoding="utf-8")
        res = _fetch_error(tmp_path, "s", "boom")
        assert not res.ok and res.error == "boom" and "x/y" in res.advice


# ---------- fetch_pack / fetch_many ----------


class TestFetch:
    def test_no_manifest(self, tmp_path: Path) -> None:
        res = fetch_pack(tmp_path, "s", "1.0.0")
        assert not res.ok and "no media packs manifest" in res.error

    def test_unknown_pack(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"a": _pack(tmp_path, "a", {})})
        res = fetch_pack(tmp_path, "zzz", "1.0.0")
        assert not res.ok and "unknown media pack" in res.error

    def test_download_failure(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, {"s": _pack(tmp_path, "s", {})})

        def dl(u: str, d: Path) -> None:
            raise urllib.error.URLError("offline")

        res = fetch_pack(tmp_path, "s", "1.0.0", downloader=dl)
        assert not res.ok and "download failed" in res.error

    def test_sha_mismatch_fail_closed(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1"}
        _write_manifest(tmp_path, {"s": _pack(tmp_path, "s", files, pack_sha="f" * 64)})

        def dl(u: str, d: Path) -> None:
            _good_tarball(d, files)

        res = fetch_pack(tmp_path, "s", "1.0.0", downloader=dl)
        assert not res.ok and "sha256 mismatch" in res.error

    def test_missing_manifest_sha_fail_closed(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1"}
        pack = _pack(tmp_path, "s", files, pack_sha="f" * 64)
        pack["sha256"] = ""
        _write_manifest(tmp_path, {"s": pack})

        def dl(u: str, d: Path) -> None:
            _good_tarball(d, files)

        res = fetch_pack(tmp_path, "s", "1.0.0", downloader=dl)
        assert not res.ok and "sha256 mismatch" in res.error
        assert not (tmp_path / "skills" / "s" / "a.png").exists()

    def test_extract_failure(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1"}
        # valid gzip wrapping non-tar bytes — sha passes, tar parsing fails
        corrupt = gzip.compress(b"this is not a tar", mtime=0)
        probe = tmp_path / "probe.bin"
        probe.write_bytes(corrupt)
        pack = _pack(tmp_path, "s", files, pack_sha=_sha256_file(probe))
        probe.unlink()
        _write_manifest(tmp_path, {"s": pack})

        def dl(u: str, d: Path) -> None:
            d.write_bytes(corrupt)

        res = fetch_pack(tmp_path, "s", "1.0.0", downloader=dl)
        assert not res.ok and "extract failed" in res.error

    def test_success_end_to_end(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"xx", "skills/s/sub/b.jpg": b"yy"}
        probe = tmp_path / "probe.tar.gz"
        _good_tarball(probe, files)
        pack = _pack(tmp_path, "s", files, pack_sha=_sha256_file(probe))
        _write_manifest(tmp_path, {"s": pack})
        probe.unlink()

        seen_urls: list[str] = []

        def dl(u: str, d: Path) -> None:
            seen_urls.append(u)
            _good_tarball(d, files)

        res = fetch_pack(tmp_path, "s", "6.14.0", downloader=dl)
        assert res.ok and res.files == 2 and res.bytes_written == 4
        assert "v6.14.0" in res.url and seen_urls[0].endswith("v6.14.0/aizee-media-s.tar.gz")
        assert (tmp_path / "skills" / "s" / "a.png").read_bytes() == b"xx"
        state = json.loads((tmp_path / "state" / "skill-media.json").read_text(encoding="utf-8"))
        assert state["packs"]["s"]["file_count"] == 2
        assert res.to_dict()["ok"] is True

    def test_fallback_url_used(self, tmp_path: Path) -> None:
        files = {"skills/s/a.png": b"1"}
        probe = tmp_path / "probe.tar.gz"
        _good_tarball(probe, files)
        pack = _pack(tmp_path, "s", files, pack_sha=_sha256_file(probe))
        _write_manifest(tmp_path, {"s": pack})
        probe.unlink()

        def dl(u: str, d: Path) -> None:
            if "/download/v" in u:
                raise urllib.error.URLError("404")
            _good_tarball(d, files)

        res = fetch_pack(tmp_path, "s", "9.9.9", downloader=dl)
        assert res.ok and "latest" in res.url

    def test_fetch_many_all_and_list(self, tmp_path: Path) -> None:
        files = {"skills/a/a.png": b"1"}
        probe = tmp_path / "probe.tar.gz"
        _good_tarball(probe, files)
        sha = _sha256_file(probe)
        probe.unlink()
        packs = {
            "a": _pack(tmp_path, "a", files, pack_sha=sha),
            "b": _pack(tmp_path, "b", files, pack_sha=sha),
        }
        _write_manifest(tmp_path, packs)

        def dl(u: str, d: Path) -> None:
            _good_tarball(d, files)

        results = fetch_many(tmp_path, ["__all__"], "1.0.0", downloader=dl)
        assert len(results) == 2 and all(r.ok for r in results)
        results = fetch_many(tmp_path, ["a"], "1.0.0", downloader=dl)
        assert len(results) == 1 and results[0].skill == "a"


# ---------- constants sanity ----------


class TestConstants:
    def test_suffixes_cover_gitignore_set(self) -> None:
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".mp4", ".mov", ".wav", ".mp3", ".pdf"):
            assert ext in MEDIA_SUFFIXES

    def test_keep_exception(self) -> None:
        assert "theme-showcase.pdf" in MEDIA_KEEP

    def test_result_defaults(self) -> None:
        r = FetchResult(ok=True, skill="x")
        assert r.files == 0 and r.error == "" and r.to_dict()["skill"] == "x"


# ---------- skill_lock media-light hashing ----------


class TestLockMediaLight:
    def test_folder_hash_skips_media(self, tmp_path: Path) -> None:
        from runtime.skill_lock import folder_hash

        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("x", encoding="utf-8")
        base = folder_hash(d)
        (d / "img.png").write_bytes(b"123")
        assert folder_hash(d) == base
        (d / "notes.txt").write_text("y", encoding="utf-8")
        assert folder_hash(d) != base

    def test_folder_hash_keeps_exceptions(self, tmp_path: Path) -> None:
        from runtime.skill_lock import folder_hash

        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("x", encoding="utf-8")
        base = folder_hash(d)
        (d / "theme-showcase.pdf").write_bytes(b"pdf")
        assert folder_hash(d) != base
