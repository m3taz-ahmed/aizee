"""Capture-time secret scrubbing (agentmemory adoption).

Memory ingest and hook capture store tool/agent output that may contain
credentials. Scrubbing must happen at capture time — before persistence —
not only at display time (config show is already masked via config_ops).

Patterns target *assigned* secrets and known token prefixes only: bare
substrings that merely look like words ("monkey") are never touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REDACTION = "[REDACTED]"

# Assigned secrets: key=value / key: value where key names a credential.
_KEYED = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization|auth|"
    r"private[_-]?key|client[_-]?secret|access[_-]?key|session[_-]?key)"
    r"([\s]*[=:]\s*)"
    r"(['\"]?)([^\s'\"]{8,})\3"
)

# Known token prefixes — redacted wherever they appear.
_PREFIXED = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|"  # OpenAI / Anthropic style keys
    r"gh[pousr]_[A-Za-z0-9]{20,}|"  # GitHub tokens
    r"glpat-[A-Za-z0-9_-]{15,}|"  # GitLab PAT
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"  # Slack tokens
    r"AIza[0-9A-Za-z_-]{30,}|"  # Google API keys
    r"AKIA[0-9A-Z]{16}|"  # AWS access key id
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|"  # JWT
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

# Authorization header values: "Bearer <token>", "Basic <b64>".
_AUTH_HEADER = re.compile(r"(?i)\b(bearer|basic)\s+([A-Za-z0-9+/=_.:-]{16,})")


@dataclass(frozen=True)
class ScrubResult:
    """Scrubbed text + how many secrets were found."""

    text: str
    findings: int


def scrub_text(text: str) -> ScrubResult:
    """Remove credentials from *text*. Returns scrubbed text + finding count."""
    findings = 0

    def _keyed(m: re.Match[str]) -> str:
        nonlocal findings
        value = m.group(4)
        # Prose filter: a pure-alpha value under 16 chars is an English
        # word ("Authorization: Distinguish auth from ..."), not a secret.
        if value.isalpha() and len(value) < 16:
            return m.group(0)
        findings += 1
        return f"{m.group(1)}{m.group(2)}{REDACTION}"

    def _replaced(m: re.Match[str]) -> str:
        nonlocal findings
        findings += 1
        return REDACTION

    def _auth(m: re.Match[str]) -> str:
        nonlocal findings
        findings += 1
        return f"{m.group(1)} {REDACTION}"

    text = _KEYED.sub(_keyed, text)
    text = _PREFIXED.sub(_replaced, text)
    text = _AUTH_HEADER.sub(_auth, text)
    return ScrubResult(text=text, findings=findings)


def scrub_obj(obj: object) -> tuple[object, int]:
    """Recursively scrub strings in dicts/lists. Returns (obj, findings)."""
    if isinstance(obj, str):
        result = scrub_text(obj)
        return result.text, result.findings
    if isinstance(obj, dict):
        return scrub_dict(obj)
    if isinstance(obj, list):
        cleaned = [scrub_obj(v) for v in obj]
        return [c[0] for c in cleaned], sum(c[1] for c in cleaned)
    return obj, 0


def scrub_dict(obj: dict[object, object]) -> tuple[dict[object, object], int]:
    """Scrub a dict's string values recursively, returning a new dict."""
    cleaned: dict[object, object] = {}
    findings = 0
    for key, value in obj.items():
        new_value, n = scrub_obj(value)
        cleaned[key] = new_value
        findings += n
    return cleaned, findings
