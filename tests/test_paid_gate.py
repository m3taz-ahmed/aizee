"""Kernel paid gate — MONEY-01 enforcement at the policy boundary.

The gate authorizes only when the caller cites an approved, unconsumed
spend quote. It never charges — ``aizee check`` can validate a paid call
without consuming its single-use approval; ``budget charge`` records the
actual spend at execution time.
"""

from __future__ import annotations

from pathlib import Path

from runtime.budget import SpendLedger
from runtime.kernel import Kernel


def _ledger(root: Path) -> SpendLedger:
    return SpendLedger(root / "state")


class TestPaidGate:
    def test_paid_call_needs_approval(self, tmp_path: Path) -> None:
        k = Kernel(tmp_path)
        result = k.act("paid_call")
        assert result["ok"] is False  # policy "ask" without approval

    def test_missing_quote_key_denied(self, tmp_path: Path) -> None:
        k = Kernel(tmp_path)
        result = k.act("paid_call", approved=True)
        assert result["ok"] is False
        assert "quote" in result["error"]

    def test_unknown_quote_key_denied(self, tmp_path: Path) -> None:
        k = Kernel(tmp_path)
        result = k.act("paid_call", approved=True, quote_key="ghost")
        assert result["ok"] is False

    def test_unapproved_quote_denied(self, tmp_path: Path) -> None:
        _ledger(tmp_path).quote("fal", 0.5, key="k1")
        k = Kernel(tmp_path)
        result = k.act("paid_call", approved=True, quote_key="k1")
        assert result["ok"] is False
        assert "not approved" in result["error"]

    def test_approved_quote_authorized_without_consuming(self, tmp_path: Path) -> None:
        led = _ledger(tmp_path)
        led.quote("fal", 0.5, key="k1")
        led.approve("k1")
        k = Kernel(tmp_path)
        result = k.act("paid_call", approved=True, quote_key="k1")
        assert result["ok"] is True
        # Gate authorizes but does not spend — a second check still passes.
        assert k.act("paid_call", approved=True, quote_key="k1")["ok"] is True
        assert led.get("k1").consumed is False

    def test_consumed_quote_denied(self, tmp_path: Path) -> None:
        led = _ledger(tmp_path)
        led.quote("fal", 0.5, key="k1")
        led.approve("k1")
        led.charge("k1")
        k = Kernel(tmp_path)
        result = k.act("paid_call", approved=True, quote_key="k1")
        assert result["ok"] is False
        assert "single-use" in result["error"]

    def test_non_paid_actions_unaffected(self, tmp_path: Path) -> None:
        k = Kernel(tmp_path)
        assert k.act("read")["ok"] is True

    def test_gate_emits_audit_events(self, tmp_path: Path) -> None:
        led = _ledger(tmp_path)
        led.quote("fal", 0.5, key="k1")
        led.approve("k1")
        k = Kernel(tmp_path)
        k.act("paid_call", approved=True, quote_key="k1")
        k.act("paid_call", approved=True, quote_key="missing")
        log = (tmp_path / "state" / "audit.log").read_text(encoding="utf-8")
        assert "paid.authorized" in log
        assert "paid.denied" in log
