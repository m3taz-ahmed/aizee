"""Doc<->code drift checker (vercel-labs/lat.md adoption).

Markdown docs link into the codebase with wiki-style refs:

- ``[[path/to/file.py]]`` — file must exist.
- ``[[path/to/file.py#symbol]]`` — file must exist AND define the symbol
  (def/class/assignment across .py/.ts/.js/.rs/.go).
- ``@aizee: [[section]]`` comments in source link code back to docs.

``check_links`` validates every ``[[...]]`` ref in tracked markdown and
reports broken targets — the drift gate lat.md runs before agents finish.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_LINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#([^\]|]+))?(?:\|[^\]]*)?\]\]")
_CODE_REF_RE = re.compile(r"@aizee:\s*\[\[([^\]]+)\]\]")
_SKIP_DIRS = frozenset(
    {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "temp",
        "refs", "archives", "graphify-out", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", "build", "dist", ".ai", "brain", "state", "backups",
    }
)
# Symbol definitions per extension — deliberately permissive.
_SYMBOL_RES: dict[str, re.Pattern[str]] = {
    ".py": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+{name}\b|^\s*{name}\s*[:=]", re.M),
    ".ts": re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var|enum)\s+{name}\b",
        re.M,
    ),
    ".js": re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+{name}\b", re.M
    ),
    ".rs": re.compile(
        r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:fn|struct|enum|trait|impl|const|static|mod|type)\s+{name}\b",
        re.M,
    ),
    ".go": re.compile(r"^\s*(?:func|type|var|const)\s+{name}\b|^\s*func\s*\([^)]*\)\s*{name}\b", re.M),
    ".md": re.compile(r"^#+\s+.*?{name}", re.M),
}


def iter_markdown(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        out.append(p)
    return out


def extract_links(text: str) -> list[tuple[str, str]]:
    """Return [(target_path, symbol_or_empty)] — fenced code blocks skipped
    (TOML ``[[table]]`` arrays and config snippets are not links)."""
    out: list[tuple[str, str]] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = re.sub(r"`[^`]*`", "", line)  # inline code spans are not links
        for m in _LINK_RE.finditer(line):
            out.append((m.group(1).strip(), (m.group(2) or "").strip()))
    return out


def extract_code_refs(text: str) -> list[str]:
    return [m.group(1).strip() for m in _CODE_REF_RE.finditer(text)]


def symbol_defined(path: Path, symbol: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    rx = _SYMBOL_RES.get(path.suffix.lower())
    if rx is None:
        # Unknown extension: symbol counts as defined if it appears at all.
        return symbol in text
    return bool(re.search(rx.pattern.format(name=re.escape(symbol)), text, re.M))


@dataclass
class LinkIssue:
    source: str
    target: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "reason": self.reason}


@dataclass
class LinkReport:
    ok: bool
    files: int = 0
    links: int = 0
    issues: list[LinkIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "files": self.files,
            "links": self.links,
            "issues": [i.to_dict() for i in self.issues],
        }


def check_links(root: Path, *, scope: str = "all") -> LinkReport:
    """Validate ``[[path#symbol]]`` refs across tracked markdown files."""
    report = LinkReport(ok=True)
    for doc in iter_markdown(root):
        report.files += 1
        rel_src = str(doc.relative_to(root)).replace("\\", "/")
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target, symbol in extract_links(text):
            report.links += 1
            if "://" in target or target.startswith("#"):
                continue
            if Path(target).is_absolute():
                resolved = Path(target)
            else:
                # root-relative first (lat.md convention), doc-relative fallback
                resolved = root / target
                if not resolved.exists() and (doc.parent / target).exists():
                    resolved = doc.parent / target
            resolved = resolved.resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                report.issues.append(LinkIssue(rel_src, target, "escapes root"))
                continue
            if not resolved.exists():
                report.issues.append(LinkIssue(rel_src, target, "file not found"))
                continue
            if symbol and resolved.is_file() and not symbol_defined(resolved, symbol):
                report.issues.append(
                    LinkIssue(rel_src, f"{target}#{symbol}", "symbol not found")
                )
    report.ok = not report.issues
    return report
