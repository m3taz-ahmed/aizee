#!/usr/bin/env python3
"""aiZee configuration and root discovery."""

from __future__ import annotations

import os
import re
from pathlib import Path


def discover_root() -> Path:
    """Discover aiZee root.

    Order:
    1. AIZEE_ROOT environment variable.
    2. Root pointer file written by ``aizee bootstrap`` (see
       :func:`root_pointer_file`) — lets a plain ``pip install aizee``
       work without a persistent env var.
    3. The directory containing the current install (parent of config.py).
    """
    env_root = os.environ.get("AIZEE_ROOT")
    if env_root:
        return _resolve_env_dir("AIZEE_ROOT", Path(__file__).resolve().parent)
    pointer = _read_root_pointer()
    if pointer is not None:
        return pointer
    return Path(__file__).resolve().parent


def root_pointer_file() -> Path:
    """User-level file holding the path of the materialized OS root."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "aizee" / "root.txt"
    return Path.home() / ".config" / "aizee" / "root.txt"


def write_root_pointer(root: Path) -> Path:
    """Persist ``root`` for later :func:`discover_root` calls."""
    pointer = root_pointer_file()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(root) + "\n", encoding="utf-8")
    return pointer


def _read_root_pointer() -> Path | None:
    """Return the pointer-file root if it exists and still points at a dir."""
    try:
        pointer = root_pointer_file()
        if not pointer.is_file():
            return None
        lines = pointer.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        return path.resolve() if path.is_dir() else None
    return None


def default_os_root() -> Path:
    """Default materialization target for ``aizee bootstrap``.

    Order:
    1. AIZEE_ROOT environment variable (existing configured root).
    2. Previously bootstrapped root (pointer file).
    3. The install directory itself when it is already a full OS root
       (source checkout — skills/ + workflows/ present).
    4. A per-user data dir (the ``pip install aizee`` case, where the
       install dir is site-packages and must not be written to).
    """
    env_root = os.environ.get("AIZEE_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()
    pointer = _read_root_pointer()
    if pointer is not None:
        return pointer
    install_dir = Path(__file__).resolve().parent
    if (install_dir / "skills").is_dir() and (install_dir / "workflows").is_dir():
        return install_dir
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "aizee"
    return Path.home() / ".local" / "share" / "aizee"


def discover_project_root() -> Path:
    """Discover active project root.

    Order:
    1. AGENT_PROJECT_ROOT environment variable (explicit project override).
    2. AIZEE_ROOT environment variable (OS root; takes precedence over CWD
       to keep dashboard/tests isolated - see dashboard/server.py _serve).
       For a different project checkout while AIZEE_ROOT is set, set
       AGENT_PROJECT_ROOT to that project's path instead of relying on CWD.
    3. Current working directory if it contains `.ai/active-context.md`.
    4. The directory containing the current install (parent of config.py).
    """
    project_env = os.environ.get("AGENT_PROJECT_ROOT")
    if project_env:
        return _resolve_env_dir("AGENT_PROJECT_ROOT", discover_root())
    os_env = os.environ.get("AIZEE_ROOT")
    if os_env:
        return _resolve_env_dir("AIZEE_ROOT", discover_root())
    cwd = Path.cwd()
    if (cwd / ".ai" / "active-context.md").exists():
        return cwd.resolve()
    return discover_root()


def _resolve_env_dir(env_var: str, fallback: Path) -> Path:
    env_root = os.environ.get(env_var)
    if env_root:
        path = Path(env_root)
        if path.is_dir():
            return path.resolve()
        raise ValueError(f"{env_var} points to non-existent directory: {env_root}")
    return fallback


def _version() -> str:
    pyproject = Path(__file__).resolve().parent / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'^version\s*=\s*"([^"\n]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return match.group(1)
    return "6.14.0"


VERSION: str = _version()
