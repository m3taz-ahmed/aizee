"""AI-Slop Verifier - detects generic, templated "AI slop" in design output.

Deterministic, model-free checking of HTML/CSS against a tiered rule catalog
inspired by pbakaus/impeccable (Apache-2.0), Nutlope/hallmark (MIT),
Leonxlnx/taste-skill (MIT) and nextlevelbuilder/ui-ux-pro-max-skill (MIT).
Original inspiration: claude-design-mode's design-verifier subagent.

Rules are grouped into three tiers:

- ``FLOOR`` - never ship. Accessibility/correctness violations (missing focus
  styles, placeholder copy, layout-property animation, no reduced-motion
  guard, unreadable text). Not waivable.
- ``REFLEX`` - the defaults an unguided model reaches for: gradient washes,
  eyebrow chips, icon tiles, marquees, Inter-family fonts, three-column
  grids. Flagged; waivable on the record via ``<!-- waive:<rule-id> -->``
  or ``data-slop-waive="<id>"`` with an explicit design-world reason.
- ``FINISH`` - craft-level polish advisories (em-dash overuse, meta dots,
  decorative arrows, status dots).

An optional ``judge_fn`` can be injected for visual analysis of screenshots
(vision-model-based) covering what text scanning cannot: spacing rhythm,
rendered contrast, viewport overflow.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from runtime.schemas import AizeeError, ErrorSeverity


class SlopCategory(str, Enum):
    """Categories of AI design slop."""

    GRADIENT_WASH = "gradient_wash"
    GRADIENT_TEXT = "gradient_text"
    AI_PALETTE = "ai_palette"
    ACCENT_BORDER_CARDS = "accent_border_cards"
    SVG_ILLUSTRATIONS = "svg_illustrations"
    OVERUSED_FONTS = "overused_fonts"
    EMOJI_DECORATION = "emoji_decoration"
    THREE_COLUMN_GRID = "three_column_grid"
    AI_HEADLINE_PHRASES = "ai_headline_phrases"
    EYEBROW_CHIP = "eyebrow_chip"
    NESTED_CARDS = "nested_cards"
    MARQUEE = "marquee"
    TYPOGRAPHY_SLOP = "typography_slop"
    SHADOW_SLOP = "shadow_slop"
    MOTION_SLOP = "motion_slop"
    TRUTH_SLOP = "truth_slop"
    META_SLOP = "meta_slop"


class SlopTier(str, Enum):
    """Enforcement tier of a rule (impeccable's floor/reflex/finish split)."""

    FLOOR = "floor"      # never ship; not waivable
    REFLEX = "reflex"    # unguided-model default; waivable on the record
    FINISH = "finish"    # craft advisory


class SlopSeverity(str, Enum):
    """Severity of a slop finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SlopRule:
    """One deterministic detector rule."""

    rule_id: str
    tier: SlopTier
    category: SlopCategory
    severity: SlopSeverity
    pattern: str
    evidence: str
    suggestion: str
    flags: int = re.IGNORECASE


@dataclass
class SlopFinding:
    """A single AI-slop detection finding."""

    category: SlopCategory
    severity: SlopSeverity
    evidence: str
    suggestion: str
    rule_id: str = ""
    tier: SlopTier | None = None


@dataclass
class SlopVerdict:
    """Full verdict from the AI-slop verifier."""

    html: str
    findings: list[SlopFinding] = field(default_factory=list)
    waived: list[SlopFinding] = field(default_factory=list)
    passed: bool = True
    slop_threshold: int = 30

    @property
    def score(self) -> int:
        """0 (clean) to 100 (maximum slop). Weighted by severity."""
        weights = {
            SlopSeverity.CRITICAL: 25,
            SlopSeverity.HIGH: 15,
            SlopSeverity.MEDIUM: 8,
            SlopSeverity.LOW: 3,
        }
        return min(100, sum(weights.get(f.severity, 5) for f in self.findings))

    @property
    def floor_failures(self) -> list[SlopFinding]:
        """Unwaived FLOOR-tier findings - hard blockers."""
        return [f for f in self.findings if f.tier == SlopTier.FLOOR]

    @property
    def is_slop(self) -> bool:
        """True if the output has enough slop to warrant a redesign."""
        return (
            self.score >= self.slop_threshold
            or any(f.severity == SlopSeverity.CRITICAL for f in self.findings)
            or bool(self.floor_failures)
        )

    def summary(self) -> str:
        """Human-readable summary."""
        if self.passed:
            return "✅ Pass - no significant AI slop detected"
        lines = [f"❌ Slop detected (score {self.score}/100):"]
        for f in self.findings:
            tag = f.tier.value if f.tier else f.severity.value
            lines.append(f"  [{tag}/{f.severity.value}] {f.category.value}: {f.evidence}")
        for f in self.waived:
            lines.append(f"  [waived] {f.rule_id or f.category.value}: {f.evidence}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic rule catalog (ported from impeccable/hallmark/taste-skill,
# adapted to regex-on-HTML detection; render-required rules stay judge_fn-side)
# ---------------------------------------------------------------------------

_SLOP_RULES: list[SlopRule] = [
    # --- FLOOR: never ship (a11y / truth / correctness) ---
    SlopRule("lorem-ipsum", SlopTier.FLOOR, SlopCategory.TRUTH_SLOP, SlopSeverity.CRITICAL,
             r"lorem\s+ipsum|lorem\b.{0,20}\bdolor", "placeholder lorem ipsum copy shipped",
             "Write real copy or a truthful description of what goes here."),
    SlopRule("fake-data", SlopTier.FLOOR, SlopCategory.TRUTH_SLOP, SlopSeverity.HIGH,
             r"(?:john|jane)\s+doe|test@test\.|example@example\.|foo@bar", "invented person/email shipped as data",
             "Use real data, an empty state, or clearly-labeled sample content."),
    SlopRule("icon-only-button", SlopTier.FLOOR, SlopCategory.TRUTH_SLOP, SlopSeverity.HIGH,
             r"<button(?![^>]*(?:aria-label|aria-labelledby|title=))[^>]*>\s*<(?:svg|i\b|img)",
             "icon-only button without an accessible name",
             "Add aria-label, visible text, or a title attribute."),
    SlopRule("tiny-text", SlopTier.FLOOR, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"text-\[(?:[6-9]|1[01])px\]|font-size\s*:\s*(?:[6-9]|1[01])px\b",
             "text below 12px is unreadable for many users",
             "Keep body text >= 14px and secondary text >= 12px."),
    SlopRule("skipped-heading", SlopTier.FLOOR, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"</h1>.*?<h[3-6]", "heading level skipped (h1 -> h3+) breaks document outline",
             "Keep heading order sequential: h1 -> h2 -> h3.", re.IGNORECASE | re.DOTALL),
    SlopRule("transition-all", SlopTier.FLOOR, SlopCategory.MOTION_SLOP, SlopSeverity.MEDIUM,
             r"\btransition-all\b|transition\s*:\s*all\b",
             "transition-all pays layout-paint cost on every property change",
             "Transition only the properties that actually animate (transform, opacity)."),
    SlopRule("animate-layout-props", SlopTier.FLOOR, SlopCategory.MOTION_SLOP, SlopSeverity.HIGH,
             r"transition\s*:[^;}]*\b(?:width|height|top|left|right|bottom|margin|padding)\b|"
             r"animate-\[?(?:width|height|top|left)\b|transition-(?:width|height|top|left|all)\b",
             "animating layout properties (width/height/top/left) triggers reflow",
             "Animate transform/opacity instead; use scale or translate."),
    SlopRule("hundred-vw", SlopTier.FLOOR, SlopCategory.MOTION_SLOP, SlopSeverity.MEDIUM,
             r"\b100vw\b", "100vw includes the scrollbar - causes horizontal overflow",
             "Use 100% or w-full; reserve vw for bleed layouts measured with scrollbar-width."),
    SlopRule("hidden-overflow-x", SlopTier.FLOOR, SlopCategory.MOTION_SLOP, SlopSeverity.LOW,
             r"overflow-x\s*:\s*hidden|overflow-x-hidden",
             "overflow-x:hidden clips content; prefer overflow-x:clip which doesn't create a scroll container",
             "Use overflow-x: clip / overflow-x-clip."),
    SlopRule("low-contrast-text", SlopTier.FLOOR, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"text-(?:gray|slate|zinc|neutral)-(300|400)\b",
             "light gray text (300-400) likely fails contrast on light backgrounds",
             "Use 600+ shades for body text on light surfaces; verify WCAG AA."),
    SlopRule("placeholder-as-label", SlopTier.FLOOR, SlopCategory.TRUTH_SLOP, SlopSeverity.HIGH,
             r"<input(?![^>]*(?:aria-label|id=))[^>]*placeholder=",
             "input relies on placeholder as its only label",
             "Add a visible <label> or aria-label; placeholders vanish on input."),

    # --- REFLEX: unguided-model defaults (waivable on the record) ---
    SlopRule("gradient-wash-purple", SlopTier.REFLEX, SlopCategory.GRADIENT_WASH, SlopSeverity.HIGH,
             r"linear-gradient\s*\([^)]*(?:purple|indigo|violet|blue-pink|pink-blue)",
             "purple/blue gradient wash",
             "Use a solid brand color or a restrained duotone instead of a gradient wash."),
    SlopRule("gradient-wash-135", SlopTier.REFLEX, SlopCategory.GRADIENT_WASH, SlopSeverity.HIGH,
             r"background\s*:\s*linear-gradient\s*\([^)]*135deg", "generic 135deg gradient",
             "If a gradient is load-bearing, pick deliberate stops; otherwise flatten it."),
    SlopRule("gradient-wash-tw", SlopTier.REFLEX, SlopCategory.GRADIENT_WASH, SlopSeverity.HIGH,
             r"bg-gradient-to-[brtr]\s+from-(?:purple|indigo|violet)\b", "Tailwind purple gradient",
             "Choose palette stops from the design system, not the Tailwind default ramp."),
    SlopRule("gradient-text", SlopTier.REFLEX, SlopCategory.GRADIENT_TEXT, SlopSeverity.MEDIUM,
             r"bg-clip-text|text-transparent.{0,80}gradient|gradient.{0,80}text-transparent",
             "gradient-filled headline text",
             "Type should carry color from the palette; gradient text is a reflex, not a choice."),
    SlopRule("ai-palette", SlopTier.REFLEX, SlopCategory.AI_PALETTE, SlopSeverity.MEDIUM,
             r"#(?:6366f1|8b5cf6|a855f7|7c3aed|4f46e5)\b|from-purple-\d00.*to-(?:pink|blue|fuchsia)-\d00",
             "default AI palette (indigo/violet Tailwind ramp)",
             "Derive palette from the product's DESIGN.md, not the AI-default violet."),
    SlopRule("accent-border-card", SlopTier.REFLEX, SlopCategory.ACCENT_BORDER_CARDS, SlopSeverity.MEDIUM,
             r"border-(?:l|r|t|b)-[248]\s+border-(?:purple|indigo|blue|violet)|border-l-[248].*?border-[a-z]+-500",
             "accent left-border card stripe",
             "Use elevation, background tint, or a full border instead of a side stripe."),
    SlopRule("svg-illustration-set", SlopTier.REFLEX, SlopCategory.SVG_ILLUSTRATIONS, SlopSeverity.MEDIUM,
             r"<svg[^>]*(?:illustration|undraw|storyset)|data:image/svg.*?(?:undraw|storyset)",
             "generic stock SVG illustration",
             "Use custom photography, product screenshots, or original illustrations."),
    SlopRule("shape-assembled-illustration", SlopTier.REFLEX, SlopCategory.SVG_ILLUSTRATIONS, SlopSeverity.MEDIUM,
             r"<svg[^>]*>[^<]*(?:<circle[^>]*/?>\s*){3,}", "shape-assembled geometric illustration",
             "Abstract geometry pretending to be illustration reads as filler; use real imagery or nothing."),
    SlopRule("eyebrow-chip", SlopTier.REFLEX, SlopCategory.EYEBROW_CHIP, SlopSeverity.MEDIUM,
             r"class=\"[^\"]*(?:rounded-full|rounded-sm)[^\"]*(?:uppercase|tracking-wid)[^\"]*\"",
             "eyebrow/kicker chip above heading",
             "Drop the reflex eyebrow; lead with the heading or a meaningful label."),
    SlopRule("numbered-labels", SlopTier.REFLEX, SlopCategory.EYEBROW_CHIP, SlopSeverity.LOW,
             r">\s*0[1-9]\s*<|>\s*0[1-9]\s*[./]", "numbered section labels (01 / 02 / 03)",
             "Numbered labels on every section are decoration; number only real sequences."),
    SlopRule("icon-tile", SlopTier.REFLEX, SlopCategory.NESTED_CARDS, SlopSeverity.MEDIUM,
             r"class=\"[^\"]*(?:w-1[0-4]|h-1[0-4])[^\"]*rounded[^\"]*\"[^>]*>\s*<svg",
             "icon in colored rounded tile above text",
             "Let the icon sit inline or stand alone; the rounded square tile is a reflex."),
    SlopRule("fake-browser-chrome", SlopTier.REFLEX, SlopCategory.NESTED_CARDS, SlopSeverity.LOW,
             r"(?:w-2\.?5?|h-2\.?5?|w-3|h-3)[^\"]*rounded-full[^\"]*bg-(?:red|yellow|green)-\d00",
             "fake browser-window traffic-light dots",
             "Show the product, not a browser costume."),
    SlopRule("marquee", SlopTier.REFLEX, SlopCategory.MARQUEE, SlopSeverity.MEDIUM,
             r"@keyframes\s+marquee|animate-?marquee|\bmarquee\b[^;]{0,40}(?:infinite|scroll)",
             "infinite logo/content marquee",
             "A static, confident logo row beats an endless scroll; marquees burn attention."),
    SlopRule("three-col-grid", SlopTier.REFLEX, SlopCategory.THREE_COLUMN_GRID, SlopSeverity.HIGH,
             r"grid-cols-3.*?grid-cols-3|grid-template-columns\s*:\s*repeat\(3",
             "repeated equal three-column grid",
             "Use asymmetric layouts, bento, or editorial spacing instead of 3-equal-columns.",
             re.IGNORECASE | re.DOTALL),
    SlopRule("oversized-h1", SlopTier.REFLEX, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"<h1[^>]*class=\"[^\"]*text-(?:[7-9]xl)\b|font-size\s*:\s*(?:[6-9]\d|1\d\d)px",
             "oversized display heading (7xl+)",
             "Scale type to the message; oversized h1 is a reflex when nothing else carries the page."),
    SlopRule("extreme-tracking", SlopTier.REFLEX, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"tracking-tighter\b|letter-spacing\s*:\s*-0?\.0[5-9]em|letter-spacing\s*:\s*-\d",
             "extreme negative letter-spacing",
             "Negative tracking below the font's design intent breaks legibility."),
    SlopRule("wide-tracked-caps", SlopTier.REFLEX, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.MEDIUM,
             r"class=\"[^\"]*uppercase[^\"]*tracking-(?:widest|wider|\[0\.[2-9])[^\"]*text-(?:xs|sm|base)\b",
             "tiny tracked all-caps label",
             "Reserve tracked caps for genuine labels; don't style body text this way."),
    SlopRule("italic-serif-accent", SlopTier.REFLEX, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.LOW,
             r"<(?:em|i)[^>]*class=\"[^\"]*font-(?:serif|display)|font-(?:serif|display)[^\"]*italic",
             "italic serif accent word inside a heading",
             "One italic serif word per heading is a signature; per-heading is a reflex."),
    SlopRule("justified-text", SlopTier.REFLEX, SlopCategory.TYPOGRAPHY_SLOP, SlopSeverity.LOW,
             r"text-justify|text-align\s*:\s*justify", "justified body text creates rivers",
             "Left-align body copy on the web."),
    SlopRule("hard-offset-shadow", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.MEDIUM,
             r"box-shadow\s*:\s*\d+px\s+\d+px\s+0\s|shadow-\[\d+px_\d+px_0",
             "hard offset shadow (no blur)",
             "Hard offset shadows belong to neobrutalism; elsewhere use soft elevation."),
    SlopRule("dark-glow", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.MEDIUM,
             r"shadow-(?:purple|violet|indigo|pink|cyan|fuchsia)-\d00|box-shadow\s*:[^;]*\b(?:purple|violet|cyan)\b",
             "colored glow shadow",
             "Glow shadows read as decoration; elevate with neutral shadows."),
    SlopRule("radial-halo", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.MEDIUM,
             r"rounded-full[^\"]*blur-3xl|blur-3xl[^\"]*rounded-full|radial-gradient\s*\([^)]*(?:purple|violet|indigo|pink)",
             "blurred gradient halo blob",
             "Remove the ambient blob; depth comes from hierarchy, not floating glows."),
    SlopRule("grid-background", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.LOW,
             r"background-image\s*:[^;]*linear-gradient[^;]*linear-gradient|bg-\[linear-gradient",
             "engineered grid/graph-paper background",
             "Grid backgrounds are a known AI tell; prefer texture-free surfaces."),
    SlopRule("repeating-stripes", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.LOW,
             r"repeating-linear-gradient", "repeating gradient stripes decoration",
             "Stripes are decoration masquerading as texture; use them only if the world demands it."),
    SlopRule("bounce-easing", SlopTier.REFLEX, SlopCategory.MOTION_SLOP, SlopSeverity.MEDIUM,
             r"ease-(?:bounce|elastic)|cubic-bezier\(\s*0?\.68\s*,\s*-|back\.out|elastic\.out",
             "bounce/elastic easing on UI",
             "UI motion should settle, not bounce; use expo/power easings."),
    SlopRule("pulsing-dot", SlopTier.REFLEX, SlopCategory.MOTION_SLOP, SlopSeverity.LOW,
             r"animate-ping\b", "pulsing attention dot",
             "Static status beats pulsing; reserve ping for genuinely live signals."),
    SlopRule("blinking-cursor", SlopTier.REFLEX, SlopCategory.MOTION_SLOP, SlopSeverity.LOW,
             r"@keyframes\s+(?:blink|caret)|animate-\[?blink|typewriter", "blinking typewriter cursor",
             "Typewriter cursors are a demo trope; type once, then stop."),
    SlopRule("glassmorphism", SlopTier.REFLEX, SlopCategory.SHADOW_SLOP, SlopSeverity.LOW,
             r"backdrop-blur[^\"]*bg-white/|backdrop-blur[^\"]*bg-black/|backdrop-blur-\w+\b[^\"]*(?:white|black)/(?:5|10|15|20)\b",
             "decorative glassmorphism (blur + translucent white/black)",
             "Glass panels only earn their cost over imagery/maps; on flat surfaces use solid fills."),

    # --- FINISH: craft advisories ---
    SlopRule("em-dash-overuse", SlopTier.FINISH, SlopCategory.META_SLOP, SlopSeverity.LOW,
             r"(?:—|&mdash;).*(?:—|&mdash;).*(?:—|&mdash;).*(?:—|&mdash;)",
             "4+ em dashes in copy - signature AI punctuation",
             "Vary punctuation; em dashes lose meaning when every sentence leans on them.",
             re.IGNORECASE | re.DOTALL),
    SlopRule("meta-dots", SlopTier.FINISH, SlopCategory.META_SLOP, SlopSeverity.LOW,
             r"[^<>\n]{1,40}·[^<>\n]{1,40}·[^<>\n]{1,40}", "middle-dot-joined metadata string",
             "Separate metadata with spacing/structure instead of dot dividers."),
    SlopRule("arrow-in-link", SlopTier.FINISH, SlopCategory.META_SLOP, SlopSeverity.LOW,
             r"<a\b[^>]*>[^<]*[→⟶↗]", "arrow glyph glued inside link text",
             "Use an icon with intent or drop it; trailing arrows are filler."),
    SlopRule("status-dot", SlopTier.FINISH, SlopCategory.META_SLOP, SlopSeverity.LOW,
             r"w-2\s+h-2\s+rounded-full\s+bg-(?:green|emerald|red|amber|yellow)-\d00",
             "decorative colored status dot",
             "Status dots need real state behind them; decorative dots are noise."),
]

# Phrases kept as data (not regex) - matched against stripped text.
_AI_HEADLINE_PHRASES: list[str] = [
    "supercharge your", "supercharge their", "unlock the power",
    "unlock your potential", "seamlessly integrate", "seamless integration",
    "powerful and intuitive", "intuitive and powerful",
    "next-generation platform", "cutting-edge solution", "revolutionary approach",
    "game-changing", "game changer", "one-stop solution", "all-in-one platform",
    "elevate your", "transform your business", "empower your team",
    "harness the power", "leverage ai", "ai-powered platform",
    "built for the future", "future-proof", "scale effortlessly",
    "effortlessly scale", "take your", "to the next level",
    "in today's fast-paced", "look no further", "the ultimate",
    "say goodbye to", "revolutionize your", "discover the power",
    "whether you're a", "designed to help you", "delve into",
    "world-class", "best-in-class", "paradigm shift",
]

_OVERUSED_FONTS: set[str] = {
    "inter", "poppins", "montserrat", "roboto", "open sans", "lato",
    "raleway", "arial", "helvetica neue", "nunito sans",
}

_EMOJI_RE = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF\U00002700-\U000027BF]"
)
_WAIVER_RE = re.compile(
    r"<!--\s*waive:([\w-]+)\s*-->|data-slop-waive=[\"']([\w-]+)[\"']",
    re.IGNORECASE,
)


class DesignSlopVerifier:
    """Verify design output against a tiered AI-slop rule catalog.

    Deterministic regex checks run always; an optional ``judge_fn`` handles
    visual/screenshot analysis (spacing rhythm, rendered contrast, overflow).
    """

    def __init__(
        self,
        *,
        slop_threshold: int = 30,
        judge_fn: Callable[[str, str], list[SlopFinding]] | None = None,
    ) -> None:
        """Initialize the verifier.

        Args:
            slop_threshold: Score threshold above which output is flagged as slop.
            judge_fn: Optional injectable vision-model judge. Receives
                (html, screenshot_path) and returns additional findings.
        """
        if slop_threshold < 0:
            raise DesignSlopError(
                f"slop_threshold must be >= 0, got {slop_threshold}",
                context={"slop_threshold": slop_threshold},
            )
        self._threshold = slop_threshold
        self._judge_fn = judge_fn

    def rule_ids(self) -> list[str]:
        """Return the ids of every deterministic rule in the catalog."""
        return [r.rule_id for r in _SLOP_RULES]

    def verify(self, html: str, *, screenshot_path: str | None = None) -> SlopVerdict:
        """Verify HTML output for AI slop.

        Args:
            html: The HTML/CSS text to check.
            screenshot_path: Optional path to a screenshot for visual analysis.

        Returns:
            A SlopVerdict with all findings, waivers, and a pass/fail call.
        """
        waivers = {m for m in _WAIVER_RE.findall(html) for m in m if m}
        findings: list[SlopFinding] = []
        waived: list[SlopFinding] = []

        for rule in _SLOP_RULES:
            if not re.search(rule.pattern, html, rule.flags):
                continue
            finding = SlopFinding(
                category=rule.category,
                severity=rule.severity,
                evidence=rule.evidence,
                suggestion=rule.suggestion,
                rule_id=rule.rule_id,
                tier=rule.tier,
            )
            # FLOOR rules are never waivable; REFLEX/FINISH waive on the record.
            if rule.rule_id in waivers and rule.tier != SlopTier.FLOOR:
                waived.append(finding)
            else:
                findings.append(finding)

        findings.extend(self._check_overused_fonts(html))
        findings.extend(self._check_emoji_decoration(html))
        findings.extend(self._check_ai_headlines(html))
        findings.extend(self._check_reduced_motion(html))
        findings.extend(self._check_missing_focus(html))

        if self._judge_fn and screenshot_path:
            try:
                findings.extend(self._judge_fn(html, screenshot_path))
            except Exception as exc:
                findings.append(SlopFinding(
                    category=SlopCategory.TRUTH_SLOP,
                    severity=SlopSeverity.LOW,
                    evidence=f"vision judge unavailable ({type(exc).__name__}); visual review uncertain",
                    suggestion="Retry visual review manually or re-run with a working judge_fn.",
                    rule_id="judge-unavailable",
                    tier=SlopTier.FINISH,
                ))

        verdict = SlopVerdict(
            html=html, findings=findings, waived=waived,
            passed=True, slop_threshold=self._threshold,
        )
        verdict.passed = not verdict.is_slop
        return verdict

    def verify_batch(
        self,
        items: list[tuple[str, str | None]],
    ) -> list[SlopVerdict]:
        """Verify multiple HTML files. Each item is (html, screenshot_path)."""
        return [self.verify(html, screenshot_path=ss) for html, ss in items]

    # -- Checks that need counting or tag-stripping, not a single regex --------

    def _check_overused_fonts(self, html: str) -> list[SlopFinding]:
        font_matches = re.findall(r"font-family\s*:\s*['\"]?([^;'\"{]+)", html, re.IGNORECASE)
        tailwind_fonts = re.findall(
            r"""class\s*=\s*["'][^"']*\bfont-(sans|mono)\b[^"']*["']""", html, re.IGNORECASE)
        font_matches.extend(tailwind_fonts)
        for font in font_matches:
            font_clean = font.strip().lower()
            if font_clean in _OVERUSED_FONTS or font_clean in ("sans", "mono"):
                label = f"'{font_clean}' is an overused AI-default font" if font_clean in _OVERUSED_FONTS else (
                    f"'font-{font_clean}' Tailwind default stack (often Inter/ui-monospace)"
                )
                return [SlopFinding(
                    category=SlopCategory.OVERUSED_FONTS,
                    severity=SlopSeverity.MEDIUM,
                    evidence=label,
                    suggestion="Pair a distinctive display font with a clean body font; consult design-db typography.",
                    rule_id="overused-font",
                    tier=SlopTier.REFLEX,
                )]
        return []

    def _check_emoji_decoration(self, html: str) -> list[SlopFinding]:
        emoji_count = len(_EMOJI_RE.findall(html))
        if emoji_count >= 3:
            return [SlopFinding(
                category=SlopCategory.EMOJI_DECORATION,
                severity=SlopSeverity.LOW,
                evidence=f"{emoji_count} emoji found in HTML (decorative overuse / emoji-as-icon)",
                suggestion="Replace emoji with a real icon system (Phosphor, Iconsax, Lucide).",
                rule_id="emoji-decoration",
                tier=SlopTier.REFLEX,
            )]
        return []

    def _check_ai_headlines(self, html: str) -> list[SlopFinding]:
        text = re.sub(r"<[^>]+>", " ", html).lower()
        for phrase in _AI_HEADLINE_PHRASES:
            if phrase in text:
                return [SlopFinding(
                    category=SlopCategory.AI_HEADLINE_PHRASES,
                    severity=SlopSeverity.CRITICAL,
                    evidence=f"'{phrase}' is a cliché AI headline phrase",
                    suggestion="Write specific, concrete copy describing what the product actually does.",
                    rule_id="ai-headline",
                    tier=SlopTier.REFLEX,
                )]
        return []

    def _check_reduced_motion(self, html: str) -> list[SlopFinding]:
        has_animation = re.search(
            r"@keyframes|animate-|animation\s*:|transition", html, re.IGNORECASE)
        has_guard = re.search(
            r"prefers-reduced-motion|motion-safe|motion-reduce|gsap\.matchMedia",
            html, re.IGNORECASE)
        if has_animation and not has_guard:
            return [SlopFinding(
                category=SlopCategory.MOTION_SLOP,
                severity=SlopSeverity.MEDIUM,
                evidence="animations present with no prefers-reduced-motion guard",
                suggestion="Wrap motion in @media (prefers-reduced-motion: no-preference) or motion-safe: variants.",
                rule_id="reduced-motion-missing",
                tier=SlopTier.FLOOR,
            )]
        return []

    def _check_missing_focus(self, html: str) -> list[SlopFinding]:
        interactive = re.search(r"<a\b|<button\b|cursor-pointer", html, re.IGNORECASE)
        focus_style = re.search(
            r"focus-visible|focus:|focus\s*\{|outline", html, re.IGNORECASE)
        if interactive and not focus_style:
            return [SlopFinding(
                category=SlopCategory.TRUTH_SLOP,
                severity=SlopSeverity.MEDIUM,
                evidence="interactive elements present but no visible focus styling",
                suggestion="Add focus-visible: styles (ring/outline) for keyboard users.",
                rule_id="missing-focus-visible",
                tier=SlopTier.FLOOR,
            )]
        return []


# -- Exception -----------------------------------------------------------------


class DesignSlopError(AizeeError):
    """Raised when the slop verifier encounters an error."""

    def __init__(self, message: str, context: dict[str, object] | None = None) -> None:
        super().__init__("SLOP_ERROR", message, ErrorSeverity.MEDIUM, context)
