#!/usr/bin/env python3
"""Domain intelligence MCP tools: DNS resolve/walk, WHOIS, certs, subdomains, IP."""

from __future__ import annotations

import json

from aizee_mcp._compat import FastMCP

_MAX_TIMEOUT = 30.0


def _clamp_timeout(value: float) -> float:
    try:
        return max(0.5, min(float(value), _MAX_TIMEOUT))
    except (TypeError, ValueError):
        return 5.0


def register_intel_tools(mcp: FastMCP) -> None:
    """Register domain-intelligence tools (all network-bounded, no scanning)."""

    @mcp.tool()
    def domain_resolve(domain: str, record_type: str = "A", provider: str = "google",
                       timeout: float = 5.0) -> str:
        """Resolve DNS records for a domain via DNS-over-HTTPS (google|cloudflare|alibaba)."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            resp = domain_intel.doh_query(domain, record_type, provider=provider,
                                          timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({
            "ok": True, "domain": domain, "status": resp.rcode_name, "provider": resp.provider,
            "answers": [{"name": a.name, "type": a.rtype, "ttl": a.ttl, "data": a.data}
                        for a in resp.answers]}, ensure_ascii=False)

    @mcp.tool()
    def domain_walk(domain: str, record_type: str = "A", timeout: float = 5.0) -> str:
        """Iterative authoritative DNS walk: root -> TLD -> authoritative, with trace."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            res = domain_intel.AuthoritativeWalker().walk(domain, record_type,
                                                          timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({
            "ok": True, "domain": res.domain, "qtype": res.qtype, "final_code": res.final_code,
            "answers": [{"name": a.name, "type": a.rtype, "ttl": a.ttl, "data": a.data}
                        for a in res.answers],
            "trace": [{"server": s.queried, "action": s.action, "detail": s.detail}
                      for s in res.trace]}, ensure_ascii=False)

    @mcp.tool()
    def domain_whois(domain: str, timeout: float = 5.0) -> str:
        """WHOIS lookup via the IANA referral chain (bounded raw output)."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            out = domain_intel.whois_lookup(domain, timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        out["ok"] = True
        return json.dumps(out, ensure_ascii=False)

    @mcp.tool()
    def domain_certs(domain: str, timeout: float = 10.0) -> str:
        """Certificate-transparency history for a domain via crt.sh (bounded)."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            certs = domain_intel.cert_history(domain, timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({"ok": True, "domain": domain, "count": len(certs),
                           "certificates": certs}, ensure_ascii=False)

    @mcp.tool()
    def domain_subdomains(domain: str, timeout: float = 10.0) -> str:
        """Passive subdomain enumeration from certificate-transparency logs."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            subs = domain_intel.enumerate_subdomains(domain, timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({"ok": True, "domain": domain, "count": len(subs),
                           "subdomains": subs}, ensure_ascii=False)

    @mcp.tool()
    def domain_summary(domain: str, timeout: float = 5.0) -> str:
        """Aggregate DNS summary: A/AAAA/MX/NS/TXT/SOA/CAA via DoH."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            out = domain_intel.domain_summary(domain, timeout=_clamp_timeout(timeout))
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        out["ok"] = True
        return json.dumps(out, ensure_ascii=False)

    @mcp.tool()
    def ip_info(address: str) -> str:
        """Classify an IP locally: version, private/global/loopback, PTR name. No network."""
        from runtime import domain_intel
        from runtime.schemas import ValidationError
        try:
            out = domain_intel.ip_info(address)
        except ValidationError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        out["ok"] = True
        return json.dumps(out, ensure_ascii=False)
