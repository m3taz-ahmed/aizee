#!/usr/bin/env python3
"""Keep the installed ``aizee`` package in lockstep with a deploy root.

``update_aizee.bat`` calls this after mirroring: wheels carry code only,
so a sync that changed code leaves the installed CLI stale until the
package is rebuilt. Reinstalls when either signal fires:

- the root's ``pyproject.toml`` version differs from the installed dist,
- or the installed code payload differs from the root's (same version,
  new code — the between-releases drift a version compare alone misses).

Same-version/same-content runs are a strict no-op — which also leaves
editable installs (``pip install -e``) untouched, since an editable
tree digests identically to the just-synced mirror.

Usage:
    python scripts/sync_installed_pkg.py <deploy_root>
Exit code is the pip return code when a reinstall ran, else 0.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import pathlib
import re
import subprocess
import sys

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"\n]+)"', re.MULTILINE)

# Code payload the wheel ships (pyproject py-modules + packages.find).
_CODE_PAYLOAD = ("aizee_cli.py", "config.py", "runtime", "memory", "aizee_mcp", "plugins", "eval")


def _root_version(root: pathlib.Path) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return ""
    match = _VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def _installed_version() -> str:
    try:
        return importlib.metadata.version("aizee")
    except importlib.metadata.PackageNotFoundError:
        return ""


def _installed_code_root() -> pathlib.Path | None:
    """Dir holding the installed ``aizee_cli.py`` (site-packages or editable tree)."""
    spec = importlib.util.find_spec("aizee_cli")
    if spec is None or not spec.origin:
        return None
    return pathlib.Path(spec.origin).resolve().parent


def _package_digest(base: pathlib.Path) -> str:
    """sha256 over the wheel's code payload — changes when ANY shipped file does."""
    h = hashlib.sha256()
    for entry in _CODE_PAYLOAD:
        path = base / entry
        if path.is_file():
            h.update(entry.encode())
            h.update(path.read_bytes())
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    h.update(f.relative_to(base).as_posix().encode())
                    h.update(f.read_bytes())
        else:
            h.update(entry.encode() + b"\x00absent")
        h.update(b"\x00")
    return h.hexdigest()


def _reinstall(root: pathlib.Path) -> int:
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", str(root)]
    ).returncode


def main() -> int:
    if len(sys.argv) < 2:
        print("[pkg-sync] usage: sync_installed_pkg.py <deploy_root>", file=sys.stderr)
        return 2
    root = pathlib.Path(sys.argv[1]).resolve()
    want = _root_version(root)
    if not want:
        print(f"[pkg-sync] no version found in {root / 'pyproject.toml'} — skipped")
        return 0
    have = _installed_version()
    if have == want:
        installed_base = _installed_code_root()
        if installed_base is not None and _package_digest(installed_base) == _package_digest(root):
            print(f"[pkg-sync] aizee {have} already matches the root — nothing to do")
            return 0
        print(f"[pkg-sync] same version {want} but code drifted — reinstalling")
        return _reinstall(root)
    print(f"[pkg-sync] installed {have or 'none'} -> {want}; reinstalling")
    return _reinstall(root)


if __name__ == "__main__":
    sys.exit(main())
