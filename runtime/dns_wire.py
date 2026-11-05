#!/usr/bin/env python3
"""DNS wire-format codec - minimal RFC 1035 subset for iterative resolution.

Clean-room implementation (inspired by domain-digger's resolver behavior,
not its AGPL source). Encodes queries, decodes responses with compression
pointer support, extracts RRs. No external dependencies.
"""

from __future__ import annotations

import ipaddress
import random
import struct
from dataclasses import dataclass, field
from typing import Final

MAX_DNS_PACKET: Final = 65_535
_MAX_NAME_POINTERS: Final = 64  # compression-loop guard
_MAX_LABEL_LEN: Final = 63
_MAX_NAME_LEN: Final = 253

TYPE_MAP: Final[dict[str, int]] = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15,
    "TXT": 16, "AAAA": 28, "OPT": 41, "DS": 43, "RRSIG": 46,
    "DNSKEY": 48, "NSEC": 47, "CAA": 257, "ANY": 255,
}
TYPE_NAMES: Final[dict[int, str]] = {v: k for k, v in TYPE_MAP.items()}
CLASS_IN: Final = 1

RCODE_NAMES: Final[dict[int, str]] = {
    0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN",
    4: "NOTIMP", 5: "REFUSED",
}


class DnsError(ValueError):
    """Malformed packet or unsupported feature."""


@dataclass(frozen=True)
class ResourceRecord:
    name: str
    rtype: int
    rclass: int
    ttl: int
    rdata: bytes
    parsed: str = ""


@dataclass(frozen=True)
class DnsMessage:
    qid: int
    flags: int
    rcode: int
    questions: list[tuple[str, int]] = field(default_factory=list)
    answers: list[ResourceRecord] = field(default_factory=list)
    authorities: list[ResourceRecord] = field(default_factory=list)
    additionals: list[ResourceRecord] = field(default_factory=list)

    @property
    def truncated(self) -> bool:
        return bool(self.flags & 0x0200)

    @property
    def authoritative(self) -> bool:
        return bool(self.flags & 0x0400)


def _encode_name(name: str) -> bytes:
    name = name.rstrip(".")
    if not name:
        return b"\x00"
    out = bytearray()
    for label in name.split("."):
        raw = label.encode("idna") if any(ord(c) > 127 for c in label) else label.encode("ascii", "strict")
        if len(raw) > _MAX_LABEL_LEN:
            raise DnsError(f"label too long: {label!r}")
        out.append(len(raw))
        out += raw
    if len(out) > _MAX_NAME_LEN:
        raise DnsError(f"name too long: {name!r}")
    out.append(0)
    return bytes(out)


def encode_query(name: str, qtype: str | int, *, qid: int | None = None,
                 dnssec_ok: bool = False) -> tuple[int, bytes]:
    """Build a single-question query. Returns (qid, wire_bytes)."""
    qid = random.SystemRandom().randrange(0x10000) if qid is None else qid
    qt = TYPE_MAP.get(qtype.upper()) if isinstance(qtype, str) else qtype
    if qt is None:
        raise DnsError(f"unknown qtype: {qtype!r}")
    flags = 0x0100  # RD=1
    header = struct.pack(">HHHHHH", qid, flags, 1, 0, 0, 1 if dnssec_ok else 0)
    question = _encode_name(name) + struct.pack(">HH", qt, CLASS_IN)
    if dnssec_ok:  # EDNS0 OPT: payload 4096, DO bit set
        opt = b"\x00" + struct.pack(">HHIH", 41, 4096, 0x00008000, 0)
        return qid, header + question + opt
    return qid, header + question


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    pos, jumped, end_pos, seen = offset, False, offset, set()
    for _ in range(_MAX_NAME_POINTERS):
        if pos >= len(data):
            raise DnsError("name exceeds packet")
        length = data[pos]
        if (length & 0xC0) == 0xC0:
            if pos + 1 >= len(data):
                raise DnsError("truncated pointer")
            ptr = ((length & 0x3F) << 8) | data[pos + 1]
            if ptr in seen:
                raise DnsError("compression loop")
            seen.add(ptr)
            if not jumped:
                end_pos = pos + 2
            pos, jumped = ptr, True
        elif length == 0:
            if not jumped:
                end_pos = pos + 1
            return ".".join(labels) + ".", end_pos
        elif length & 0xC0:
            raise DnsError("bad label type")
        else:
            pos += 1
            if pos + length > len(data):
                raise DnsError("truncated label")
            raw_label = data[pos:pos + length]
            try:
                labels.append(raw_label.decode("idna"))
            except UnicodeError:
                labels.append(raw_label.decode("ascii", "replace"))
            pos += length
    raise DnsError("too many compression pointers")


def _rdata_text(rr_type: int, pkt: bytes, rdata: bytes, off: int) -> str:
    try:
        if rr_type == TYPE_MAP["A"] and len(rdata) == 4:
            return str(ipaddress.IPv4Address(rdata))
        if rr_type == TYPE_MAP["AAAA"] and len(rdata) == 16:
            return str(ipaddress.IPv6Address(rdata))
        if rr_type in (TYPE_MAP["NS"], TYPE_MAP["CNAME"], TYPE_MAP["PTR"]):
            return _decode_name(pkt, off)[0]
        if rr_type == TYPE_MAP["MX"] and len(rdata) >= 3:
            pref = struct.unpack(">H", rdata[:2])[0]
            return f"{pref} {_decode_name(pkt, off + 2)[0]}"
        if rr_type == TYPE_MAP["SOA"] and len(rdata) >= 3:
            mname, p = _decode_name(pkt, off)
            rname, p = _decode_name(pkt, p)
            return f"{mname} {rname}"
        if rr_type == TYPE_MAP["TXT"]:
            parts, p = [], 0
            while p < len(rdata):
                ln = rdata[p]
                parts.append(rdata[p + 1:p + 1 + ln].decode("utf-8", "replace"))
                p += 1 + ln
            return " ".join(parts)
        if rr_type == TYPE_MAP["CAA"] and len(rdata) >= 2:
            tag_len = rdata[1]
            return f"{rdata[0]} {rdata[2:2 + tag_len].decode()} {rdata[2 + tag_len:].decode('utf-8', 'replace')}"
    except (DnsError, struct.error, IndexError, UnicodeDecodeError):
        return ""
    return ""


def decode_message(data: bytes) -> DnsMessage:
    if len(data) < 12 or len(data) > MAX_DNS_PACKET:
        raise DnsError(f"bad packet size: {len(data)}")
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    pos = 12
    questions: list[tuple[str, int]] = []
    for _ in range(min(qd, 16)):
        qname, pos = _decode_name(data, pos)
        qtype, _qclass = struct.unpack(">HH", data[pos:pos + 4])
        pos += 4
        questions.append((qname, qtype))

    def read_rrs(count: int) -> list[ResourceRecord]:
        nonlocal pos
        out: list[ResourceRecord] = []
        for _ in range(min(count, 512)):
            name, pos = _decode_name(data, pos)
            rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
            pos += 10
            rdata_off = pos
            rdata = data[pos:pos + rdlen]
            if len(rdata) != rdlen:
                raise DnsError("truncated rdata")
            pos += rdlen
            out.append(ResourceRecord(name, rtype, rclass, ttl, rdata,
                                      _rdata_text(rtype, data, rdata, rdata_off)))
        return out

    return DnsMessage(
        qid=qid, flags=flags, rcode=flags & 0x000F,
        questions=questions, answers=read_rrs(an),
        authorities=read_rrs(ns), additionals=read_rrs(ar),
    )
