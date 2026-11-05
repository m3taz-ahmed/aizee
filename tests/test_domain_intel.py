"""Tests for runtime.domain_intel - DNS/WHOIS/certs with injected transports."""

from __future__ import annotations

import struct
from typing import Any

import pytest

from runtime import domain_intel
from runtime.schemas import ValidationError


def _fake_http(payload: Any) -> Any:
    def fetch(_url: str, _timeout: float) -> Any:
        return payload
    return fetch


def test_validate_domain() -> None:
    assert domain_intel.validate_domain("Example.COM.") == "example.com"
    for bad in ("", "-bad.com", "no_tld", "a" * 64 + ".com", "x" * 260 + ".com"):
        with pytest.raises(ValidationError):
            domain_intel.validate_domain(bad)


def test_doh_query_parses_answers() -> None:
    body = {"Status": 0, "Answer": [{"name": "x.example", "type": 1, "TTL": 60, "data": "1.2.3.4"}]}
    resp = domain_intel.doh_query("x.example", "A", http=_fake_http(body))
    assert resp.rcode_name == "NOERROR"
    assert resp.answers[0].data == "1.2.3.4"
    assert resp.provider == "google"


def test_doh_query_bad_provider() -> None:
    with pytest.raises(ValidationError):
        domain_intel.doh_query("x.example", "A", provider="bogus")


def test_doh_query_transport_failure() -> None:
    def boom(_u: str, _t: float) -> Any:
        raise OSError("nope")
    with pytest.raises(ValidationError):
        domain_intel.doh_query("x.example", "A", http=boom)


def _a_response(qid: int, name: str, ip: bytes, flags: int = 0x8180) -> bytes:
    question = b""
    for label in name.rstrip(".").split("."):
        question += bytes([len(label)]) + label.encode()
    question += b"\x00" + struct.pack(">HH", 1, 1)
    rr = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + ip
    return struct.pack(">HHHHHH", qid, flags, 1, 1, 0, 0) + question + rr


def _ns_referral(name: str, zone: str) -> bytes:
    question = b""
    for label in name.rstrip(".").split("."):
        question += bytes([len(label)]) + label.encode()
    question += b"\x00" + struct.pack(">HH", 1, 1)
    # authority: zone NS ns1.zone (wire-format labels)
    ns_name = b"\x03ns1" + bytes([len(zone)]) + zone.encode() + b"\x00"
    auth = b"\xc0\x0c" + struct.pack(">HHIH", 2, 1, 60, len(ns_name)) + ns_name
    # additional: ns1.zone A 10.0.0.1  (uncompressed name)
    glue_name = b"\x03ns1" + bytes([len(zone)]) + zone.encode() + b"\x00"
    add = glue_name + struct.pack(">HHIH", 1, 1, 60, 4) + b"\x0a\x00\x00\x01"
    return struct.pack(">HHHHHH", 1, 0x8000, 1, 0, 1, 1) + question + auth + add


def test_walker_follows_referral_then_answers() -> None:
    calls: list[str] = []

    def transport(server: str, wire: bytes, timeout: float) -> bytes:
        calls.append(server)
        if server == domain_intel.ROOT_HINTS[0]:
            return _ns_referral("x.example", "example")
        return _a_response(1, "x.example", b"\x09\x08\x07\x06")

    w = domain_intel.AuthoritativeWalker(transport=transport,
                                         root_hints=(domain_intel.ROOT_HINTS[0],))
    res = w.walk("x.example", "A")
    assert res.answers[0].data == "9.8.7.6"
    assert [s.action for s in res.trace] == ["referral", "answer"]
    assert res.final_code == "NOERROR"


def test_walker_server_error_falls_to_next_hint() -> None:
    def transport(server: str, wire: bytes, timeout: float) -> bytes:
        if server == "1.1.1.1":
            raise OSError("timeout")
        return _a_response(1, "x.example", b"\x01\x01\x01\x01")

    w = domain_intel.AuthoritativeWalker(transport=transport, root_hints=("1.1.1.1", "2.2.2.2"))
    res = w.walk("x.example", "A")
    assert res.trace[0].action == "error"
    assert res.answers[0].data == "1.1.1.1"


def test_whois_follows_refer() -> None:
    sent: list[tuple[str, str]] = []

    def transport(server: str, q: str, t: float) -> str:
        sent.append((server, q))
        if server == domain_intel.IANA_WHOIS:
            return "domain: EXAMPLE\nrefer: whois.example-tld\n"
        return "Registrar: Test Inc."

    out = domain_intel.whois_lookup("x.example", transport=transport)
    assert out["refer"] == "whois.example-tld"
    assert "Registrar" in out["tld_raw"]
    assert sent[1][0] == "whois.example-tld"


def test_cert_history_and_subdomains() -> None:
    rows = [{"issuer_name": "CA X", "common_name": "a.example.com",
             "not_before": "2024-01-01", "not_after": "2025-01-01",
             "name_value": "a.example.com\n*.b.example.com\nother.net"}]
    certs = domain_intel.cert_history("example.com", http=_fake_http(rows))
    assert certs[0]["common_name"] == "a.example.com"
    subs = domain_intel.enumerate_subdomains("example.com", http=_fake_http(rows))
    assert "a.example.com" in subs and "b.example.com" in subs
    assert "other.net" not in subs


def test_ip_info() -> None:
    out = domain_intel.ip_info("192.168.1.1")
    assert out["version"] == 4 and out["is_private"] and not out["is_global"]
    out6 = domain_intel.ip_info("::1")
    assert out6["version"] == 6 and out6["is_loopback"]
    with pytest.raises(ValidationError):
        domain_intel.ip_info("not-an-ip")


def test_domain_summary_aggregates() -> None:
    body = {"Status": 0, "Answer": [{"name": "x.example", "type": 1, "TTL": 1, "data": "1.1.1.1"}]}
    out = domain_intel.domain_summary("x.example", http=_fake_http(body))
    assert set(out["records"]) == {"A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA"}
    assert out["records"]["A"][0]["data"] == "1.1.1.1"


def test_default_http_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def read(self) -> bytes:
            return b'{"Status":0,"Answer":[]}'

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp())
    out = domain_intel._default_http_json("https://example.test/x", 1.0)
    assert out["Status"] == 0
    resp = domain_intel.doh_query("x.example", "A")  # real code path through patched urlopen
    assert resp.rcode_name == "NOERROR"


def test_doh_query_bad_qtype_and_non_dict() -> None:
    with pytest.raises(ValidationError):
        domain_intel.doh_query("x.example", "BOGUS", http=_fake_http({}))
    with pytest.raises(ValidationError):
        domain_intel.doh_query("x.example", "A", http=_fake_http([1, 2]))


def test_udp_and_tcp_query(monkeypatch: pytest.MonkeyPatch) -> None:
    class _UdpSock:
        def __init__(self) -> None:
            self.sent: tuple[bytes, tuple] | None = None

        def settimeout(self, t: float) -> None: self.t = t
        def sendto(self, data: bytes, addr: tuple) -> None: self.sent = (data, addr)
        def recvfrom(self, n: int) -> tuple[bytes, tuple]: return (b"\x00" * 12, ("s", 53))
        def __enter__(self) -> _UdpSock: return self
        def __exit__(self, *a: object) -> None: return None

    monkeypatch.setattr("socket.socket", lambda *a: _UdpSock())
    data = domain_intel._udp_query("9.9.9.9", b"\x00\x01", 1.0)
    assert data == b"\x00" * 12

    class _TcpSock(_UdpSock):
        def connect(self, addr: tuple) -> None: self.addr = addr
        def sendall(self, data: bytes) -> None: self.last = data
        def recv(self, n: int) -> bytes: return b"\x00\x0c" if n == 2 else b"\x00" * n

    monkeypatch.setattr("socket.socket", lambda *a: _TcpSock())
    data = domain_intel._tcp_query("9.9.9.9", b"\x00\x01", 1.0)
    assert data == b"\x00" * 12


def test_default_transport_udp_then_tcp_on_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    tc_pkt = struct.pack(">HHHHHH", 1, 0x8380, 0, 0, 0, 0)  # TC set
    ok_pkt = struct.pack(">HHHHHH", 1, 0x8180, 0, 0, 0, 0)

    monkeypatch.setattr(domain_intel, "_udp_query", lambda s, w, t: calls.append("udp") or tc_pkt)
    monkeypatch.setattr(domain_intel, "_tcp_query", lambda s, w, t: calls.append("tcp") or ok_pkt)
    out = domain_intel._default_transport("8.8.8.8", b"\x00", 1.0)
    assert calls == ["udp", "tcp"]
    assert out == ok_pkt

    # UDP data that doesn't parse -> returned as-is (no TCP retry)
    monkeypatch.setattr(domain_intel, "_udp_query", lambda s, w, t: b"\xde\xad")
    out = domain_intel._default_transport("8.8.8.8", b"\x00", 1.0)
    assert out == b"\xde\xad"


def test_walker_nxdomain_and_no_servers() -> None:
    nx_pkt = struct.pack(">HHHHHH", 1, 0x8183, 0, 0, 0, 0)
    w = domain_intel.AuthoritativeWalker(transport=lambda s, w2, t: nx_pkt,
                                         root_hints=("9.9.9.9",))
    res = w.walk("gone.example", "A")
    assert res.final_code == "NXDOMAIN"
    assert res.trace[-1].action == "nxdomain"
    assert res.answers == []

    w2 = domain_intel.AuthoritativeWalker(transport=lambda s, w2, t: (_ for _ in ()).throw(OSError("x")),
                                          root_hints=())
    res2 = w2.walk("x.example", "A")
    assert res2.trace[-1].action == "error"


def test_walker_decode_error_next_server() -> None:
    seen: list[str] = []

    def transport(server: str, wire: bytes, t: float) -> bytes:
        seen.append(server)
        if server == "1.1.1.1":
            return b"\xff"  # undecodable, but not an exception
        return _a_response(1, "x.example", b"\x04\x04\x04\x04")

    w = domain_intel.AuthoritativeWalker(transport=transport, root_hints=("1.1.1.1", "2.2.2.2"))
    res = w.walk("x.example", "A")
    assert seen == ["1.1.1.1", "2.2.2.2"]
    assert res.answers[0].data == "4.4.4.4"


def test_tcp_query_early_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Sock:
        def settimeout(self, t: float) -> None: pass
        def connect(self, a: tuple) -> None: pass
        def sendall(self, d: bytes) -> None: pass
        def recv(self, n: int) -> bytes: return b"\x00\x04" if n == 2 else b""
        def __enter__(self) -> _Sock: return self
        def __exit__(self, *a: object) -> None: return None
    monkeypatch.setattr("socket.socket", lambda *a: _Sock())
    assert domain_intel._tcp_query("9.9.9.9", b"\x00", 1.0) == b""


def test_default_transport_valid_udp_skips_tcp(monkeypatch: pytest.MonkeyPatch) -> None:
    ok_pkt = struct.pack(">HHHHHH", 1, 0x8180, 0, 0, 0, 0)  # valid, NOT truncated
    monkeypatch.setattr(domain_intel, "_udp_query", lambda s, w, t: ok_pkt)
    monkeypatch.setattr(domain_intel, "_tcp_query",
                        lambda s, w, t: (_ for _ in ()).throw(AssertionError("no tcp")))
    assert domain_intel._default_transport("8.8.8.8", b"\x00", 1.0) == ok_pkt


def test_resolve_ns_ip_cache_paths() -> None:
    w = domain_intel.AuthoritativeWalker(transport=lambda s, w2, t: b"")
    w._cache["ns1.zone.example."] = ["1.2.3.4"]
    assert w._resolve_ns_ip("ns1.zone.example.", 1.0) == ["1.2.3.4"]
    w._cache["zone.example."] = ["5.6.7.8"]
    assert w._resolve_ns_ip("x.zone.example.", 1.0) == ["5.6.7.8"]  # parent-zone fallback
    assert w._resolve_ns_ip("uncached.", 1.0) == []


def test_walker_step_cap_exhaustion() -> None:
    # every query returns the same referral with glue -> loop never converges
    w = domain_intel.AuthoritativeWalker(
        transport=lambda s, w2, t: _ns_referral("x.example", "example"),
        root_hints=("9.9.9.9",))
    res = w.walk("x.example", "A")
    assert len(res.trace) == domain_intel._MAX_WALK_STEPS
    assert res.answers == []


def test_walker_referral_without_glue_ends() -> None:
    # referral with NS names but NO glue A records and uncached names
    q = b"\x07example\x03com\x00" + struct.pack(">HH", 1, 1)
    ns_name = b"\x03ns1\x07example\x03com\x00"
    auth = b"\xc0\x0c" + struct.pack(">HHIH", 2, 1, 60, len(ns_name)) + ns_name
    pkt = struct.pack(">HHHHHH", 1, 0x8000, 1, 0, 1, 0) + q + auth
    w = domain_intel.AuthoritativeWalker(transport=lambda s, w2, t: pkt,
                                         root_hints=("9.9.9.9",))
    res = w.walk("x.example", "A")
    assert res.trace[-1].action == "error"
    assert res.answers == []


def test_whois_socket_and_refer_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Conn:
        def sendall(self, data: bytes) -> None: self.sent = data
        def recv(self, n: int) -> bytes:
            if getattr(self, "done", False):
                return b""
            self.done = True
            return b"refer: whois.tld\nwhois: x\n"
        def __enter__(self) -> _Conn: return self
        def __exit__(self, *a: object) -> None: return None

    monkeypatch.setattr("socket.create_connection", lambda *a, **k: _Conn())
    out = domain_intel.whois_lookup("x.example")  # default transport via patched socket
    assert out["refer"] == "whois.tld"

    def transport(server: str, q: str, t: float) -> str:
        if server == domain_intel.IANA_WHOIS:
            return "refer: whois.tld\n"
        raise OSError("refused")

    out2 = domain_intel.whois_lookup("x.example", transport=transport)
    assert out2["tld_error"] == "refused"

    out3 = domain_intel.whois_lookup("x.example", transport=lambda s, q, t: "no refer here\n")
    assert "tld_raw" not in out3

    def iana_boom(server: str, q: str, t: float) -> str:
        raise OSError("iana down")
    with pytest.raises(ValidationError):
        domain_intel.whois_lookup("x.example", transport=iana_boom)


def test_cert_history_error_and_nonlist() -> None:
    def boom(_u: str, _t: float) -> object:
        raise OSError("crt down")
    with pytest.raises(ValidationError):
        domain_intel.cert_history("x.example", http=boom)
    assert domain_intel.cert_history("x.example", http=_fake_http({"not": "list"})) == []


def test_subdomains_cap_and_filter() -> None:
    names = "\n".join(f"sub{i}.example.com" for i in range(120))
    rows = [{"issuer_name": "i", "common_name": "x", "not_before": "", "not_after": "",
             "name_value": names + "\nother.net"}]
    subs = domain_intel.enumerate_subdomains("example.com", http=_fake_http(rows))
    assert len(subs) == domain_intel._MAX_SUBDOMAINS
    assert all(s.endswith("example.com") for s in subs)


def test_ip_info_variants() -> None:
    g = domain_intel.ip_info("8.8.8.8")
    assert g["is_global"] and not g["is_private"] and g["reverse_ptr"].endswith(".in-addr.arpa")
    m = domain_intel.ip_info("224.0.0.1")
    assert m["is_multicast"]


def test_summary_per_record_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real = domain_intel.doh_query

    def patched(domain: str, qt: str, **kw: object) -> domain_intel.DohResponse:
        if qt == "TXT":
            raise ValidationError("doh txt fail", context={})
        return real(domain, qt, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(domain_intel, "doh_query", patched)
    out = domain_intel.domain_summary("x.example", http=_fake_http({"Status": 0, "Answer": []}))
    assert "error" in out["records"]["TXT"]
    assert out["records"]["A"] == []
