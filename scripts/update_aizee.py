#!/usr/bin/env python3
"""Portable aiZee sync: source root -> sibling ``aizee`` deployment mirror.

Cross-platform equivalent of ``scripts/update_aizee.bat`` (which uses
robocopy and only runs on Windows). Same semantics, stdlib only:

- ``/MIR`` behavior — copy new/changed files, delete files missing from
  the source (stale-path cleanup).
- Same exclusion lists for runtime state, secrets, regenerable output.
- Same guards: target must exist and look like an aiZee deployment
  (``pyproject.toml`` + ``config.py``), self-mirror refused.

Usage::

    python scripts/update_aizee.py            # apply
    python scripts/update_aizee.py --dry-run  # report only
    AIZEE_DEPLOY=/opt/aizee python scripts/update_aizee.py
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".ai", "temp", "state", "brain", "backups", "graphify-out",
    "htmlcov", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__",
    "node_modules", ".venv", "venv", "abstracts", ".idea", ".claude",
    ".devin", "tools", "archives",
}
EXCLUDE_FILES = {
    ".env", ".coverage", ".aizee-version", "settings.json",
    "settings.local.json", "mcp_config.local.json", "config.local.json",
    "implementation_plan.md", "DEEP_AUDIT_PROMPT.md", "GRAPH_REPORT.md",
    "GAMES.md",
}
EXCLUDE_GLOBS = ("*.pyc", "*.pyo", "*.log", "notes-*.md")

# Sub-trees mirrored separately with lighter exclusions (config/skills only).
SUB_TREES = {
    ".claude": {"exclude_dirs": {"__pycache__"},
                "exclude_files": {"settings.json", "settings.local.json", "*.pyc", "*.pyo"}},
    ".devin": {"exclude_dirs": {"__pycache__"},
               "exclude_files": {"mcp_config.local.json", "config.local.json", "*.pyc", "*.pyo"}},
}


def _excluded_dir(rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return False
    # never descend into junction'd skill mirrors under .agents/skills
    if parts[:2] == (".agents", "skills"):
        return True
    return any(part in EXCLUDE_DIRS for part in parts)


def _excluded_file(name: str, extra: set[str]) -> bool:
    import fnmatch

    all_ex = EXCLUDE_FILES | extra | set(EXCLUDE_GLOBS)
    return any(fnmatch.fnmatch(name, pat) for pat in all_ex)


def mirror(src: Path, dst: Path, *, dry_run: bool, extra_files: set[str] | None = None,
           exclude_dirs: set[str] | None = None) -> dict[str, int]:
    """Robocopy /MIR equivalent: copy changed, delete extras."""
    stats = {"copied": 0, "removed": 0, "skipped": 0}
    skip_dirs = (exclude_dirs or EXCLUDE_DIRS)
    skip_files = extra_files or set()
    seen: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(src):
        rel_dir = Path(dirpath).relative_to(src)
        dirnames[:] = [
            d for d in dirnames
            if not _excluded_dir(rel_dir / d) and d not in skip_dirs
        ]
        target_dir = dst / rel_dir
        for name in filenames:
            rel = rel_dir / name
            seen.add(str(rel).replace(os.sep, "/"))  # excluded files are kept, not pruned
            if _excluded_file(name, skip_files):
                stats["skipped"] += 1
                continue
            s = Path(dirpath) / name
            t = target_dir / name
            if t.exists() and filecmp.cmp(s, t, shallow=False):
                stats["skipped"] += 1
                continue
            stats["copied"] += 1
            if not dry_run:
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, t)

    # prune: anything in dst not seen in src gets removed — but excluded
    # dirs are left untouched in BOTH trees (robocopy /XD semantics).
    # dirnames filtering only works top-down; track visited dirs for the
    # empty-dir sweep instead of re-walking junction'd trees.
    visited_dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(dst):
        rel_dir = Path(dirpath).relative_to(dst)
        dirnames[:] = [
            d for d in dirnames
            if not _excluded_dir(rel_dir / d) and d not in skip_dirs
        ]
        visited_dirs.append(Path(dirpath))
        for name in filenames:
            rel = rel_dir / name
            if _excluded_file(name, skip_files):  # /XF: never delete excluded patterns
                continue
            if str(rel).replace(os.sep, "/") not in seen:
                stats["removed"] += 1
                if not dry_run:
                    try:
                        (Path(dirpath) / name).unlink()
                    except OSError as exc:
                        print(f"  warn: cannot remove {rel}: {exc}")
    if not dry_run:
        for d in reversed(visited_dirs):
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                continue
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="aiZee source->mirror sync (portable)")
    ap.add_argument("--dry-run", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    source = Path(__file__).resolve().parent.parent
    target = Path(os.environ.get("AIZEE_DEPLOY", source.parent / "aizee")).resolve()

    print(f"=== aiZee Sync: {source} -> {target} ===")
    if not target.is_dir():
        print(f"ERROR: target {target} does not exist (set AIZEE_DEPLOY)")
        return 1
    if source == target:
        print("Refusing self-mirror — run from the source root's scripts/.")
        return 1
    for marker in ("pyproject.toml", "config.py"):
        if not (target / marker).exists():
            print(f"ERROR: {target} lacks {marker} — refusing to mirror into a non-aiZee dir.")
            return 1

    main_stats = mirror(source, target, dry_run=args.dry_run)
    print(f"main:   copied={main_stats['copied']} removed={main_stats['removed']} "
          f"unchanged={main_stats['skipped']}")
    for sub, spec in SUB_TREES.items():
        s_sub, t_sub = source / sub, target / sub
        if not s_sub.is_dir():
            continue
        t_sub.mkdir(parents=True, exist_ok=True)
        st = mirror(s_sub, t_sub, dry_run=args.dry_run,
                    extra_files=set(spec["exclude_files"]),
                    exclude_dirs=set(spec["exclude_dirs"]) | {".git"})
        print(f"{sub}: copied={st['copied']} removed={st['removed']} unchanged={st['skipped']}")

    print("=== Sync Complete ===" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
