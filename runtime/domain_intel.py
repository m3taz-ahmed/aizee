#!/usr/bin/env python3
"""Domain intelligence - DNS, WHOIS, certificates, subdomains.

Clean-room Python implementation inspired by domain-digger's *behavior*
(the AGPL Next.js source is not vendored). All transports are injectable
for testing; production defaults use DoH (dns.google / cloudflare-dns) and
the IANA WHOIS referral chain. Bounded results + strict timeouts; no
unbounded scanning - not a crawler.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from runtime import dns_wire
from runtime.schemas import ValidationError

DEFAULT_TIMEOUT: Final = 5.0
_MAX_WALK_STEPS: Final = 32
_MAX_CRT_RESULTS: Final = 200
_MAX_SUBDOMAINS: Final = 100
_DOMAIN_RE: Final = re.compile(
    r"^(?=.{1,253}\.?$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?$",
    re.IGNORECASE)

DOH_ENDPOINTS: Final[dict[str, str]] = {
    "google": "https://dns.google/resolve",
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "alibaba": "https://dns.alidns.com/resolve",
}
IANA_WHOIS: Final = "whois.iana.org"
CRT_SH: Final = "https://crt.sh/"
# IANA IPv4 root hints (long-lived; used when live hint-fetch is disabled)
ROOT_HINTS: Final[tuple[str, ...]] = (
    "198.41.0.4", "170.247.170.2", "192.33.4.12", "199.7.91.13",
    "192.203.230.10", "192.5.5.241", "192.112.36.4", "198.97.190.53",
    "192.36.148.17", "192.58.128.30", "193.0.14.129", "199.7.83.42",
    "202.12.27.33",
)


class QueryKind(str, Enum):
    A = "A"
    AAAA = "AAAA"
    MX = "MX"
    NS = "NS"
    TXT = "TXT"
    SOA = "SOA"
    CNAME = "CNAME"
    CAA = "CAA"
    DS = "DS"
    PTR = "PTR"


def validate_domain(domain: str) -> str:
    """Validate a registrable-style domain; raises ValidationError."""
    d = domain.strip().rstrip(".").lower()
    if not _DOMAIN_RE.match(d + "."):
        raise ValidationError(f"invalid domain: {domain!r}", context={"domain": domain})
    return d


@dataclass
class DnsAnswer:
    name: str
    rtype: str
    ttl: int
    data: str


@dataclass
class DohResponse:
    status: int
    answers: list[DnsAnswer] = field(default_factory=list)
    provider: str = "google"

    @property
    def rcode_name(self) -> str:
        return dns_wire.RCODE_NAMES.get(self.status, str(self.status))


# Transport signature for the iterative walker: (server_ip, wire_query) -> wire_response
WalkerTransport = Callable[[str, bytes, float], bytes]
HttpJson = Callable[[str, float], Any]


def _default_http_json(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={
        "Accept": "application/dns-json",
        "User-Agent": "aiZee-domain-intel/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def doh_query(domain: str, qtype: str = "A", provider: str = "google",
              timeout: float = DEFAULT_TIMEOUT,
              http: HttpJson | None = None) -> DohResponse:
    """Resolve via DNS-over-HTTPS JSON API."""
    endpoint = DOH_ENDPOINTS.get(provider)
    if endpoint is None:
        raise ValidationError(f"unknown DoH provider: {provider}", context={"provider": provider})
    if qtype.upper() not in dns_wire.TYPE_MAP:
        raise ValidationError(f"unknown qtype: {qtype}", context={"qtype": qtype})
    url = f"{endpoint}?{urllib.parse.urlencode({'name': validate_domain(domain), 'type': qtype.upper()})}"
    fetch = http or _default_http_json
    try:
        body = fetch(url, timeout)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"DoH query failed: {exc}", context={"provider": provider}) from exc
    if not isinstance(body, dict):
        raise ValidationError("DoH returned non-object body", context={"provider": provider})
    answers = [
        DnsAnswer(
            name=str(a.get("name", "")), rtype=dns_wire.TYPE_NAMES.get(int(a.get("type", 0)), str(a.get("type"))),
            ttl=int(a.get("TTL", 0)), data=str(a.get("data", "")))
        for a in body.get("Answer") or [] if isinstance(a, dict)
    ]
    return DohResponse(status=int(body.get("Status", -1)), answers=answers, provider=provider)


def _udp_query(server_ip: str, wire: bytes, timeout: float) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(wire, (server_ip, 53))
        data, _ = sock.recvfrom(4096)
    return data


def _tcp_query(server_ip: str, wire: bytes, timeout: float) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((server_ip, 53))
        sock.sendall(len(wire).to_bytes(2, "big") + wire)
        raw = sock.recv(2)
        size = int.from_bytes(raw, "big")
        buf = b""
        while len(buf) < size:
            chunk = sock.recv(size - len(buf))
            if not chunk:
                break
            buf += chunk
    return buf


def _default_transport(server_ip: str, wire: bytes, timeout: float) -> bytes:
    data = _udp_query(server_ip, wire, timeout)
    try:
        if dns_wire.decode_message(data).truncated:
            return _tcp_query(server_ip, wire, timeout)
    except dns_wire.DnsError:
        pass
    return data


@dataclass
class WalkStep:
    queried: str
    action: str  # referral | answer | nxdomain | error
    detail: str = ""


@dataclass
class WalkResult:
    domain: str
    qtype: str
    answers: list[DnsAnswer] = field(default_factory=list)
    trace: list[WalkStep] = field(default_factory=list)
    final_code: str = ""


def _in_bailiwick(ref: str, zone: str) -> bool:
    return ref.rstrip(".").endswith(zone.rstrip(".")) or zone == "."


class AuthoritativeWalker:
    """Iterative resolver: root -> TLD -> authoritative, bailiwick-checked."""

    def __init__(self, transport: WalkerTransport | None = None,
                 root_hints: tuple[str, ...] = ROOT_HINTS) -> None:
        self._transport = transport or _default_transport
        self._hints = root_hints
        self._cache: dict[str, list[str]] = {}  # zone -> nameserver IPs

    def _glue_ips(self, msg: dns_wire.DnsMessage) -> list[str]:
        return [r.parsed for r in msg.additionals if r.rtype == dns_wire.TYPE_MAP["A"] and r.parsed]

    def _ns_names(self, msg: dns_wire.DnsMessage) -> list[str]:
        return [r.parsed for r in msg.authorities if r.rtype == dns_wire.TYPE_MAP["NS"] and r.parsed]

    def _resolve_ns_ip(self, name: str, timeout: float) -> list[str]:
        if name in self._cache:
            return self._cache[name]
        # Parent-zone fallback: cache keys are RR owner names (trailing dot).
        parent = ".".join(name.rstrip(".").split(".")[-2:]) + "."
        cached = self._cache.get(parent)
        if cached:
            return cached
        return []  # caller falls back to glue or re-walks

    def walk(self, domain: str, qtype: str = "A", timeout: float = DEFAULT_TIMEOUT) -> WalkResult:
        domain = validate_domain(domain)
        result = WalkResult(domain=domain, qtype=qtype.upper())
        servers = list(self._hints)
        for _ in range(_MAX_WALK_STEPS):
            if not servers:
                result.trace.append(WalkStep("", "error", "no reachable nameservers"))
                break
            server = servers[0]
            try:
                _qid, wire = dns_wire.encode_query(domain, qtype)
                msg = dns_wire.decode_message(self._transport(server, wire, timeout))
            except (dns_wire.DnsError, OSError) as exc:
                servers = servers[1:]
                result.trace.append(WalkStep(server, "error", str(exc)))
                continue
            result.final_code = dns_wire.RCODE_NAMES.get(msg.rcode, str(msg.rcode))
            answers = [r for r in msg.answers if r.rtype != dns_wire.TYPE_MAP["OPT"]]
            if answers or msg.rcode == 3:
                result.answers = [
                    DnsAnswer(r.name, dns_wire.TYPE_NAMES.get(r.rtype, str(r.rtype)), r.ttl, r.parsed or r.rdata.hex())
                    for r in answers]
                result.trace.append(WalkStep(server, "answer" if answers else "nxdomain", result.final_code))
                break
            # Referral: bailiwick check then prefer glue, else cached NS ips.
            zone = msg.authorities[0].name if msg.authorities else domain
            ns_names = [n for n in self._ns_names(msg) if _in_bailiwick(n, zone)]
            glue = self._glue_ips(msg)
            if glue:
                self._cache[zone] = glue
            next_servers = glue or [ip for n in ns_names for ip in self._resolve_ns_ip(n, timeout)]
            result.trace.append(WalkStep(server, "referral",
                                         f"zone={zone} ns={len(ns_names)} glue={len(glue)}"))
            servers = next_servers
        return result


_WHOIS_REFER_RE: Final = re.compile(r"^refer:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def whois_lookup(domain: str, timeout: float = DEFAULT_TIMEOUT,
                 transport: Callable[[str, str, float], str] | None = None) -> dict[str, Any]:
    """WHOIS via IANA referral chain (whois.iana.org -> refer -> TLD server)."""
    domain = validate_domain(domain)

    def _query(server: str, q: str, t: float) -> str:
        with socket.create_connection((server, 43), timeout=t) as conn:
            conn.sendall((q + "\r\n").encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                chunks.append(data)
        return b"".join(chunks).decode("utf-8", "replace")

    fetch = transport or _query
    try:
        iana = fetch(IANA_WHOIS, domain, timeout)
    except OSError as exc:
        raise ValidationError(f"whois failed: {exc}", context={"server": IANA_WHOIS}) from exc
    refer = _WHOIS_REFER_RE.search(iana)
    out: dict[str, Any] = {"domain": domain, "iana_server": IANA_WHOIS,
                           "refer": refer.group(1) if refer else None, "raw": iana[:16000]}
    if refer:
        try:
            out["tld_raw"] = fetch(refer.group(1), domain, timeout)[:16000]
        except OSError as exc:
            out["tld_error"] = str(exc)
    return out


def cert_history(domain: str, timeout: float = 10.0,
                 http: HttpJson | None = None) -> list[dict[str, Any]]:
    """Certificate-transparency history via crt.sh (bounded)."""
    domain = validate_domain(domain)
    url = f"{CRT_SH}?{urllib.parse.urlencode({'q': f'%.{domain}', 'output': 'json'})}"
    fetch = http or _default_http_json
    try:
        body = fetch(url, timeout)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"crt.sh failed: {exc}", context={"domain": domain}) from exc
    rows: list[Any] = body if isinstance(body, list) else []
    return [{
        "issuer": str(r.get("issuer_name", ""))[:200],
        "common_name": str(r.get("common_name", ""))[:253],
        "not_before": str(r.get("not_before", "")),
        "not_after": str(r.get("not_after", "")),
        "names": str(r.get("name_value", ""))[:4000],
    } for r in rows[:_MAX_CRT_RESULTS] if isinstance(r, dict)]


def enumerate_subdomains(domain: str, timeout: float = 10.0,
                         http: HttpJson | None = None) -> list[str]:
    """Passive subdomain enumeration from crt.sh name_value sets."""
    names: set[str] = set()
    for row in cert_history(domain, timeout=timeout, http=http):
        for n in row["names"].splitlines():
            n = n.strip().lower().lstrip("*.")
            if n.endswith(domain) and n not in names:
                names.add(n)
                if len(names) >= _MAX_SUBDOMAINS:
                    return sorted(names)
    return sorted(names)


def ip_info(ip: str) -> dict[str, Any]:
    """Classify an IP address locally (no external calls, no tracking)."""
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError as exc:
        raise ValidationError(f"invalid IP: {ip!r}", context={"ip": ip}) from exc
    return {
        "ip": str(addr), "version": addr.version,
        "is_private": addr.is_private, "is_global": addr.is_global,
        "is_loopback": addr.is_loopback, "is_multicast": addr.is_multicast,
        "reverse_ptr": addr.reverse_pointer,
    }


def domain_summary(domain: str, timeout: float = DEFAULT_TIMEOUT,
                   http: HttpJson | None = None) -> dict[str, Any]:
    """Aggregate DNS summary: A/AAAA/MX/NS/TXT/SOA/CAA via DoH."""
    domain = validate_domain(domain)
    out: dict[str, Any] = {"domain": domain, "records": {}}
    for qt in ("A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA"):
        try:
            resp = doh_query(domain, qt, timeout=timeout, http=http)
            out["records"][qt] = [{"data": a.data, "ttl": a.ttl} for a in resp.answers]
            out.setdefault("status", resp.rcode_name)
        except ValidationError as exc:
            out["records"][qt] = {"error": str(exc)}
    return out
