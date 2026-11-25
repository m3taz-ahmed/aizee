#!/usr/bin/env python3
"""Build ``runtime/_osroot.tar.gz`` — the doctrine content bundle shipped in the wheel.

The PyPI wheel carries the Python packages; this archive carries the OS-root
content tree (skills, workflows, rules, tech-stack, resources, characters,
design-library, scripts, docs, eval scenarios) plus root-level doctrine files.
``runtime/bootstrap.py`` extracts it so ``pip install aizee`` + ``aizee
bootstrap`` yields a full-capability install.

Usage: ``python scripts/build_osroot_bundle.py`` (run before ``uv build``).
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runtime" / "_osroot.tar.gz"

_DIRS = [
    "skills",
    "workflows",
    "routines",
    "rules",
    "tech-stack",
    "resources",
    "characters",
    "design-library",
    "scripts",
    "docs",
    "eval/scenarios",
]

_FILES = [
    "AGENTS.md",
    "global-roles.md",
    "global-workflow.md",
    "Memory.md",
    "README.md",
    "README-AR.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
    "skills-lock.json",
    "integrity.manifest",
    "deps.yaml",
    ".gitignore",
    "spec.md",
    "llms.txt",
    "SKILL.md",
]

_SKIP_DIRS = {"__pycache__", ".git", "node_modules", "temp", "state", "brain", "memory", "refs", "graphify-out", "dist", "build", "_bmad", "_bmad-output", ".agents"}
_SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".db", ".sqlite", ".sqlite3"}

# Media-light vendoring: raster/AV/print media under ``skills/`` never ships in
# the wheel — it would blow past PyPI's 100 MB limit. Users fetch it on demand
# via ``aizee skill media-fetch``. The suffix set lives canonically in
# ``runtime/skill_media.py``; ``theme-showcase.pdf`` stays because the
# theme-factory workflow requires it.
sys.path.insert(0, str(ROOT))

from runtime.skill_media import MEDIA_KEEP as _KEEP_NAMES  # noqa: E402
from runtime.skill_media import MEDIA_SUFFIXES as _MEDIA_SUFFIXES  # noqa: E402


def _is_media_excluded(p: Path) -> bool:
    if p.suffix.lower() not in _MEDIA_SUFFIXES:
        return False
    rel = p.relative_to(ROOT).as_posix()
    if not rel.startswith("skills/"):
        return False
    return p.name not in _KEEP_NAMES


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for rel in _DIRS:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.relative_to(ROOT).parts):
                continue
            if p.suffix.lower() in _SKIP_SUFFIX:
                continue
            if _is_media_excluded(p):
                continue
            files.append(p)
    for rel in _FILES:
        p = ROOT / rel
        if p.is_file():
            files.append(p)
    return files


def main() -> int:
    files = _iter_files()
    with tarfile.open(OUT, "w:gz", compresslevel=9) as tar:
        for p in files:
            tar.add(p, arcname=p.relative_to(ROOT).as_posix(), recursive=False)
    size = OUT.stat().st_size
    print(f"{OUT.name}: {len(files)} files, {size / 1024 / 1024:.2f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
