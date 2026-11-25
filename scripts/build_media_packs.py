#!/usr/bin/env python3
"""Build per-skill media packs (``dist/media/aizee-media-<skill>.tar.gz``).

Vendored skill media (raster/AV/print) stays out of git per the media-light
policy in ``.gitignore`` — this script packs exactly those gitignored files
into per-skill tarballs plus a committed manifest (``skills/media-packs.json``)
so end users can fetch them on demand via ``aizee skill media-fetch``.

Media exists only on the maintainer's source tree (gitignored), so this runs
as part of the LOCAL release flow (``scripts/release.py``), never in CI —
a clean clone has no media. When no media files are found the script exits 0
with a loud warning and writes nothing, so releases from media-less machines
skip the upload step instead of shipping empty packs.

Usage: ``python scripts/build_media_packs.py`` (run before the release upload).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runtime.skill_media import MEDIA_SUFFIXES  # noqa: E402

OUT_DIR = ROOT / "dist" / "media"
MANIFEST = ROOT / "skills" / "media-packs.json"

# Never pack upstream repo metadata, even though ``.gitignore`` covers it —
# these paths are noise, not skill content.
_SKIP_PARTS = {".github", "__pycache__"}

MANIFEST_VERSION = 1


def _gitignored(paths: list[Path]) -> set[Path]:
    """Return the subset of ``paths`` that git ignores (batch check-ignore).

    The ``.gitignore`` media-light block (incl. the theme-showcase.pdf negation)
    is the single source of truth for what counts as packable media.
    """
    if not paths:
        return set()
    rels = [p.relative_to(ROOT).as_posix() for p in paths]
    # Bytes, not text=True — text mode translates "\n" to "\r\n" on Windows,
    # and the trailing CR silently breaks every gitignore match.
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input=("\n".join(rels) + "\n").encode("utf-8"),
        capture_output=True,
        cwd=ROOT,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    ignored = {line.strip() for line in out.splitlines() if line.strip()}
    return {p for p, rel in zip(paths, rels, strict=True) if rel in ignored}


def scan_media(root: Path = ROOT) -> dict[str, list[Path]]:
    """Group gitignored media files under ``skills/`` by skill directory."""
    candidates: list[Path] = []
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return {}
    for p in sorted(skills_root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in _SKIP_PARTS for part in rel_parts):
            continue
        candidates.append(p)
    packs: dict[str, list[Path]] = {}
    for p in sorted(_gitignored(candidates)):
        rel = p.relative_to(root)
        if len(rel.parts) < 3:
            continue
        packs.setdefault(rel.parts[1], []).append(p)
    return packs


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_pack(out_path: Path, files: list[Path], root: Path) -> None:
    """Write a reproducible tarball — fixed gzip/tar metadata so identical
    input bytes yield identical pack bytes (and a stable manifest sha256)
    across machines and rebuilds."""
    with (
        out_path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for p in files:
            arcname = p.relative_to(root).as_posix()
            info = tarfile.TarInfo(arcname)
            info.size = p.stat().st_size
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with p.open("rb") as fh:
                tar.addfile(info, fh)


def build_packs(root: Path = ROOT, out_dir: Path = OUT_DIR) -> dict[str, object]:
    """Build one tarball per skill; return the manifest dict."""
    packs = scan_media(root)
    manifest: dict[str, object] = {
        "version": MANIFEST_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "packs": {},
    }
    if not packs:
        print("WARNING: no gitignored skill media found — nothing to pack")
        print("(media only exists on the maintainer source tree; clean clones skip)")
        return manifest
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_entries: dict[str, object] = {}
    for skill in sorted(packs):
        files = packs[skill]
        asset = f"aizee-media-{skill}.tar.gz"
        out_path = out_dir / asset
        _write_pack(out_path, files, root)
        entries: dict[str, object] = {}
        total_bytes = 0
        for p in files:
            rel = p.relative_to(root).as_posix()
            size = p.stat().st_size
            total_bytes += size
            entries[rel] = {"bytes": size, "sha256": _sha256(p)}
        pack_entries[skill] = {
            "asset": asset,
            "sha256": _sha256(out_path),
            "bytes": total_bytes,
            "file_count": len(files),
            "files": entries,
        }
        print(f"{asset}: {len(files)} files, {total_bytes / 1024 / 1024:.1f} MiB")
    manifest["packs"] = pack_entries
    return manifest


def write_manifest(manifest: dict[str, object], path: Path = MANIFEST) -> bool:
    """Write the committed manifest; returns False when there is nothing to write."""
    packs = manifest.get("packs")
    if not packs:
        return False
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{path.name}: {len(packs)} packs recorded")
    return True


def main() -> int:
    manifest = build_packs()
    write_manifest(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
