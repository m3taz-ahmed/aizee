"""Tests for runtime.dns_wire - RFC 1035 wire codec."""

from __future__ import annotations

import struct

import pytest

from runtime.dns_wire import DnsError, decode_message, encode_query


def _answer(name_off: int = 0x0C, rtype: int = 1, ttl: int = 300, rdata: bytes = b"\x01\x02\x03\x04") -> bytes:
    return (b"\xc0" + bytes([name_off]) + struct.pack(">HHIH", rtype, 1, ttl, len(rdata)) + rdata)


def _response(qid: int, flags: int, qd: int, an: int, body: bytes) -> bytes:
    return struct.pack(">HHHHHH", qid, flags, qd, an, 0, 0) + body


def test_encode_query_basic() -> None:
    qid, wire = encode_query("example.com", "A", qid=0x1234)
    assert qid == 0x1234
    assert wire[:2] == b"\x12\x34"
    assert wire[4:6] == b"\x00\x01"  # QDCOUNT
    assert b"\x07example\x03com\x00" in wire
    assert wire[-4:] == struct.pack(">HH", 1, 1)


def test_encode_query_dnssec_adds_opt() -> None:
    _, wire = encode_query("example.com", "A", qid=1, dnssec_ok=True)
    assert struct.unpack(">H", wire[10:12])[0] == 1  # ARCOUNT
    assert struct.pack(">H", 41) in wire  # OPT rrtype


def test_encode_query_bad_type() -> None:
    with pytest.raises(DnsError):
        encode_query("example.com", "BOGUS")


def test_decode_a_response_with_compression() -> None:
    question = b"\x07example\x03com\x00" + struct.pack(">HH", 1, 1)
    answer = _answer(0x0C, 1, 300, b"\x5d\xb8\xd8\x22")
    pkt = _response(0x1234, 0x8180, 1, 1, question + answer)
    msg = decode_message(pkt)
    assert msg.qid == 0x1234
    assert msg.questions == [("example.com.", 1)]
    assert len(msg.answers) == 1
    assert msg.answers[0].name == "example.com."
    assert msg.answers[0].parsed == "93.184.216.34"
    assert not msg.truncated and not msg.authoritative


def test_decode_ns_and_glue() -> None:
    question = b"\x03com\x00" + struct.pack(">HH", 2, 1)
    ns_wire = b"\x01a\x0cgtld-servers\x03net\x00"
    ns_rr = (b"\xc0\x0c" + struct.pack(">HHIH", 2, 1, 100, len(ns_wire))
             + ns_wire)
    glue = b"\x01a\x0cgtld-servers\x03net\x00"
    glue_rr = glue + struct.pack(">HHIH", 1, 1, 100, 4) + b"\xc0\x2a\xf4\x01"
    pkt = struct.pack(">HHHHHH", 1, 0x8000, 1, 0, 1, 1) + question + ns_rr + glue_rr
    msg = decode_message(pkt)
    assert len(msg.authorities) == 1
    assert msg.authorities[0].rtype == 2
    assert len(msg.additionals) == 1
    assert msg.additionals[0].parsed == "192.42.244.1"


def test_decode_truncated_and_bad() -> None:
    with pytest.raises(DnsError):
        decode_message(b"\x00" * 11)
    with pytest.raises(DnsError):
        decode_message(b"\xff" * 70000)


def test_compression_loop_rejected() -> None:
    # name at 0x0C points to itself
    pkt = struct.pack(">HHHHHH", 1, 0x8000, 1, 0, 0, 0) + b"\xc0\x0c" + struct.pack(">HH", 1, 1)
    with pytest.raises(DnsError):
        decode_message(pkt)


def test_roundtrip_mx_txt() -> None:
    q = b"\x07example\x03com\x00" + struct.pack(">HH", 15, 1)
    mx_data = b"\x00\x0a" + b"\x04mail\x07example\x03com\x00"
    mx_rr = b"\xc0\x0c" + struct.pack(">HHIH", 15, 1, 60, len(mx_data)) + mx_data
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 1, 0, 0) + q + mx_rr
    msg = decode_message(pkt)
    assert msg.answers[0].parsed == "10 mail.example.com."


def _pkt(qname: bytes, rrs: bytes, an: int = 1, flags: int = 0x8180) -> bytes:
    return struct.pack(">HHHHHH", 1, flags, 1, an, 0, 0) + qname + struct.pack(">HH", 1, 1) + rrs


def _rr(rtype: int, rdata: bytes, name: bytes = b"\xc0\x0c") -> bytes:
    return name + struct.pack(">HHIH", rtype, 1, 60, len(rdata)) + rdata


def test_encode_root_and_idn() -> None:
    _, wire = encode_query(".", "A", qid=1)
    assert wire[12:13] == b"\x00"
    _, wire = encode_query("", "A", qid=1)
    assert wire[12:13] == b"\x00"
    _, wire = encode_query("xn--mnchen-3ya.de", "A", qid=1)  # punycode label
    assert b"xn--mnchen-3ya" in wire
    _, wire = encode_query("münchen.de", "A", qid=1)  # real IDN -> idna encode
    assert b"xn--mnchen-3ya" in wire


def test_encode_label_and_name_too_long() -> None:
    with pytest.raises(DnsError):
        encode_query("x" * 64 + ".com", "A")
    long_name = ".".join(["a" * 60] * 5) + ".com"
    with pytest.raises(DnsError):
        encode_query(long_name, "A")


def test_decode_truncated_pointer_and_label() -> None:
    # RR name is a lone pointer byte (no second byte) at packet end
    q = b"\x03com\x00" + struct.pack(">HH", 1, 1)
    bad = struct.pack(">HHHHHH", 1, 0x8180, 1, 1, 0, 0) + q + b"\xc0"
    with pytest.raises(DnsError):
        decode_message(bad)
    # truncated label: length says 10, packet ends
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0) + b"\x0aabc"
    with pytest.raises(DnsError):
        decode_message(pkt)


def test_decode_reserved_label_types() -> None:
    for first in (0x40, 0x80):
        pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0) + bytes([first, 0x61, 0])
        with pytest.raises(DnsError):
            decode_message(pkt)


def test_decode_idna_fallback_label() -> None:
    # len-3 label of non-ASCII bytes -> idna fails -> ascii replace fallback
    q = b"\x03\x80\x81\x82\x00" + struct.pack(">HH", 1, 1)
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0) + q
    msg = decode_message(pkt)
    assert msg.questions[0][0].endswith(".")


def test_rdata_aaaa_soa_txt_caa_unknown() -> None:
    q = b"\x07example\x03com\x00"
    aaaa = _rr(28, bytes(range(16)))
    soa_rd = b"\x02ns\x00" + b"\x0ahostmaster\x00" + b"\x00" * 10
    soa = _rr(6, soa_rd)
    txt_rd = b"\x05hello\x05world"
    txt = _rr(16, txt_rd)
    caa_rd = bytes([0, 5]) + b"issue" + b"ca.example"
    caa = _rr(257, caa_rd)
    unk = _rr(65280, b"\xde\xad")
    for rrs, want in (
        (aaaa, "1:203:405:607:809:a0b:c0d:e0f"),
        (soa, "ns. hostmaster."),
        (txt, "hello world"),
        (caa, "0 issue ca.example"),
        (unk, ""),
    ):
        pkt = _pkt(q, rrs, 1)
        msg = decode_message(pkt)
        assert msg.answers[0].parsed == want


def test_rdata_parse_exception_returns_empty() -> None:
    q = b"\x07example\x03com\x00"
    # NS rdata with a dangling compression pointer -> DnsError inside -> ""
    bad_ns = _rr(2, b"\xc0\xff")
    pkt = _pkt(q, bad_ns, 1)
    msg = decode_message(pkt)
    assert msg.answers[0].parsed == ""


def test_decode_truncated_rdata() -> None:
    q = b"\x07example\x03com\x00" + struct.pack(">HH", 1, 1)
    rr = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + b"\x01\x02"  # rdlen 4, only 2 bytes
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 1, 0, 0) + q + rr
    with pytest.raises(DnsError):
        decode_message(pkt)


def test_pointer_chain_over_limit() -> None:
    # >64 distinct forward pointers -> DnsError("too many compression pointers")
    body = b""
    for i in range(70):
        target = 12 + (i + 1) * 2
        body += bytes([0xC0 | (target >> 8), target & 0xFF])
    body += b"\x00"
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0) + body
    with pytest.raises(DnsError, match="compression"):
        decode_message(pkt)


def test_double_pointer_jump() -> None:
    # question name at 12 -> offset 30 -> offset 34 -> "x."
    pkt = struct.pack(">HHHHHH", 1, 0x8180, 1, 0, 0, 0)
    pkt += b"\xc0\x1e" + struct.pack(">HH", 1, 1)  # 12-13 name ptr, 14-17 qtype
    pkt += b"\x00" * 12  # padding 18-29
    pkt += b"\xc0\x22"  # at 30: pointer -> 34
    pkt += b"\x00\x00"  # 32-33 pad
    pkt += b"\x01x\x00"  # at 34: labels
    msg = decode_message(pkt)
    assert msg.questions[0][0] == "x."


def test_flags_truncated_authoritative() -> None:
    q = b"\x03com\x00" + struct.pack(">HH", 1, 1)
    pkt = struct.pack(">HHHHHH", 1, 0x8780, 1, 0, 0, 0) + q  # TC+AA set
    msg = decode_message(pkt)
    assert msg.truncated and msg.authoritative
