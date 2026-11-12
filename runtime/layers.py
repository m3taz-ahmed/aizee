"""Architectural layer classification for graph nodes (Understand-Anything adoption).

Heuristic path/name mapping — deterministic, no LLM. Shared by
``runtime.impact`` and ``runtime.tour`` so both speak the same layer
vocabulary (their dashboard's API/Service/Data/UI/Utility analog).
"""

from __future__ import annotations

import enum


class Layer(str, enum.Enum):
    CLI = "cli"
    DASHBOARD = "dashboard"
    RUNTIME = "runtime"
    MEMORY = "memory"
    SKILLS = "skills"
    WORKFLOWS = "workflows"
    TESTS = "tests"
    DOCS = "docs"
    CONFIG = "config"
    VENDOR = "vendor"
    SCRIPTS = "scripts"
    OTHER = "other"


_PREFIX_MAP: tuple[tuple[str, Layer], ...] = (
    ("tests/", Layer.TESTS),
    ("test/", Layer.TESTS),
    ("dashboard/", Layer.DASHBOARD),
    ("runtime/", Layer.RUNTIME),
    ("memory/", Layer.MEMORY),
    ("skills/", Layer.SKILLS),
    ("workflows/", Layer.WORKFLOWS),
    ("docs/", Layer.DOCS),
    ("scripts/", Layer.SCRIPTS),
    ("aizee_mcp/", Layer.RUNTIME),
    ("refs/", Layer.VENDOR),
    ("vendor/", Layer.VENDOR),
    ("node_modules/", Layer.VENDOR),
    ("eval/", Layer.TESTS),
    ("tech-stack/", Layer.DOCS),
)

_CONFIG_NAMES = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "config.py",
        "manifest.json",
        "plugin.json",
        "server.json",
        "deps.yaml",
        "settings.json",
        ".gitignore",
        ".gitattributes",
    }
)

_DOC_SUFFIXES = (".md", ".rst", ".txt", ".adoc")


def layer_for(path: str) -> Layer:
    """Classify a repo-relative path into an architectural layer."""
    norm = path.replace("\\", "/")
    if norm.startswith("./"):
        norm = norm[2:]
    lower = norm.lower()
    base = lower.rsplit("/", 1)[-1]
    for prefix, layer in _PREFIX_MAP:
        if lower.startswith(prefix):
            return layer
    if base in _CONFIG_NAMES or base.endswith((".toml", ".yaml", ".yml", ".cfg", ".ini")):
        return Layer.CONFIG
    if base.startswith(".env") or (base.startswith(".") and "." not in base[1:]):
        return Layer.CONFIG
    if lower.endswith(_DOC_SUFFIXES) or base.startswith("readme"):
        return Layer.DOCS
    if base.endswith((".bat", ".cmd", ".ps1", ".sh")):
        return Layer.SCRIPTS
    if "/" not in lower and lower.endswith(".py"):
        return Layer.CLI
    return Layer.OTHER


def layer_for_test_of(source_path: str) -> str | None:
    """Return the conventional test filename for a source file, if any."""
    norm = source_path.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if not base.endswith(".py") or base.startswith("test_"):
        return None
    return f"tests/test_{base}"
