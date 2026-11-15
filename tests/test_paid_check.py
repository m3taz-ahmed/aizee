"""Tests for the spend ledger (MONEY-01: quote -> approve -> charge -> report)."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.budget import SpendLedger
from runtime.schemas import PolicyDeniedError


def test_quote_registers_estimate(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    q = led.quote("fal", 0.42, key="k1", account="ws-1")
    assert q.key == "k1" and q.estimate == 0.42 and not q.approved


def test_identical_request_dedupes(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    q1 = led.quote("fal", 0.42, key="k1")
    q2 = led.quote("fal", 0.42, key="k1")
    assert q1 is q2 or q1.key == q2.key
    # Only one quote record on disk for the identical request.
    assert sum('"event": "quote"' in line for line in (tmp_path / "spend_ledger.jsonl").read_text().splitlines()) == 1


def test_unapproved_charge_denied(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 1.0, key="k1")
    with pytest.raises(PolicyDeniedError):
        led.charge("k1")


def test_charge_missing_quote_denied(tmp_path: Path) -> None:
    with pytest.raises(PolicyDeniedError):
        SpendLedger(tmp_path).charge("nope")


def test_approve_then_charge_once(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 0.5, key="k1")
    led.approve("k1")
    assert led.charge("k1", actual=0.6) == 0.6
    # Approval is single-use — second charge is denied.
    with pytest.raises(PolicyDeniedError):
        led.charge("k1")


def test_charge_defaults_to_estimate(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("veed", 2.0, key="k9")
    led.approve("k9")
    assert led.charge("k9") == 2.0


def test_report_totals_per_provider(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 1.0, key="a", account="ws-1")
    led.approve("a")
    led.charge("a", actual=1.2)
    led.quote("fal", 2.0, key="b", account="ws-2")
    led.approve("b")
    led.charge("b")
    led.quote("veed", 9.9, key="c")  # never approved/charged — excluded
    report = led.report()
    assert report["total"] == pytest.approx(3.2)
    assert report["providers"]["fal"]["calls"] == 2
    assert set(report["providers"]["fal"]["accounts"]) == {"ws-1", "ws-2"}
    assert "veed" not in report["providers"]


def test_ledger_persists_across_instances(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 0.5, key="k1")
    led.approve("k1")
    # New instance reads the same JSONL store.
    assert SpendLedger(tmp_path).charge("k1") == 0.5


def test_approve_missing_quote_denied(tmp_path: Path) -> None:
    with pytest.raises(PolicyDeniedError):
        SpendLedger(tmp_path).approve("nope")


def test_approve_consumed_quote_denied(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 0.5, key="k1")
    led.approve("k1")
    led.charge("k1")
    with pytest.raises(PolicyDeniedError):
        led.approve("k1")


def test_report_excludes_charges_without_account(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 1.0, key="noacct")  # no account on the charge
    led.approve("noacct")
    led.charge("noacct")
    report = led.report()
    assert report["providers"]["fal"]["calls"] == 1
    assert report["providers"]["fal"]["accounts"] == []


def _append_raw(tmp_path: Path, text: str) -> None:
    with (tmp_path / "spend_ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(text)


def test_torn_tail_line_is_recovered(tmp_path: Path) -> None:
    led = SpendLedger(tmp_path)
    led.quote("fal", 1.0, key="k1")
    _append_raw(tmp_path, '{"event": "quo')  # crash mid-append: no newline
    # Ledger still works — the incomplete write is ignored.
    led.approve("k1")
    assert led.charge("k1") == 1.0
    assert led.report()["corrupt_lines"] == 1


def test_mid_file_corruption_fails_closed(tmp_path: Path) -> None:
    from runtime.schemas import StorageError

    led = SpendLedger(tmp_path)
    led.quote("fal", 1.0, key="k1")
    _append_raw(tmp_path, '{"event": "approve", garbage\n')  # bad line mid-file
    _append_raw(tmp_path, '{"event": "quote", "key": "k2", "provider": "x", "estimate": 1, "approved": false, "consumed": false, "actual": null, "currency": "USD", "account": "", "created_at": "t"}\n')
    with pytest.raises(StorageError):
        led.quote("veed", 2.0, key="k3")
    with pytest.raises(StorageError):
        led.report()


def test_quote_dedupes_by_content_hash(tmp_path) -> None:
    """Same provider+estimate+account re-quoted returns one open quote (S2)."""
    led = SpendLedger(tmp_path / "state")
    a = led.quote("fal", 1.5)
    b = led.quote("fal", 1.5)
    assert a.key == b.key and a.key.startswith("q")
    c = led.quote("fal", 2.5)
    assert c.key != a.key  # different estimate -> different quote
    d = led.quote("fal", 1.5, account="work")
    assert d.key != a.key  # different account -> different quote


def test_explicit_key_still_dedupes(tmp_path) -> None:
    led = SpendLedger(tmp_path / "state")
    a = led.quote("fal", 1.0, key="mine")
    b = led.quote("fal", 9.9, key="mine")
    assert a.key == b.key == "mine" and b.estimate == 1.0


def test_blank_lines_and_newlineless_tail_repaired(tmp_path) -> None:
    """Blank lines are skipped; a tail with no newline at all truncates fully."""
    led = SpendLedger(tmp_path / "state")
    led.quote("fal", 1.0, key="k1")
    path = tmp_path / "state" / "spend_ledger.jsonl"
    path.write_bytes(path.read_bytes() + b"\n\n")  # blank lines tolerated
    assert led.report()["corrupt_lines"] == 0
    path.write_bytes(b'{"event": "quo')             # tail fragment, zero newlines
    led.quote("fal", 2.0, key="k2")                 # append truncates whole tail
    led.approve("k2")
    led.charge("k2", 2.0)
    rep = led.report()
    assert rep["corrupt_lines"] == 1 and rep["providers"]["fal"]["charged"] == 2.0


def test_hash_chain_detects_tampering(tmp_path) -> None:
    """Editing a committed record breaks the HMAC chain -> fail closed."""
    import json as _json

    import pytest

    from runtime.schemas import StorageError

    led = SpendLedger(tmp_path / "state")
    led.quote("fal", 1.0, key="k1")
    led.approve("k1")
    path = tmp_path / "state" / "spend_ledger.jsonl"
    recs = [_json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    assert recs[0]["prev_hash"] == "0" * 64 and recs[0]["hash"]
    assert recs[1]["prev_hash"] == recs[0]["hash"]
    recs[0]["estimate"] = 9999.0  # tamper with a committed record
    path.write_text("\n".join(_json.dumps(r, sort_keys=True) for r in recs) + "\n")
    with pytest.raises(StorageError):
        led.report()


def test_hash_chain_detects_stripped_hash(tmp_path) -> None:
    """A record with its hash stripped reads as chain-broken — fail closed."""
    import json as _json

    import pytest

    from runtime.schemas import StorageError

    led = SpendLedger(tmp_path / "state")
    led.quote("fal", 1.0, key="k1")
    path = tmp_path / "state" / "spend_ledger.jsonl"
    rec = _json.loads(path.read_text().splitlines()[0])
    del rec["hash"], rec["prev_hash"]
    path.write_text(_json.dumps(rec, sort_keys=True) + "\n")
    with pytest.raises(StorageError):
        led.report()
