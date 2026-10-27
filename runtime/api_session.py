"""Governed API session (mimic adoption).

mimic's insight: an app authenticates every request with a stable *auth
bundle* — bearer token + device/session headers. Capture it once from a
real call (curl paste, browser HAR export, or a header dict) and new
calls replay it faithfully. mimic then codegen'd a whole client; we stop
at the governed boundary: every request goes through ``kernel.act`` so
policy/budget/audit apply to replayed traffic.

Security: headers are filtered through the bundle rules (noise dropped),
secrets can be referenced as ``{NAME}`` placeholders resolved by a
``SensitiveVault`` at send time, and audit records masked headers only.
"""

from __future__ import annotations

import json
import shlex
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from runtime.sensitive import SensitiveVault

_AUTH_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie"})


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Fail-closed redirect policy for captured auth bundles.

    A captured session is scoped to ONE host — a same-host endpoint that
    302s to an attacker domain would make urllib resend Authorization and
    Cookie there. Same-host redirects keep the bundle (same trust domain);
    cross-host redirects are refused entirely.
    """

    def __init__(self, allowed_host: str) -> None:
        self._allowed_host = allowed_host.lower()
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        new_host = urlparse(newurl).netloc.lower()
        if new_host and new_host != self._allowed_host:
            return None  # refuse: raises HTTPError, no cross-host replay
        return super().redirect_request(req, fp, code, msg, headers, newurl)

# Auth-bundle heuristics (mimic/extract.py): which headers are worth replaying.
KEEP_EXACT = frozenset(
    {"authorization", "cookie", "user-agent", "accept-language", "accept", "content-type"}
)
KEEP_PREFIX = ("x-",)
DROP = frozenset(
    {
        "content-length",
        "host",
        "connection",
        "accept-encoding",
        "content-encoding",
        "priority",
        "x-forwarded-for",
    }
)


def keep_header(name: str) -> bool:
    n = name.lower()
    if n in DROP:
        return False
    return n in KEEP_EXACT or n.startswith(KEEP_PREFIX)


def extract_bundle(headers: dict[str, str]) -> dict[str, str]:
    """Filter a raw request's headers down to the replayable auth bundle."""
    return {k: v for k, v in headers.items() if keep_header(k)}


def _parse_curl(text: str) -> tuple[str, str, dict[str, str], str | None]:
    """Parse ``curl 'URL' -H 'k: v' -X POST -d '...'`` → (method, url, headers, body)."""
    tokens = shlex.split(text.replace("\\\n", " "), posix=True)
    if tokens and tokens[0] == "curl":
        tokens = tokens[1:]
    method, url, body = "GET", "", None
    headers: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-H", "--header") and i + 1 < len(tokens):
            i += 1
            name, _, value = tokens[i].partition(":")
            headers[name.strip()] = value.strip()
        elif tok in ("-X", "--request") and i + 1 < len(tokens):
            i += 1
            method = tokens[i].upper()
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--json") and i + 1 < len(tokens):
            i += 1
            body = tokens[i]
            if method == "GET":
                method = "POST"
        elif not tok.startswith("-") and not url:
            url = tok
        i += 1
    if not url:
        raise ValueError("curl command contains no URL")
    return method, url, headers, body


@dataclass
class GovernedApiSession:
    """Replays a captured auth bundle through the aiZee governance gates."""

    base_url: str
    headers: dict[str, str] = field(default_factory=dict)
    kernel: Any = None
    vault: SensitiveVault = field(default_factory=SensitiveVault)

    def _opener(self) -> urllib.request.OpenerDirector:
        host = urlparse(self.base_url).netloc
        return urllib.request.build_opener(_SameHostRedirect(host))

    # --- constructors -------------------------------------------------------
    @classmethod
    def from_curl(
        cls, text: str, kernel: Any = None, vault: SensitiveVault | None = None
    ) -> GovernedApiSession:
        """Build a session from a copied ``curl`` command."""
        _method, url, headers, _body = _parse_curl(text)
        parsed = urlparse(url if "://" in url else f"https://{url}")
        base = f"{parsed.scheme}://{parsed.netloc}"
        return cls(base, extract_bundle(headers), kernel, vault or SensitiveVault())

    @classmethod
    def from_headers(
        cls,
        base_url: str,
        headers: dict[str, str],
        kernel: Any = None,
        vault: SensitiveVault | None = None,
    ) -> GovernedApiSession:
        """Build a session from an explicit header dict (already filtered)."""
        return cls(base_url.rstrip("/"), extract_bundle(headers), kernel, vault or SensitiveVault())

    @classmethod
    def from_har(
        cls,
        path: Path | str,
        host: str | None = None,
        kernel: Any = None,
        vault: SensitiveVault | None = None,
    ) -> GovernedApiSession:
        """Build a session from a browser HAR export.

        With no *host*, picks the most-requested host in the file (mimic).
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = data.get("log", {}).get("entries", [])
        if not entries:
            raise ValueError("HAR contains no entries")
        counts: dict[str, int] = {}
        for e in entries:
            h = urlparse(e.get("request", {}).get("url", "")).netloc
            if h:
                counts[h] = counts.get(h, 0) + 1
        if host is None:
            if not counts:
                raise ValueError("HAR contains no request URLs")
            host = max(counts, key=counts.__getitem__)
        # Newest request to the host carries the freshest auth bundle.
        for entry in reversed(entries):
            req = entry.get("request", {})
            if urlparse(req.get("url", "")).netloc == host:
                headers = {h["name"]: h["value"] for h in req.get("headers", [])}
                return cls(
                    f"{urlparse(req['url']).scheme}://{host}",
                    extract_bundle(headers),
                    kernel,
                    vault or SensitiveVault(),
                )
        raise ValueError(f"no request to {host} found in HAR")

    # --- governed send ------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        body: bytes | str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send one request after the governance gate.

        ``kernel.act("ApiCall")`` must approve first; on denial the request
        is never dispatched (fail-closed). Audit records masked headers.
        """
        if path.startswith("http"):
            url = path
            # The auth bundle is bound to base_url's host — never replay it
            # to a different one (fail closed, exfiltration guard).
            if urlparse(url).netloc.lower() != urlparse(self.base_url).netloc.lower():
                return {"ok": False, "error": "cross-host URL denied for captured session", "status": 0}
        else:
            url = f"{self.base_url}{path}"
        if self.kernel is not None:
            verdict = self.kernel.act(
                "ApiCall",
                url=url,
                method=method,
                headers=self.vault.mask_dict({**self.headers, **(extra_headers or {})}),
            )
            if not verdict.get("ok"):
                return {"ok": False, "error": verdict.get("error", "denied by policy"), "status": 0}
        headers = {k: self.vault.inject(v) for k, v in self.headers.items()}
        headers.update(extra_headers or {})
        data = body.encode() if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener().open(req, timeout=timeout) as resp:
                payload = resp.read()
                return {
                    "ok": True,
                    "status": resp.status,
                    "headers": dict(resp.headers.items()),
                    "body": payload[:1_000_000].decode("utf-8", errors="replace"),
                }
        except urllib.error.HTTPError as exc:
            return {"ok": False, "status": exc.code, "error": str(exc)}
        except OSError as exc:
            return {"ok": False, "status": 0, "error": str(exc)}
