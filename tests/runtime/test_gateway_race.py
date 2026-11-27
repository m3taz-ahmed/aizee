"""Tests for runtime/gateway_race.py — evaluation-only provider racing."""

from __future__ import annotations

import time

import pytest

from runtime.gateway_proxy import GatewayConfig, Provider
from runtime.gateway_race import (
    ProviderResult,
    RaceConfig,
    RaceErrorClass,
    _worker,
    classify_status,
    diagnose_failures,
    race,
)


def _config(*names: str) -> GatewayConfig:
    return GatewayConfig(
        providers=tuple(
            Provider(name=n, base_url="http://127.0.0.1:1", kind="openai") for n in names
        )
    )


def _ok_forward(status: int = 200, body: bytes = b"{}", delay: float = 0.0):
    def fwd(provider, path, body_bytes, headers):
        if delay:
            time.sleep(delay)
        return status, body, {}
    return fwd


FAST = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=5.0,
                  wave_size=2, wave_stagger=0.0, retries_on_429=1, retry_backoff=0.01)


class TestClassifyStatus:
    def test_success(self):
        assert classify_status(200) is None
        assert classify_status(299) is None

    def test_timeout_zero(self):
        assert classify_status(0) is RaceErrorClass.TIMEOUT

    def test_auth(self):
        assert classify_status(401) is RaceErrorClass.AUTH
        assert classify_status(403) is RaceErrorClass.AUTH

    def test_credits(self):
        assert classify_status(402) is RaceErrorClass.CREDITS

    def test_not_found(self):
        assert classify_status(404) is RaceErrorClass.NOT_FOUND

    def test_rate_limit(self):
        assert classify_status(429) is RaceErrorClass.RATE_LIMIT

    def test_server(self):
        assert classify_status(500) is RaceErrorClass.SERVER
        assert classify_status(503) is RaceErrorClass.SERVER

    def test_unknown(self):
        assert classify_status(400) is RaceErrorClass.UNKNOWN


class TestProviderResult:
    def test_ok_true(self):
        r = ProviderResult(provider="x", status=200, error_class=None)
        assert r.ok is True
        assert r.to_dict()["error_class"] is None

    def test_ok_false(self):
        r = ProviderResult(provider="x", status=500, error_class=RaceErrorClass.SERVER)
        assert r.ok is False
        d = r.to_dict()
        assert d["error_class"] == "server"
        assert d["ok"] is False


class TestDiagnose:
    def test_empty_results(self):
        assert "no providers" in diagnose_failures([])

    def test_all_ok_returns_empty(self):
        out = diagnose_failures([ProviderResult(provider="a", error_class=None)])
        assert out == ""

    def test_dominant_hint(self):
        results = [
            ProviderResult(provider="a", error_class=RaceErrorClass.AUTH),
            ProviderResult(provider="b", error_class=RaceErrorClass.AUTH),
            ProviderResult(provider="c", error_class=RaceErrorClass.SERVER),
        ]
        out = diagnose_failures(results)
        assert "auth x2" in out
        assert "API keys" in out

    def test_each_hint_class(self):
        for cls, fragment in [
            (RaceErrorClass.CREDITS, "billing"),
            (RaceErrorClass.RATE_LIMIT, "wave_stagger"),
            (RaceErrorClass.TIMEOUT, "connectivity"),
            (RaceErrorClass.NOT_FOUND, "stale"),
            (RaceErrorClass.SERVER, "upstream incident"),
        ]:
            out = diagnose_failures([ProviderResult(provider="a", error_class=cls)])
            assert fragment in out

    def test_unknown_hint_fallback(self):
        out = diagnose_failures([ProviderResult(provider="a", error_class=RaceErrorClass.UNKNOWN)])
        assert "inspect raw statuses" in out


class TestWorker:
    def test_success_first_try(self):
        p = Provider(name="a", base_url="http://x")
        r = _worker(p, "/v1/x", b"{}", {}, FAST, _ok_forward())
        assert r.ok
        assert r.attempts == 1
        assert r.body_bytes == 2

    def test_retry_429_then_success(self):
        calls = {"n": 0}

        def flaky(provider, path, body, headers):
            calls["n"] += 1
            return (429 if calls["n"] == 1 else 200), b"ok", {}

        p = Provider(name="a", base_url="http://x")
        r = _worker(p, "/v1/x", b"{}", {}, FAST, flaky)
        assert r.ok
        assert r.attempts == 2

    def test_retry_exhausted(self):
        p = Provider(name="a", base_url="http://x")
        r = _worker(p, "/v1/x", b"{}", {}, FAST, _ok_forward(status=429))
        assert r.error_class is RaceErrorClass.RATE_LIMIT
        assert r.attempts == 2  # 1 + retries_on_429

    def test_no_retry_when_disabled(self):
        cfg = RaceConfig(retries_on_429=0, wave_stagger=0.0)
        p = Provider(name="a", base_url="http://x")
        r = _worker(p, "/v1/x", b"{}", {}, cfg, _ok_forward(status=429))
        assert r.attempts == 1


class TestRace:
    def test_empty_providers(self):
        report = race(GatewayConfig(providers=()), "/v1/x", b"{}", race_config=FAST)
        assert report.results == []
        assert "no providers" in report.diagnosis
        assert report.winner == ""

    @pytest.mark.slow  # real sleep needed — latency ordering is the assertion
    def test_all_success_winner_fastest(self):
        def fwd(provider, path, body, headers):
            if provider.name == "slow":
                time.sleep(0.3)
            return 200, b"{}", {}

        cfg = RaceConfig(min_results=2, grace_period=0.5, hard_timeout=5.0, wave_stagger=0.0)
        report = race(_config("fast", "slow"), "/v1/x", b"{}", race_config=cfg, forward_fn=fwd)
        assert len(report.successes) == 2
        assert report.winner == "fast"
        assert report.diagnosis == ""
        d = report.to_dict()
        assert d["successes"] == 2
        assert d["providers"] == 2

    @pytest.mark.slow  # real sleep needed — cancellation timing is the assertion
    def test_early_exit_cancels_straggler(self):
        def fwd(provider, path, body, headers):
            if provider.name == "slow":
                time.sleep(2.0)
            return 200, b"{}", {}

        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=5.0,
                         wave_size=2, wave_stagger=0.0)
        report = race(_config("fast", "slow"), "/v1/x", b"{}", race_config=cfg, forward_fn=fwd)
        statuses = {r.provider: r.error_class for r in report.results}
        assert statuses["fast"] is None
        assert statuses["slow"] is RaceErrorClass.CANCELLED
        assert report.duration_ms < 1500

    @pytest.mark.slow  # real sleep needed — the provider must actually hang
    def test_hard_timeout_recorded(self):
        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=0.15,
                         wave_size=1, wave_stagger=0.0)
        report = race(
            _config("hang"), "/v1/x", b"{}", race_config=cfg,
            forward_fn=_ok_forward(delay=2.0),
        )
        assert report.results[0].error_class is RaceErrorClass.TIMEOUT
        assert report.successes == []
        assert report.diagnosis  # zero successes → aggregated diagnosis

    def test_dispatch_aborted_when_already_overtime(self):
        cfg = RaceConfig(hard_timeout=-1.0, wave_stagger=0.0)
        report = race(_config("a", "b"), "/v1/x", b"{}", race_config=cfg,
                      forward_fn=_ok_forward())
        # negative hard timeout → dispatch loop breaks before submitting
        assert report.results == []
        assert report.diagnosis

    def test_worker_exception_unknown(self):
        def boom(provider, path, body, headers):
            raise RuntimeError("transport exploded")

        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=2.0, wave_stagger=0.0)
        report = race(_config("x"), "/v1/x", b"{}", race_config=cfg, forward_fn=boom)
        assert report.results[0].error_class is RaceErrorClass.UNKNOWN

    def test_zero_success_diagnosis(self):
        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=2.0, wave_stagger=0.0)
        report = race(
            _config("a", "b"), "/v1/x", b"{}", race_config=cfg,
            forward_fn=_ok_forward(status=401),
        )
        assert report.successes == []
        assert "auth" in report.diagnosis
        assert report.winner == ""

    def test_extra_headers_forwarded(self):
        seen: dict[str, str] = {}

        def fwd(provider, path, body, headers):
            seen.update(headers)
            return 200, b"{}", {}

        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=2.0, wave_stagger=0.0)
        race(_config("a"), "/v1/x", b"{}", race_config=cfg, forward_fn=fwd,
             extra_headers={"x-test": "yes"})
        assert seen.get("x-test") == "yes"

    def test_wave_stagger_sleep_skipped_when_zero(self):
        # wave_stagger=0 → no per-submit sleep; still submits all providers
        report = race(_config("a", "b", "c"), "/v1/x", b"{}", race_config=FAST,
                      forward_fn=_ok_forward())
        assert len(report.results) == 3

    def test_wave_stagger_positive_still_submits_all(self):
        # stagger > 0 exercises the per-submit pacing branch; in fast tier the
        # sleep itself is mocked away, so this stays instant.
        cfg = RaceConfig(min_results=1, grace_period=0.05, hard_timeout=2.0,
                         wave_size=1, wave_stagger=0.5)
        report = race(_config("a", "b"), "/v1/x", b"{}", race_config=cfg,
                      forward_fn=_ok_forward())
        assert report.winner in ("a", "b")
