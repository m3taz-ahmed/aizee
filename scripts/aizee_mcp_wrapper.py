#!/usr/bin/env python3
"""Wrapper script for the aiZee MCP server.

This replaces the inline Python one-liner in MCP config files.
Sets AIZEE_ROOT and launches the MCP server.
"""
import os
import pathlib
import subprocess
import sys


def discover_root() -> str:
    """Discover the aiZee root directory."""
    root = os.environ.get("AIZEE_ROOT")
    if root and pathlib.Path(root).is_dir():
        return root
    cwd = pathlib.Path.cwd()
    if (cwd / "config.py").exists():
        return str(cwd)
    return str(cwd)


def _reexec_if_missing_deps() -> None:
    """Re-exec under a dep-capable python when the launch interpreter lacks them.

    MCP configs invoke bare ``python`` — on this machine that is 3.15, which
    has no project deps installed, so the server dies before the initialize
    handshake. ``AIZEE_MCP_PYTHON`` overrides the fallback interpreter.
    """
    import importlib.util
    if (
        importlib.util.find_spec("mcp") is None
        and not os.environ.get("AIZEE_MCP_WRAPPER_REEXEC")
        and sys.platform == "win32"
    ):
        os.environ["AIZEE_MCP_WRAPPER_REEXEC"] = "1"
        override = os.environ.get("AIZEE_MCP_PYTHON")
        if override:
            os.execv(override, [override, str(pathlib.Path(__file__).resolve())])
        os.execvp("py", ["py", "-3.10", str(pathlib.Path(__file__).resolve())])


def main() -> None:
    _reexec_if_missing_deps()
    root = discover_root()
    os.environ["AIZEE_ROOT"] = root
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    # Load centralized .env secrets before launching the MCP server
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        from mcp_secrets_loader import load_env
        load_env()
    except Exception as exc:  # secrets are optional — never block server launch
        print(f"[aizee-mcp-wrapper] secrets load skipped: {exc}", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "aizee_mcp.aizee_server"], cwd=root)


if __name__ == "__main__":
    main()
