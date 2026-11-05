"""Tests for aizee_mcp.tools.intel_tools - MCP tool registration + dispatch."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aizee_mcp._compat import FastMCP
from aizee_mcp.tools import register_intel_tools
from runtime import domain_intel


def _tools() -> dict[str, Any]:
    m = FastMCP("t")
    register_intel_tools(m)
    mgr = getattr(m, "_tool_manager", None) or getattr(m, "tool_manager", None)
    tools = getattr(mgr, "_tools", None) or getattr(mgr, "tools", None)
    assert isinstance(tools, dict)
    return tools


def _fn(tools: dict[str, Any], name: str) -> Any:
    t = tools[name]
    return getattr(t, "fn", None) or getattr(t, "function", None) or t


def test_clamp_timeout_bad_type() -> None:
    from aizee_mcp.tools.intel_tools import _clamp_timeout

    assert _clamp_timeout("bad") == 5.0  # type: ignore[arg-type]
    assert _clamp_timeout(999.0) == 30.0
    assert _clamp_timeout(0.0) == 0.5


def test_registers_seven_tools() -> None:
    tools = _tools()
    for name in ("domain_resolve", "domain_walk", "domain_whois", "domain_certs",
                 "domain_subdomains", "domain_summary", "ip_info"):
        assert name in tools


def test_domain_resolve_ok_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(domain_intel, "_default_http_json",
                        lambda url, timeout: {"Status": 0, "Answer": [
                            {"name": "x.example", "type": 1, "TTL": 9, "data": "1.2.3.4"}]})
    fn = _fn(_tools(), "domain_resolve")
    out = json.loads(fn("x.example", "A"))
    assert out["ok"] and out["answers"][0]["data"] == "1.2.3.4"
    out = json.loads(fn("not a domain", "A"))
    assert out["ok"] is False


def test_domain_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    class _W:
        def walk(self, domain: str, qtype: str, timeout: float = 5.0) -> domain_intel.WalkResult:
            domain_intel.validate_domain(domain)
            r = domain_intel.WalkResult(domain=domain, qtype=qtype)
            r.final_code = "NOERROR"
            r.answers.append(domain_intel.DnsAnswer("x.", "A", 1, "2.3.4.5"))
            r.trace.append(domain_intel.WalkStep("8.8.8.8", "answer", ""))
            return r
    monkeypatch.setattr(domain_intel, "AuthoritativeWalker", _W)
    out = json.loads(_fn(_tools(), "domain_walk")("x.example"))
    assert out["ok"] and out["answers"][0]["data"] == "2.3.4.5"
    out = json.loads(_fn(_tools(), "domain_walk")("bad domain"))
    assert out["ok"] is False


def test_domain_whois(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(domain_intel, "whois_lookup",
                        lambda domain, timeout=5.0: {"domain": domain, "refer": "w.tld", "raw": "x"})
    out = json.loads(_fn(_tools(), "domain_whois")("x.example"))
    assert out["ok"] and out["refer"] == "w.tld"
    monkeypatch.setattr(domain_intel, "whois_lookup",
                        lambda domain, timeout=5.0: (_ for _ in ()).throw(
                            domain_intel.ValidationError("bad", context={})))
    out = json.loads(_fn(_tools(), "domain_whois")("bad"))
    assert out["ok"] is False


def test_domain_certs_and_subdomains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(domain_intel, "cert_history",
                        lambda domain, timeout=10.0: [{"common_name": "a.x", "issuer": "i"}])
    out = json.loads(_fn(_tools(), "domain_certs")("x.example"))
    assert out["ok"] and out["count"] == 1
    monkeypatch.setattr(domain_intel, "cert_history",
                        lambda domain, timeout=10.0: (_ for _ in ()).throw(
                            domain_intel.ValidationError("crt fail", context={})))
    out = json.loads(_fn(_tools(), "domain_certs")("x"))
    assert out["ok"] is False
    monkeypatch.setattr(domain_intel, "enumerate_subdomains",
                        lambda domain, timeout=10.0: ["a.x.example"])
    out = json.loads(_fn(_tools(), "domain_subdomains")("x.example"))
    assert out["ok"] and out["subdomains"] == ["a.x.example"]
    monkeypatch.setattr(domain_intel, "enumerate_subdomains",
                        lambda domain, timeout=10.0: (_ for _ in ()).throw(
                            domain_intel.ValidationError("e", context={})))
    out = json.loads(_fn(_tools(), "domain_subdomains")("x"))
    assert out["ok"] is False


def test_domain_summary_and_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(domain_intel, "domain_summary",
                        lambda domain, timeout=5.0: {"domain": domain, "records": {"A": []}})
    out = json.loads(_fn(_tools(), "domain_summary")("x.example"))
    assert out["ok"] and "records" in out
    monkeypatch.setattr(domain_intel, "domain_summary",
                        lambda domain, timeout=5.0: (_ for _ in ()).throw(
                            domain_intel.ValidationError("e", context={})))
    out = json.loads(_fn(_tools(), "domain_summary")("x"))
    assert out["ok"] is False

    out = json.loads(_fn(_tools(), "ip_info")("127.0.0.1"))
    assert out["ok"] and out["is_loopback"]
    out = json.loads(_fn(_tools(), "ip_info")("zzz"))
    assert out["ok"] is False
