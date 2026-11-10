#!/usr/bin/env python3
"""aiZee release script — bump version, validate, test, tag, push, publish.

Ships a release in one command, run from the DEV root (.ai), never the
deployed aizee mirror:

    python scripts/release.py --version 6.8.0 --title "short release title"

Flow: bump all version-bearing files -> validate-globals (catches a missed
file automatically) -> full test suite -> commit -> tag -> push -> gh release.
Use --dry-run to preview every write without touching anything.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

# Files where replacing the OLD version literal with NEW is safe — the
# version appears only as display/config metadata in each.
# NOTE: aizee_mcp/config.json is intentionally EXCLUDED — its version
# literals are external npm pins (e.g. rea-agents@x.y.z), not aiZee's.
PLAIN_BUMP = [
    "pyproject.toml",
    "manifest.json",
    "plugin.json",
    "config.py",
    "scripts/validate-globals.py",
    "scripts/validate-globals.ps1",
]
README_FILES = ["README.md", "README-AR.md"]

# Relative links/images break on PyPI — every README link must be absolute.
REL_LINK_RE = re.compile(r"\]\((?!https?://|#|mailto:)[^)\s]+\)|<img[^>]+src=\"(?!https?://)[^\"]+\"")


def _err(msg: str) -> None:
    print(f"[release] ERROR: {msg}")


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"[release] $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, capture_output=False, text=True, check=check)


def _current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"\n]+)"', text, re.MULTILINE)
    if not match:
        sys.exit("[release] ERROR: could not read version from pyproject.toml")
    return match.group(1)


def _bump_markdown(path: Path, new: str, dry_run: bool) -> bool:
    """Bump every x.y.z inside badge/alt/Version lines (fixes stale alts too)."""
    changed = False
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if ("badge/" in line or "Version" in line or "الإصدار" in line) and VERSION_RE.search(line):
            out.append(VERSION_RE.sub(new, line))
            changed = True
        else:
            out.append(line)
    if changed and not dry_run:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def _bump_changelog(path: Path, new: str, title: str, today: str, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    if f"## [{new}]" in text:
        return False
    entry = f"\n\n## [{new}] - {today} ({title})\n"
    updated = text.replace("# Changelog\n", f"# Changelog\n{entry}\n", 1)
    if updated == text:
        sys.exit("[release] ERROR: '# Changelog' header not found in CHANGELOG.md")
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def _check_readme_links() -> list[str]:
    """Fail the release if any README link/image is relative (PyPI breaks them)."""
    bad = []
    for rel in README_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in REL_LINK_RE.finditer(line):
                bad.append(f"{rel}:{i}: {m.group(0)[:80]}")
    return bad


def bump(old: str, new: str, title: str, today: str, dry_run: bool) -> list[str]:
    touched = []
    for rel in PLAIN_BUMP:
        path = ROOT / rel
        if not path.exists():
            print(f"[release] warn: {rel} missing, skipped")
            continue
        text = path.read_text(encoding="utf-8")
        bumped = text.replace(old, new)
        if rel == "manifest.json":
            bumped = re.sub(r'"updated"\s*:\s*"[^"]+"', f'"updated": "{today}"', bumped)
        if bumped != text:
            if not dry_run:
                path.write_text(bumped, encoding="utf-8")
            touched.append(rel)
    for rel in README_FILES:
        path = ROOT / rel
        if path.exists() and _bump_markdown(path, new, dry_run):
            touched.append(rel)
    if _bump_changelog(ROOT / "CHANGELOG.md", new, title, today, dry_run):
        touched.append("CHANGELOG.md")
    print(f"[release] bumped: {', '.join(touched) or 'nothing'}")
    return touched


def main() -> int:
    ap = argparse.ArgumentParser(description="aiZee release — bump, validate, tag, push, publish")
    ap.add_argument("--version", required=True, help="New version, e.g. 6.8.0")
    ap.add_argument("--title", default="maintenance release", help="CHANGELOG heading title")
    ap.add_argument("--dry-run", action="store_true", help="Preview writes; no side effects")
    ap.add_argument("--skip-tests", action="store_true", help="Skip the full test suite")
    ap.add_argument("--no-push", action="store_true", help="Commit + tag locally; do not push")
    ap.add_argument("--no-release", action="store_true", help="Do not create the GitHub release")
    ap.add_argument("--publish-pypi", action="store_true", help="uv build + uv publish to PyPI (needs UV_PUBLISH_TOKEN)")
    args = ap.parse_args()

    if not VERSION_RE.fullmatch(args.version):
        _err(f"--version must be x.y.z, got {args.version!r}")
        return 1
    old, new, today = _current_version(), args.version, date.today().isoformat()
    if tuple(map(int, new.split("."))) <= tuple(map(int, old.split("."))):
        _err(f"new version {new} must be > current {old}")
        return 1
    print(f"[release] {old} -> {new} ({'DRY-RUN' if args.dry_run else 'LIVE'})")

    touched = bump(old, new, args.title, today, args.dry_run)
    if args.dry_run:
        print("[release] dry-run done — no files changed, nothing committed")
        return 0
    if not touched:
        _err("no files were bumped; aborting")
        return 1

    bad_links = _check_readme_links()
    if bad_links:
        for bl in bad_links:
            _err(f"relative link in {bl} — PyPI renders it 404; use absolute github.com URL")
        return 1

    if _run([sys.executable, "scripts/validate-globals.py"], check=False).returncode != 0:
        _err("validate-globals failed — fix the reported files (likely a missed version) and rerun")
        return 1
    if not args.skip_tests and _run([sys.executable, "aizee_cli.py", "test", "--full"], check=False).returncode != 0:
        _err("test suite failed — release aborted")
        return 1

    # Rebuild the bundled OS root so the wheel ships the new README/version.
    if _run([sys.executable, "scripts/build_osroot_bundle.py"], check=False).returncode != 0:
        _err("osroot bundle rebuild failed — release aborted")
        return 1

    _run(["git", "add", *touched])
    _run(["git", "commit", "-m", f"chore(release): bump version to {new} — {args.title}"])
    _run(["git", "tag", "-a", f"v{new}", "-m", f"v{new} — {args.title}"])
    if args.no_push:
        print(f"[release] local commit + tag v{new} created — push when ready")
        return 0
    _run(["git", "push", "origin", "main"])
    _run(["git", "push", "origin", f"v{new}"])
    if not args.no_release:
        _run(["gh", "release", "create", f"v{new}", "--title", f"aiZee v{new}", "--generate-notes"])
    if args.publish_pypi:
        import os
        if not (os.environ.get("UV_PUBLISH_TOKEN") or os.environ.get("TWINE_PASSWORD")):
            _err("--publish-pypi needs UV_PUBLISH_TOKEN (or TWINE_PASSWORD) in env")
            return 1
        if _run(["uv", "build"], check=False).returncode != 0:
            _err("uv build failed — PyPI publish aborted")
            return 1
        if _run(["uv", "publish"], check=False).returncode != 0:
            _err("uv publish failed — check token/scope")
            return 1
        print(f"[release] PyPI: https://pypi.org/project/aizee/{new}/")
    print(f"[release] DONE — v{new} published. Users update via update.bat (scripts/update.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
