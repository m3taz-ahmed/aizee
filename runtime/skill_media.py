"""On-demand skill media packs — the fetch side of media-light vendoring.

Vendored skill media (raster/AV/print) is excluded from git per the
media-light policy in ``.gitignore``; it ships as per-skill tarballs attached
to GitHub releases. This module:

- reads the committed manifest ``skills/media-packs.json`` (pack names,
  per-file sizes/hashes, pack sha256 — the trust anchor, distributed with
  the repo/bundle itself),
- reports per-skill media status offline (``status_report``),
- downloads packs on demand (``fetch_pack``) from the exact-version release,
  falling back to the latest release, verifying the pack sha256 before
  extraction (fail-closed) and validating every tar member against path
  traversal,
- records installs in the machine-local ``state/skill-media.json``.

When no release asset is reachable, ``upstream_advice`` points the user at
the skill's ``vendored_from`` source so the media can be re-fetched manually.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GITHUB_REPO = "m3taz-ahmed/aizee"
MANIFEST_PATH = "skills/media-packs.json"
STATE_PATH = "state/skill-media.json"
MANIFEST_VERSION = 1
_CHUNK = 1024 * 1024
_TIMEOUT = 60

# Media-light vendoring suffixes — the single canonical home. Keep in sync with
# the media-light block in ``.gitignore``; ``scripts/build_media_packs.py`` and
# ``scripts/build_osroot_bundle.py`` mirror/import this set, and
# ``runtime/skill_lock.py`` uses it so lock hashes cover exactly what git covers.
MEDIA_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif",
    ".mp4", ".mov", ".wav", ".mp3", ".pdf",
}

# Media-suffix files that ARE committed (gitignore negations) — keyed by file
# name, not suffix-skipped anywhere. theme-factory's workflow requires the PDF.
MEDIA_KEEP = {"theme-showcase.pdf"}

_STATUS_INSTALLED = "installed"
_STATUS_PARTIAL = "partial"
_STATUS_MISSING = "missing"


@dataclass
class PackStatus:
    skill: str
    status: str
    files_expected: int
    files_present: int
    bytes: int
    asset: str
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "status": self.status,
            "files_expected": self.files_expected,
            "files_present": self.files_present,
            "bytes": self.bytes,
            "asset": self.asset,
            "fetched_at": self.fetched_at,
        }


@dataclass
class FetchResult:
    ok: bool
    skill: str
    files: int = 0
    bytes_written: int = 0
    url: str = ""
    error: str = ""
    advice: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skill": self.skill,
            "files": self.files,
            "bytes_written": self.bytes_written,
            "url": self.url,
            "error": self.error,
            "advice": self.advice,
        }


@dataclass
class MediaReport:
    ok: bool
    packs: list[PackStatus] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "packs": [p.to_dict() for p in self.packs],
        }


def load_manifest(root: Path) -> dict[str, Any]:
    """Read ``skills/media-packs.json``; empty packs when absent/invalid."""
    path = root / MANIFEST_PATH
    if not path.exists():
        return {"version": MANIFEST_VERSION, "packs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": MANIFEST_VERSION, "packs": {}}
    if not isinstance(data, dict) or not isinstance(data.get("packs"), dict):
        return {"version": MANIFEST_VERSION, "packs": {}}
    return data


def _load_state(root: Path) -> dict[str, Any]:
    path = root / STATE_PATH
    if not path.exists():
        return {"version": 1, "packs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "packs": {}}
    if not isinstance(data, dict) or not isinstance(data.get("packs"), dict):
        return {"version": 1, "packs": {}}
    return data


def _write_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def pack_status(root: Path, skill: str, pack: dict[str, Any], state: dict[str, Any]) -> PackStatus:
    files = pack.get("files", {})
    present = sum(1 for rel in files if (root / rel).is_file())
    expected = int(pack.get("file_count", len(files)))
    if present == 0:
        status = _STATUS_MISSING
    elif present < expected:
        status = _STATUS_PARTIAL
    else:
        status = _STATUS_INSTALLED
    fetched = ""
    rec = state.get("packs", {}).get(skill, {})
    if isinstance(rec, dict):
        fetched = str(rec.get("fetched_at", ""))
    return PackStatus(
        skill=skill,
        status=status,
        files_expected=expected,
        files_present=present,
        bytes=int(pack.get("bytes", 0)),
        asset=str(pack.get("asset", "")),
        fetched_at=fetched,
    )


def status_report(root: Path, skills: list[str] | None = None) -> MediaReport:
    """Offline per-skill media status from the committed manifest."""
    manifest = load_manifest(root)
    packs = manifest.get("packs", {})
    if not packs:
        return MediaReport(ok=False, error="no media packs manifest — nothing to fetch")
    state = _load_state(root)
    wanted = skills if skills else sorted(packs)
    unknown = [s for s in wanted if s not in packs]
    if unknown:
        return MediaReport(
            ok=False,
            error=f"unknown media pack(s): {', '.join(unknown)} — available: {', '.join(sorted(packs))}",
        )
    report = MediaReport(ok=True)
    for skill in wanted:
        report.packs.append(pack_status(root, skill, packs[skill], state))
    return report


def release_urls(repo: str, version: str, asset: str) -> list[str]:
    """Exact-version asset URL first, then the latest-release fallback."""
    base = f"https://github.com/{repo}/releases"
    urls = [f"{base}/download/v{version}/{asset}"]
    urls.append(f"{base}/latest/download/{asset}")
    return urls


def upstream_advice(root: Path, skill: str) -> str:
    """Point at the skill's ``vendored_from`` upstream when downloads fail."""
    skill_md = root / "skills" / skill / "SKILL.md"
    if not skill_md.exists():
        return ""
    try:
        head = skill_md.read_text(encoding="utf-8", errors="replace")[:3000]
    except OSError:
        return ""
    match = re.search(r"^vendored_from:\s*(\S+)", head, re.MULTILINE)
    if not match:
        return ""
    return f"media can also be re-fetched manually from upstream: {match.group(1)}"


def _download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "aizee-media-fetch"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response, dest.open("wb") as fh:
        shutil.copyfileobj(response, fh, _CHUNK)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """Reject anything but in-tree regular files (path-traversal defense)."""
    members: list[tarfile.TarInfo] = []
    for member in tar.getmembers():
        name = member.name
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts or "\\" in name:
            raise ValueError(f"unsafe tar member: {name}")
        if not name.startswith("skills/"):
            raise ValueError(f"tar member outside skills/: {name}")
        if member.islnk() or member.issym() or member.isdev():
            raise ValueError(f"link/device tar member refused: {name}")
        if member.isfile():
            members.append(member)
    return members


def _extract_pack(tarball: Path, root: Path) -> tuple[int, int]:
    files = 0
    written = 0
    with tarfile.open(tarball, "r:gz") as tar:
        members = _validated_members(tar)
        for member in members:
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is None:
                continue
            with target.open("wb") as dest:
                shutil.copyfileobj(src, dest, _CHUNK)
            files += 1
            written += int(member.size)
    return files, written


def _record_fetch(root: Path, skill: str, pack: dict[str, Any], url: str, files: int) -> None:
    state = _load_state(root)
    state.setdefault("packs", {})[skill] = {
        "asset": str(pack.get("asset", "")),
        "sha256": str(pack.get("sha256", "")),
        "file_count": files,
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_state(root, state)


def _fetch_error(root: Path, skill: str, error: str) -> FetchResult:
    return FetchResult(ok=False, skill=skill, error=error, advice=upstream_advice(root, skill))


def _download_asset(
    urls: list[str],
    dest: Path,
    downloader: Any,
) -> tuple[str, str]:
    """Try each release URL in order; return (used_url, last_error)."""
    last_error = ""
    for url in urls:
        try:
            downloader(url, dest)
            return url, ""
        except (urllib.error.URLError, OSError) as exc:
            last_error = str(exc)
    return "", last_error


def fetch_pack(
    root: Path,
    skill: str,
    version: str,
    *,
    repo: str = GITHUB_REPO,
    downloader: Any = _download,
) -> FetchResult:
    """Download, verify and extract one skill's media pack (fail-closed)."""
    manifest = load_manifest(root)
    packs = manifest.get("packs", {})
    if not packs:
        return _fetch_error(root, skill, "no media packs manifest — nothing to fetch")
    pack = packs.get(skill)
    if not isinstance(pack, dict):
        return _fetch_error(
            root,
            skill,
            f"unknown media pack: {skill} — available: {', '.join(sorted(packs))}",
        )
    asset = str(pack.get("asset", ""))
    expected = str(pack.get("sha256", ""))
    tmpdir = Path(tempfile.mkdtemp(prefix="aizee-media-"))
    try:
        tarball = tmpdir / asset
        used_url, last_error = _download_asset(release_urls(repo, version, asset), tarball, downloader)
        if not used_url or not tarball.exists():
            return _fetch_error(root, skill, f"download failed: {last_error or 'no asset retrieved'}")
        if not expected or _sha256_file(tarball) != expected:
            return _fetch_error(root, skill, "sha256 mismatch — pack refused (fail-closed)")
        try:
            files, written = _extract_pack(tarball, root)
        except (tarfile.TarError, ValueError, OSError) as exc:
            return _fetch_error(root, skill, f"extract failed: {exc}")
        _record_fetch(root, skill, pack, used_url, files)
        return FetchResult(ok=True, skill=skill, files=files, bytes_written=written, url=used_url)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def fetch_many(
    root: Path,
    skills: list[str],
    version: str,
    *,
    repo: str = GITHUB_REPO,
    downloader: Any = _download,
) -> list[FetchResult]:
    """Fetch several packs; ``--all`` expands to every manifest pack."""
    manifest = load_manifest(root)
    packs = manifest.get("packs", {})
    if skills == ["__all__"]:
        skills = sorted(packs)
    return [fetch_pack(root, skill, version, repo=repo, downloader=downloader) for skill in skills]
