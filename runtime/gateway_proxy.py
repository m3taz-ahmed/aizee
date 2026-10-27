"""Governed LLM gateway proxy — failover chain + enforcement on the path.

Adopted from free-claude-code + ds2api: a localhost HTTP proxy that sits on
the LLM traffic path instead of only advising around it. Forwards Anthropic
``/v1/messages`` and OpenAI ``/v1/chat/completions`` shaped requests to a
provider chain with ordered failover (timeout/429/5xx -> next provider).

Every request passes ``kernel.act("LLMRequest", ...)`` first — probity,
guardian, policy, prompt guardrails, budget, audit all still apply —
so governance is enforced inside the path, not around it.

Stdlib-only (http.server + urllib): no new runtime dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PORT = 8787
DEFAULT_TIMEOUT = 30.0
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_SUPPORTED_PATHS = ("/v1/messages", "/v1/chat/completions")
_MAX_BODY_BYTES = 10 * 1024 * 1024  # local proxy — refuse oversized payloads
# Prompt-guardrail scan window: large enough that injected instructions
# cannot hide past the gate, bounded so a hostile body cannot stall it.
_PROMPT_GATE_CHARS = 64_000


@dataclass(frozen=True)
class Provider:
    """One upstream in the failover chain.

    ``tiers`` marks which request classes this provider serves
    (browser-use's small-model split): ``default`` = main reasoning;
    ``flash`` = fast/cheap calls that skip deep reasoning; ``extraction``
    = page/data extraction work. An empty tuple serves every tier.
    """

    name: str
    base_url: str
    kind: str = "anthropic"  # anthropic | openai
    api_key_env: str = ""
    timeout: float = DEFAULT_TIMEOUT
    headers: dict[str, str] = field(default_factory=dict)
    tiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class GatewayConfig:
    providers: tuple[Provider, ...]
    verify: str = "final"

    def providers_for(self, tier: str) -> tuple[Provider, ...]:
        """Failover order for one tier: dedicated providers first, then
        untiered fallbacks (a dedicated-only chain that can never serve is
        a config bug, so untiered providers remain eligible)."""
        dedicated = tuple(p for p in self.providers if tier in p.tiers)
        if dedicated:
            return dedicated + tuple(p for p in self.providers if not p.tiers)
        return self.providers

    @staticmethod
    def load(path: Path) -> GatewayConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        providers = tuple(
            Provider(
                name=str(p["name"]),
                base_url=str(p["base_url"]).rstrip("/"),
                kind=str(p.get("kind", "anthropic")),
                api_key_env=str(p.get("api_key_env", "")),
                timeout=float(p.get("timeout", DEFAULT_TIMEOUT)),
                headers={str(k): str(v) for k, v in (p.get("headers") or {}).items()},
                tiers=tuple(str(t) for t in (p.get("tiers") or ())),
            )
            for p in data.get("providers", [])
        )
        # YAML 1.1 parses bare off/on/yes/no as booleans — normalize so a
        # user-written `verify: off` still resolves to the level name.
        raw_verify = data.get("verify", "final")
        if raw_verify is False:
            verify = "off"
        elif raw_verify is True:
            verify = "strict"
        else:
            verify = str(raw_verify)
        return GatewayConfig(providers=providers, verify=verify)


def estimate_tokens(payload: dict[str, Any]) -> int:
    """Rough token estimate from message text (4 chars ~ 1 token)."""
    total_chars = 0
    for msg in payload.get("messages", []) or []:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += sum(
                len(b.get("text", "")) for b in content if isinstance(b, dict)
            )
    prompt = payload.get("prompt", "")
    if isinstance(prompt, str):
        total_chars += len(prompt)
    return max(1, total_chars // 4)


def extract_prompt_text(payload: dict[str, Any]) -> str:
    """Flatten message text for prompt-guardrail inspection."""
    parts: list[str] = []
    for msg in payload.get("messages", []) or []:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(b.get("text", "") for b in content if isinstance(b, dict))
    prompt = payload.get("prompt", "")
    if isinstance(prompt, str):
        parts.append(prompt)
    return "\n".join(parts)


def forward(
    provider: Provider,
    path: str,
    body: bytes,
    extra_headers: dict[str, str],
) -> tuple[int, bytes, dict[str, str]]:
    """Forward one request to a provider; return (status, body, resp_headers)."""
    url = provider.base_url + path
    headers = {
        "Content-Type": "application/json",
        **provider.headers,
        **extra_headers,
    }
    if provider.api_key_env:
        key = os.environ.get(provider.api_key_env, "")
        if key:
            if provider.kind == "anthropic":
                headers["x-api-key"] = key
                headers.setdefault("anthropic-version", "2023-06-01")
            else:
                headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=provider.timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers or {})
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b"", {}


def forward_with_failover(
    config: GatewayConfig,
    path: str,
    body: bytes,
    extra_headers: dict[str, str],
    tier: str = "default",
) -> tuple[int, bytes, dict[str, str], str]:
    """Try providers in order; retry on timeout/429/5xx. Returns 4-tuple."""
    last: tuple[int, bytes, dict[str, str]] = (0, b"", {})
    for provider in config.providers_for(tier):
        status, resp_body, resp_headers = forward(provider, path, body, extra_headers)
        if status != 0 and status not in _RETRYABLE_STATUS:
            return status, resp_body, resp_headers, provider.name
        last = (status, resp_body, resp_headers)
    status, resp_body, resp_headers = last
    return status, resp_body, resp_headers, ""


def make_handler(config: GatewayConfig, kernel: Any) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to config + kernel enforcement."""

    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path not in _SUPPORTED_PATHS:
                self._respond(404, _envelope_err("NOT_FOUND", f"unsupported path {path}"))
                return
            try:
                body = self._read_body()
                payload = json.loads(body) if body else {}
            except (ValueError, OSError):
                self._respond(400, _envelope_err("BAD_INPUT", "invalid JSON body"))
                return

            gate = self._gate(payload)
            if gate is not None:
                self._respond(403, gate)
                return

            headers = {"anthropic-version": self.headers.get("anthropic-version", "")}
            headers = {k: v for k, v in headers.items() if v}
            tier = str(payload.get("tier") or payload.get("metadata", {}).get("tier") or "default")
            status, resp_body, _resp_headers, provider_name = forward_with_failover(
                config, path, body, headers, tier=tier,
            )
            if status == 0:
                self._respond(502, _envelope_err("UPSTREAM_BROKEN", "all providers failed"))
                return
            if not provider_name:
                # Last-try failure still returns the upstream's body for debug.
                provider_name = config.providers[-1].name if config.providers else "none"
            self._respond(status, resp_body, provider=provider_name)

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            if length > _MAX_BODY_BYTES:
                raise ValueError("body too large")
            return self.rfile.read(length) if length else b""

        def _gate(self, payload: dict[str, Any]) -> dict[str, Any] | None:
            """Run kernel.act on the outbound prompt; None = allow."""
            if kernel is None:
                return None
            tokens = estimate_tokens(payload)
            prompt_text = extract_prompt_text(payload)
            result = kernel.act(
                "LLMRequest",
                prompt=prompt_text[:_PROMPT_GATE_CHARS],
                tokens=tokens,
                verify=config.verify,
            )
            if result.get("ok"):
                return None
            return _envelope_err("POLICY_DENIED", str(result.get("reason") or result.get("error", "blocked by policy")))

        def _respond(self, status: int, body: bytes | dict[str, Any], provider: str = "") -> None:
            raw = json.dumps(body).encode("utf-8") if isinstance(body, dict) else body
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            if provider:
                self.send_header("X-Aizee-Provider", provider)
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return  # quiet — audit log already records gated requests

    return GatewayHandler


def _envelope_err(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "aizee.gateway.v1",
        "ok": False,
        "error": {"code": code, "message": message},
    }


def serve(config_path: Path, port: int, kernel: Any, host: str = "127.0.0.1") -> int:
    """Start the gateway proxy (blocking). Returns on KeyboardInterrupt."""
    config = GatewayConfig.load(config_path)
    if not config.providers:
        raise ValueError(f"gateway config {config_path} has no providers")
    handler = make_handler(config, kernel)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"aizee gateway listening on http://{host}:{port} ({len(config.providers)} providers)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
