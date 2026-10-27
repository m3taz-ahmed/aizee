"""Tests for runtime.design_slop_verifier - AI-slop design verifier."""

from __future__ import annotations

import pytest

from runtime.design_slop_verifier import (
    DesignSlopVerifier,
    SlopCategory,
    SlopFinding,
    SlopSeverity,
    SlopTier,
    SlopVerdict,
)


@pytest.fixture
def verifier() -> DesignSlopVerifier:
    return DesignSlopVerifier()


# --- Clean input ---

def test_clean_html_passes(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify("<div><h1>Hello World</h1><p>Just a plain page.</p></div>")
    assert v.passed
    assert v.score == 0


# --- Per-category detection ---

def test_gradient_wash_detected(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify('<div style="background: linear-gradient(135deg, purple, pink)">x</div>')
    cats = {f.category for f in v.findings}
    assert SlopCategory.GRADIENT_WASH in cats
    grad = next(f for f in v.findings if f.category == SlopCategory.GRADIENT_WASH)
    assert grad.severity == SlopSeverity.HIGH


def test_accent_border_detected(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify('<div class="border-l-4 border-purple-500">card</div>')
    cats = {f.category for f in v.findings}
    assert SlopCategory.ACCENT_BORDER_CARDS in cats


def test_overused_font_detected(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify('<div style="font-family: Inter; color: red;">text</div>')
    cats = {f.category for f in v.findings}
    assert SlopCategory.OVERUSED_FONTS in cats


def test_emoji_decoration_detected(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify("<div>🚀 🎉 ✨ features</div>")
    cats = {f.category for f in v.findings}
    assert SlopCategory.EMOJI_DECORATION in cats


def test_three_column_grid_detected(verifier: DesignSlopVerifier) -> None:
    html = '<div class="grid grid-cols-3">a</div><div class="grid grid-cols-3">b</div>'
    v = verifier.verify(html)
    cats = {f.category for f in v.findings}
    assert SlopCategory.THREE_COLUMN_GRID in cats


def test_ai_headline_detected(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify("<h1>Supercharge your workflow today</h1>")
    cats = {f.category for f in v.findings}
    assert SlopCategory.AI_HEADLINE_PHRASES in cats
    headline = next(f for f in v.findings if f.category == SlopCategory.AI_HEADLINE_PHRASES)
    assert headline.severity == SlopSeverity.CRITICAL


# --- Verdict properties ---

def test_is_slop_threshold(verifier: DesignSlopVerifier) -> None:
    # gradient (HIGH=15) + accent border (MEDIUM=8) + overused font (MEDIUM=8) = 31 >= 30
    html = (
        '<div style="background: linear-gradient(135deg, purple, pink)">'
        '<div class="border-l-4 border-purple-500">card</div>'
        '<span style="font-family: Inter">x</span></div>'
    )
    v = verifier.verify(html)
    assert len(v.findings) >= 2
    assert v.is_slop


def test_verdict_summary_passed(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify("<p>clean</p>")
    assert v.passed
    assert "✅" in v.summary()


def test_verdict_summary_failed(verifier: DesignSlopVerifier) -> None:
    v = verifier.verify("<h1>Supercharge your workflow</h1>")
    assert not v.passed
    assert "❌" in v.summary()


# --- Batch ---

def test_verify_batch(verifier: DesignSlopVerifier) -> None:
    items: list[tuple[str, str | None]] = [
        ("<p>clean</p>", None),
        ('<div style="background: linear-gradient(135deg, purple, pink)">x</div>', None),
        ("<h1>Supercharge your day</h1>", None),
    ]
    results = verifier.verify_batch(items)
    assert len(results) == 3
    assert all(isinstance(r, SlopVerdict) for r in results)


# --- Injectable judge_fn ---

def test_judge_fn_injected() -> None:
    extra = SlopFinding(
        category=SlopCategory.SVG_ILLUSTRATIONS,
        severity=SlopSeverity.MEDIUM,
        evidence="judge-detected illustration",
        suggestion="replace it",
    )

    def judge(html: str, screenshot: str) -> list[SlopFinding]:
        return [extra]

    v = DesignSlopVerifier(judge_fn=judge)
    verdict = v.verify("<p>clean</p>", screenshot_path="shot.png")
    assert extra in verdict.findings


def test_judge_fn_error_fails_open() -> None:
    def judge(html: str, screenshot: str) -> list[SlopFinding]:
        raise RuntimeError("judge crashed")

    v = DesignSlopVerifier(judge_fn=judge)
    verdict = v.verify("<p>clean</p>", screenshot_path="shot.png")
    # Verification still completes despite judge error
    assert isinstance(verdict, SlopVerdict)
    assert verdict.passed


# --- Tiered rules (impeccable/hallmark port) ---

def test_floor_rules_not_waivable() -> None:
    html = '<p>lorem ipsum</p><!-- waive:lorem-ipsum -->'
    v = DesignSlopVerifier().verify(html)
    assert any(f.rule_id == "lorem-ipsum" for f in v.findings)
    assert not v.passed


def test_reflex_rule_waivable() -> None:
    html = '<div style="background: linear-gradient(135deg, purple, pink)"><!-- waive:gradient-wash-135 -->x</div>'
    v = DesignSlopVerifier().verify(html)
    assert any(f.rule_id == "gradient-wash-135" for f in v.waived)


def test_gradient_text_detected() -> None:
    v = DesignSlopVerifier().verify('<h1 class="bg-clip-text text-transparent bg-gradient-to-r">Hi</h1>')
    assert any(f.category == SlopCategory.GRADIENT_TEXT for f in v.findings)


def test_marquee_detected() -> None:
    v = DesignSlopVerifier().verify('<div class="animate-marquee">logos</div>')
    assert any(f.category == SlopCategory.MARQUEE for f in v.findings)


def test_transition_all_floor() -> None:
    v = DesignSlopVerifier().verify('<div style="transition: all 300ms">x</div>')
    assert any(f.rule_id == "transition-all" and f.tier == SlopTier.FLOOR for f in v.findings)


def test_animate_layout_props_floor() -> None:
    v = DesignSlopVerifier().verify('<div style="transition: width 200ms">x</div>')
    assert any(f.rule_id == "animate-layout-props" for f in v.findings)


def test_hundred_vw_floor() -> None:
    v = DesignSlopVerifier().verify('<div style="width: 100vw">x</div>')
    assert any(f.rule_id == "hundred-vw" for f in v.findings)


def test_icon_only_button_floor() -> None:
    v = DesignSlopVerifier().verify("<button><svg><path/></svg></button>")
    assert any(f.rule_id == "icon-only-button" for f in v.findings)


def test_icon_only_button_with_label_ok() -> None:
    v = DesignSlopVerifier().verify('<button aria-label="Close"><svg><path/></svg></button>')
    assert not any(f.rule_id == "icon-only-button" for f in v.findings)


def test_reduced_motion_missing_floor() -> None:
    v = DesignSlopVerifier().verify('<style>@keyframes spin { to { transform: rotate(1turn) } }</style>')
    assert any(f.rule_id == "reduced-motion-missing" for f in v.findings)


def test_reduced_motion_guarded_ok() -> None:
    html = '<style>@media (prefers-reduced-motion: no-preference) { @keyframes spin {} }</style>'
    v = DesignSlopVerifier().verify(html)
    assert not any(f.rule_id == "reduced-motion-missing" for f in v.findings)


def test_missing_focus_floor() -> None:
    v = DesignSlopVerifier().verify('<a href="/x">go</a><button>hi</button>')
    assert any(f.rule_id == "missing-focus-visible" for f in v.findings)


def test_oversized_h1_detected() -> None:
    v = DesignSlopVerifier().verify('<h1 class="text-9xl">Big</h1>')
    assert any(f.rule_id == "oversized-h1" for f in v.findings)


def test_hard_offset_shadow_detected() -> None:
    v = DesignSlopVerifier().verify('<div style="box-shadow: 8px 8px 0 #000">x</div>')
    assert any(f.rule_id == "hard-offset-shadow" for f in v.findings)


def test_radial_halo_detected() -> None:
    v = DesignSlopVerifier().verify('<div class="absolute rounded-full blur-3xl bg-purple-500/30"></div>')
    assert any(f.rule_id == "radial-halo" for f in v.findings)


def test_skipped_heading_floor() -> None:
    v = DesignSlopVerifier().verify("<h1>Title</h1><h3>Skipped</h3>")
    assert any(f.rule_id == "skipped-heading" for f in v.findings)


def test_floor_failures_property() -> None:
    v = DesignSlopVerifier().verify('<p>lorem ipsum</p>')
    assert v.floor_failures
    assert v.is_slop


def test_rules_have_unique_ids() -> None:
    v = DesignSlopVerifier()
    ids = v.rule_ids()
    assert len(ids) == len(set(ids))
    assert len(ids) >= 40


def test_summary_lists_waived() -> None:
    html = '<p>lorem ipsum</p><div style="background: linear-gradient(135deg, purple, pink)"><!-- waive:gradient-wash-135 -->x</div>'
    v = DesignSlopVerifier().verify(html)
    text = v.summary()
    assert "[waived]" in text
    assert "gradient-wash-135" in text
