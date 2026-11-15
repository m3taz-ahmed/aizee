"""Paid action types never inherit a permissive default (MONEY-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.policy import PolicyEngine, _is_paid_action


def _engine(tmp_path: Path, default: str) -> PolicyEngine:
    e = PolicyEngine(tmp_path)  # no policies dir — fallback path
    e.default_action = default  # configured default (settings.json / default.yaml)
    return e


class TestPaidTokens:
    @pytest.mark.parametrize(
        "at",
        ["paid_call", "generate_paid_call", "paid", "pay", "payment",
         "purchase", "spend", "bill", "billing", "charge", "checkout", "invoice"],
    )
    def test_paid_recognized(self, at: str) -> None:
        assert _is_paid_action(at)

    @pytest.mark.parametrize(
        "at",
        ["read", "edit", "deploy", "raindrop", "unpaid_invoice_view", "billable_view"],
    )
    def test_non_paid_not_matched(self, at: str) -> None:
        assert not _is_paid_action(at)


class TestPaidDecisions:
    def test_paid_never_inherits_allow_default(self, tmp_path: Path) -> None:
        e = _engine(tmp_path, "allow")
        result = e.can("paid_call")
        assert result["decision"] == "ask"
        assert result["requires_approval"] is True

    def test_all_paid_tokens_ask_under_allow(self, tmp_path: Path) -> None:
        e = _engine(tmp_path, "allow")
        for at in ("purchase", "spend", "charge", "invoice"):
            assert e.can(at)["decision"] == "ask", at

    def test_strict_deny_still_wins(self, tmp_path: Path) -> None:
        e = _engine(tmp_path, "deny")
        assert e.can("paid_call")["decision"] == "deny"

    def test_benign_unknown_still_follows_default(self, tmp_path: Path) -> None:
        e = _engine(tmp_path, "allow")
        assert e.can("frobnicate")["decision"] == "allow"

    def test_default_ask_unchanged(self, tmp_path: Path) -> None:
        e = _engine(tmp_path, "ask")
        assert e.can("paid_call")["decision"] == "ask"
        assert e.can("frobnicate")["decision"] == "ask"
