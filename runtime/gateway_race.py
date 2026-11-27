#!/usr/bin/env python3
"""Evaluation-only parallel provider race for the governed gateway.

**This is a benchmarking tool, not a serving path.** Racing multiplies
cost per prompt by the number of providers engaged, so production traffic
keeps using the ordered failover chain in ``runtime/gateway_proxy.py``.
The race exists to answer operational questions with evidence:

- Which providers in my chain are actually fast/reliable *today*?
- How does the error taxonomy split (auth vs rate-limit vs timeout)?
- What latency does wave-staggered dispatch buy or cost?

Design (clean-room, stdlib-only — same constraints as the proxy):

- **Wave-staggered dispatch** — providers launch in waves of
  ``wave_size``, ``wave_stagger`` seconds apart, so a burst of simultaneous
  connections does not trip shared rate limiters.
- **Early exit** — once ``min_results`` successes land, a grace period
  runs; stragglers still finishing inside it are counted, the rest are
  cancelled and recorded as such.
- **Hard timeout** — nothing outlives ``hard_timeout``; unfinished
  providers are recorded ``timeout``.
- **Bounded 429 retries** — the worker retries rate-limit responses
  in-place at most ``retries_on_429`` times with linear backoff.
- **Honest reporting** — every provider gets a classified outcome; a
  race that yields zero successes carries an aggregated diagnosis.

Usage::

    from runtime.gateway_race import race, RaceConfig
    from runtime.gateway_proxy import GatewayConfig

    report = race(config, "/v1/chat/completions", body, tier="default")
    print(report.diagnosis or report.winner)
"""

from __future__ import annotations

import concurrent.futures as futures
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from runtime.gateway_proxy import GatewayConfig, Provider, forward

_logger = logging.getLogger(__name__)

# Signature of the injectable transport: same contract as gateway_proxy.forward.
ForwardFn = Callable[[Provider, str, bytes, dict[str, str]], tuple[int, bytes, dict[str, str]]]


class RaceErrorClass(str, Enum):
    """Normalized transport-error taxonomy across providers."""

    AUTH = "auth"  # 401/403 — key invalid or permission denied
    CREDITS = "credits"  # 402 — out of credits / payment required
    NOT_FOUND = "not_found"  # 404 — model or endpoint missing
    RATE_LIMIT = "rate_limit"  # 429
    SERVER = "server"  # 5xx upstream
    TIMEOUT = "timeout"  # no response / connection failure / race deadline
    CANCELLED = "cancelled"  # lost the early-exit race
    UNKNOWN = "unknown"


def classify_status(status: int) -> RaceErrorClass | None:
    """Map an HTTP-ish status to its error class; None means success."""
    if status == 0:
        return RaceErrorClass.TIMEOUT
    if 200 <= status < 300:
        return None
    if status in (401, 403):
        return RaceErrorClass.AUTH
    if status == 402:
        return RaceErrorClass.CREDITS
    if status == 404:
        return RaceErrorClass.NOT_FOUND
    if status == 429:
        return RaceErrorClass.RATE_LIMIT
    if status >= 500:
        return RaceErrorClass.SERVER
    return RaceErrorClass.UNKNOWN


@dataclass(frozen=True)
class RaceConfig:
    """Tunables for one race."""

    min_results: int = 2
    grace_period: float = 2.0
    hard_timeout: float = 30.0
    wave_size: int = 4
    wave_stagger: float = 0.15
    retries_on_429: int = 1
    retry_backoff: float = 0.5


@dataclass
class ProviderResult:
    """One provider's classified outcome."""

    provider: str
    status: int = 0
    latency_ms: float = 0.0
    error_class: RaceErrorClass | None = RaceErrorClass.UNKNOWN
    attempts: int = 0
    body_bytes: int = 0

    @property
    def ok(self) -> bool:
        return self.error_class is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
            "error_class": self.error_class.value if self.error_class else None,
            "attempts": self.attempts,
            "body_bytes": self.body_bytes,
            "ok": self.ok,
        }


@dataclass
class RaceReport:
    """Aggregate race outcome."""

    results: list[ProviderResult] = field(default_factory=list)
    duration_ms: float = 0.0
    diagnosis: str = ""

    @property
    def successes(self) -> list[ProviderResult]:
        return [r for r in self.results if r.ok]

    @property
    def winner(self) -> str:
        """Fastest successful provider name, or empty when none succeeded."""
        ok = sorted(self.successes, key=lambda r: r.latency_ms)
        return ok[0].provider if ok else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "duration_ms": round(self.duration_ms, 1),
            "successes": len(self.successes),
            "providers": len(self.results),
            "diagnosis": self.diagnosis,
            "results": [r.to_dict() for r in self.results],
        }


def diagnose_failures(results: list[ProviderResult]) -> str:
    """Aggregated diagnosis when no provider succeeded.

    Groups by error class so an operator sees 'all auth' vs 'all rate-limit'
    at a glance instead of reading N raw statuses.
    """
    if not results:
        return "no providers configured for this tier"
    counts: dict[RaceErrorClass, int] = {}
    for r in results:
        if r.error_class is not None:
            counts[r.error_class] = counts.get(r.error_class, 0) + 1
    if not counts:
        return ""
    parts = ", ".join(
        f"{cls.value} x{n}" for cls, n in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    dominant = max(counts, key=lambda c: counts[c])
    hints = {
        RaceErrorClass.AUTH: "check API keys / permissions",
        RaceErrorClass.CREDITS: "provider billing is exhausted",
        RaceErrorClass.RATE_LIMIT: "increase wave_stagger or reduce wave_size",
        RaceErrorClass.TIMEOUT: "check connectivity or raise hard_timeout",
        RaceErrorClass.NOT_FOUND: "model/endpoint names are stale — refresh the catalog",
        RaceErrorClass.SERVER: "upstream incident — retry later",
    }
    hint = hints.get(dominant, "inspect raw statuses")
    return f"all providers failed ({parts}) — {hint}"


def _worker(
    provider: Provider,
    path: str,
    body: bytes,
    headers: dict[str, str],
    race_config: RaceConfig,
    forward_fn: ForwardFn,
) -> ProviderResult:
    """One provider attempt loop (retries on 429 in-place)."""
    start = time.monotonic()
    attempts = 0
    status, resp_body = 0, b""
    max_attempts = 1 + max(0, race_config.retries_on_429)
    for attempt in range(max_attempts):
        attempts = attempt + 1
        status, resp_body, _ = forward_fn(provider, path, body, headers)
        if status != 429:
            break
        if attempt < max_attempts - 1:
            time.sleep(race_config.retry_backoff * (attempt + 1))
    latency_ms = (time.monotonic() - start) * 1000.0
    return ProviderResult(
        provider=provider.name,
        status=status,
        latency_ms=latency_ms,
        error_class=classify_status(status),
        attempts=attempts,
        body_bytes=len(resp_body),
    )


def race(
    config: GatewayConfig,
    path: str,
    body: bytes,
    *,
    tier: str = "default",
    race_config: RaceConfig | None = None,
    forward_fn: ForwardFn = forward,
    extra_headers: dict[str, str] | None = None,
) -> RaceReport:
    """Race a tier's providers in parallel; return a classified report.

    Args:
        config: Gateway config supplying the provider chain.
        path: API path (e.g. ``/v1/chat/completions``).
        body: Serialized request payload shared by all providers.
        tier: Provider tier selection (same semantics as the proxy).
        race_config: Tunables; defaults are sane for a handful of providers.
        forward_fn: Injectable transport — tests pass fakes, never network.
        extra_headers: Extra headers forwarded to every provider.
    """
    rc = race_config or RaceConfig()
    providers = list(config.providers_for(tier))
    started = time.monotonic()
    if not providers:
        return RaceReport(results=[], duration_ms=0.0, diagnosis=diagnose_failures([]))

    headers = dict(extra_headers or {})
    results: list[ProviderResult] = []
    pending: dict[futures.Future[ProviderResult], Provider] = {}
    executor = futures.ThreadPoolExecutor(max_workers=max(1, min(len(providers), rc.wave_size * 2)))
    try:
        # Wave-staggered dispatch: submit in chunks, briefly spaced, so the
        # burst does not self-inflict rate limiting.
        for wave_start in range(0, len(providers), max(1, rc.wave_size)):
            wave = providers[wave_start: wave_start + max(1, rc.wave_size)]
            for provider in wave:
                if time.monotonic() - started > rc.hard_timeout:
                    break
                fut = executor.submit(_worker, provider, path, body, headers, rc, forward_fn)
                pending[fut] = provider
                if rc.wave_stagger > 0:
                    time.sleep(rc.wave_stagger)

        grace_deadline: float | None = None
        while pending:
            elapsed = time.monotonic() - started
            if elapsed > rc.hard_timeout:
                # Hard timeout: everything still running is a timeout.
                for fut, provider in list(pending.items()):
                    fut.cancel()
                    results.append(ProviderResult(
                        provider=provider.name,
                        error_class=RaceErrorClass.TIMEOUT,
                        latency_ms=elapsed * 1000.0,
                    ))
                    del pending[fut]
                break
            done, _ = futures.wait(
                list(pending), timeout=0.05, return_when=futures.FIRST_COMPLETED
            )
            for fut in done:
                provider = pending.pop(fut)
                try:
                    results.append(fut.result())
                except Exception as exc:  # transport exploded outside HTTP semantics
                    _logger.warning("race worker for %s raised: %s", provider.name, exc)
                    results.append(ProviderResult(
                        provider=provider.name,
                        error_class=RaceErrorClass.UNKNOWN,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                    ))
            successes = sum(1 for r in results if r.ok)
            if successes >= rc.min_results and grace_deadline is None:
                grace_deadline = time.monotonic() + rc.grace_period
            if grace_deadline is not None and time.monotonic() >= grace_deadline:
                # Early exit: cancel stragglers, record them honestly.
                for fut, provider in list(pending.items()):
                    fut.cancel()
                    results.append(ProviderResult(
                        provider=provider.name,
                        error_class=RaceErrorClass.CANCELLED,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                    ))
                    del pending[fut]
                break
            if not pending:
                break
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    duration_ms = (time.monotonic() - started) * 1000.0
    report = RaceReport(results=results, duration_ms=duration_ms)
    if not report.successes:
        report.diagnosis = diagnose_failures(results)
    return report
