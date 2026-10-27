"""Skill security scanner (scientific-agent-skills' skill-scanner adoption).

Static pattern scan over SKILL.md files — same class of checks Cisco AI
Defense's skill-scanner runs per-PR, implemented locally so it works
offline and inside ``aizee skill scan``:

- prompt-injection phrasing aimed at the agent ("ignore previous
  instructions", "you are now", "reveal your system prompt")
- exfiltration primitives (curl/wget to non-doc hosts, http URLs carrying
  key/token params, base64 blobs that decode to shell)
- dangerous execution primitives in embedded commands (eval, os.system,
  rm -rf, chmod 777, piping remote scripts into a shell)

Severity: ``high`` findings fail the scan; ``medium`` are warnings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HIGH = "high"
MEDIUM = "medium"


@dataclass(frozen=True)
class Finding:
    """One scanner hit."""

    severity: str
    rule: str
    line: int
    excerpt: str


_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (HIGH, "prompt-injection", re.compile(
        r"(?i)(ignore\s+((all|any|previous|prior|above|these|the)\s+)*instructions|"
        r"disregard\s+((all|any|prior|previous|above)\s+)*(instructions|rules|guidelines)|"
        r"you are now|new system prompt|reveal (your|the) "
        r"(system|initial) prompt|do not tell the user)"
    )),
    (HIGH, "exfil-channel", re.compile(
        r"(?i)(curl|wget|invoke-webrequest|invoke-restmethod)\b[^\n]*"
        r"(token|api[_\s-]?key|secret|password|authorization)"
    )),
    (HIGH, "remote-pipe-shell", re.compile(
        r"(?i)(curl|wget|invoke-webrequest)\b[^\n]*(\||&&|;)\s*(bash|sh|zsh|pwsh|powershell|cmd)\b"
    )),
    (HIGH, "credential-request", re.compile(
        r"(?i)(paste|enter|provide|send)\s+(your|the)\s+(api[_\s-]?key|password|"
        r"private key|secret|token)"
    )),
    (MEDIUM, "shell-eval", re.compile(r"(?i)\b(eval|exec)\s*\(|os\.system\s*\(")),
    (MEDIUM, "destructive-fs", re.compile(
        r"(?i)\b(rm\s+-rf?\s+/|del\s+/[sfq]|format\s+[a-z]:|chmod\s+777)"
    )),
    (MEDIUM, "opaque-blob", re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{120,}={0,2}(?![A-Za-z0-9+/=])")),
    (MEDIUM, "hidden-comment", re.compile(r"<!--[\s\S]{0,200}(ignore|instruction|secret|token)[\s\S]{0,200}-->", re.I)),
)


def scan_text(text: str, source: str = "") -> list[Finding]:
    """Scan raw markdown/text for skill-security patterns."""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for severity, rule, pattern in _RULES:
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity=severity,
                        rule=rule,
                        line=lineno,
                        excerpt=line.strip()[:120],
                    )
                )
    return findings


def scan_file(path: Path) -> list[Finding]:
    return scan_text(path.read_text(encoding="utf-8"), source=str(path))


_ALLOWLIST = ".scan-allowlist.json"


def _load_allowlist(root: Path) -> list[dict[str, str]]:
    """Maintainer-triaged suppressions (anthropic-cybersecurity's
    lint-baseline.json pattern): each entry pins {file, rule, match} so only
    that exact finding is suppressed — new injections elsewhere still fire."""
    path = root / "skills" / _ALLOWLIST
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def _suppressed(f: Finding, rel: str, allowlist: list[dict[str, str]]) -> bool:
    return any(
        e.get("file") == rel
        and e.get("rule") == f.rule
        and str(e.get("match", "")) in f.excerpt
        for e in allowlist
    )


def scan_tree(root: Path, subdir: str = "skills") -> dict[str, Any]:
    """Scan every markdown skill file under *root/subdir*."""
    base = root / subdir
    files = sorted(base.rglob("*.md")) if base.is_dir() else []
    allowlist = _load_allowlist(root)
    report: dict[str, list[dict[str, Any]]] = {}
    high = 0
    suppressed = 0
    for path in files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        hits: list[Finding] = []
        for f in scan_file(path):
            if _is_doc_exempt(path, f) or _suppressed(f, rel, allowlist):
                suppressed += 1
                continue
            hits.append(f)
        if hits:
            report[rel] = [
                {
                    "severity": f.severity,
                    "rule": f.rule,
                    "line": f.line,
                    "excerpt": f.excerpt,
                }
                for f in hits
            ]
            high += sum(1 for f in hits if f.severity == HIGH)
    return {
        "ok": high == 0,
        "high": high,
        "suppressed": suppressed,
        "files_scanned": len(files),
        "findings": report,
    }


def _is_doc_exempt(path: Path, finding: Finding) -> bool:
    """Docs teaching *about* injection (this module's own docs, security
    skills, this file) quote the patterns legitimately — exempt files whose
    frontmatter marks them as security-reference material."""
    if finding.rule in {"shell-eval", "destructive-fs"}:
        return "scanner" in path.name or "security" in path.name
    return False
