"""Design DB - searchable design intelligence over vendored curated corpora.

Adopted from nextlevelbuilder/ui-ux-pro-max-skill (MIT, see ``design-db/ATTRIBUTION.md``).
The CSV datasets under ``<root>/design-db/`` hold curated UI styles, product
palettes + reasoning profiles, font pairings, UX guidelines, chart types,
landing-page patterns, GSAP motion presets, Google Fonts, and per-stack
implementation guidelines.

``DesignDB`` exposes:

- :meth:`search` - domain-scoped ranked search with BM25-style scoring,
  normalization synonyms, and honest empty results (no fabricated output).
- :meth:`design_system` - aggregate a coherent product-wide visual direction
  (style + palette + typography + layout pattern + motion + anti-patterns)
  with optional ``variance``/``motion``/``density`` dials (1-10).
- :meth:`stacks` / :meth:`domains` - capability introspection.

All searches run locally; nothing leaves the machine.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

from runtime.schemas import AizeeError, ErrorSeverity


class DesignDomain(str, Enum):
    """Searchable design domains (one CSV corpus each)."""

    STYLE = "style"
    PRODUCT = "product"
    COLOR = "color"
    TYPOGRAPHY = "typography"
    GOOGLE_FONTS = "google-fonts"
    ICONS = "icons"
    UX = "ux"
    LANDING = "landing"
    CHART = "chart"
    MOTION = "gsap"
    REACT = "react"
    APP = "app"
    REASONING = "reasoning"


@dataclass(frozen=True)
class DomainConfig:
    """CSV file + weighted search columns for a domain."""

    filename: str
    identity_cols: tuple[str, ...]  # name/title fields - highest weight
    keyword_cols: tuple[str, ...]  # keyword/tag fields - medium weight
    body_cols: tuple[str, ...] = ()  # prose fields - lowest weight


@dataclass
class DesignHit:
    """One ranked search result."""

    domain: str
    score: float
    row: dict[str, str]

    @property
    def title(self) -> str:
        for key in ("Style Category", "Product Type", "Font Pairing Name", "Pattern Name",
                    "Family", "Icon Name", "Issue", "Guideline", "Best Chart Type",
                    "Data Type", "Category", "UI_Category"):
            if self.row.get(key):
                return self.row[key]
        return next(iter(self.row.values()), "")


@dataclass
class DesignSearchResult:
    """Search response: hits plus honesty metadata."""

    query: str
    domain: str
    hits: list[DesignHit] = field(default_factory=list)
    fallback: bool = False  # True => no verified match; caller must say so


@dataclass
class DesignSystemResult:
    """Aggregated product-wide visual direction."""

    query: str
    project: str
    dials: dict[str, int]
    sections: dict[str, dict[str, str] | None]
    markdown: str


# Normalization: longest-first synonym substitution at token boundaries.
_SYNONYMS = {
    "q&a": "question answer",
    "e-commerce": "ecommerce",
    "dark-mode": "dark",
    "darkmode": "dark",
    "light-mode": "light",
    "lightmode": "light",
    "a11y": "accessibility",
    "nav": "navigation",
    "sign-up": "signup",
    "log-in": "login",
    "colour": "color",
    "colours": "colors",
    "customisation": "customization",
    "organisation": "organization",
    "behaviour": "behavior",
    "ux/ui": "ux ui",
}
_SYNONYM_PATTERNS = [
    (re.compile(r"(?<!\w)" + re.escape(v) + r"(?!\w)", re.IGNORECASE), c)
    for v, c in sorted(_SYNONYMS.items(), key=lambda i: len(i[0]), reverse=True)
]
_STOPWORDS = {
    "to", "in", "on", "at", "is", "of", "by", "or", "an", "if", "no", "so",
    "do", "be", "we", "it", "as", "the", "and", "for", "are", "was", "a",
}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9&.+#-]*")

# Domain auto-detection cues (first match wins).
_DOMAIN_CUES: list[tuple[DesignDomain, tuple[str, ...]]] = [
    (DesignDomain.CHART, ("chart", "graph", "plot", "visualization", "visualisation", "dashboard data")),
    (DesignDomain.GOOGLE_FONTS, ("google font", "font family", "typeface")),
    (DesignDomain.TYPOGRAPHY, ("pairing", "typography", "font")),
    (DesignDomain.ICONS, ("icon", "glyph", "pictogram")),
    (DesignDomain.MOTION, ("gsap", "animation", "motion", "scroll reveal", "transition", "ease")),
    (DesignDomain.LANDING, ("landing", "hero", "cta", "conversion", "section order")),
    (DesignDomain.REACT, ("react", "rerender", "memo", "hook")),
    (DesignDomain.COLOR, ("palette", "color", "hex", "swatch")),
    (DesignDomain.STYLE, ("style", "glassmorphism", "neumorphism", "brutalism", "minimalism", "bento")),
    (DesignDomain.APP, ("mobile", "ios", "android", "native", "touch", "safe area")),
    (DesignDomain.UX, ("ux", "accessibility", "usability", "wcag", "focus", "error", "form", "a11y")),
]

_DENSITY_SPACING = {
    "low": ("24px", "32px", "48px", "64px", "96px"),
    "standard": ("16px", "24px", "32px", "48px", "64px"),
    "high": ("8px", "12px", "16px", "24px", "32px"),
}
_MOTION_TIERS = {  # dial 1-10 -> intensity tier
    "subtle": range(1, 4),
    "standard": range(4, 8),
    "complex": range(8, 11),
}


def _normalize(text: str) -> str:
    out = str(text)
    for pattern, canonical in _SYNONYM_PATTERNS:
        out = pattern.sub(canonical, out)
    return out


def _stem(tok: str) -> str:
    """Naive suffix stemmer so 'dashboard' matches 'dashboards' etc."""
    for suffix, repl, min_len in (
        ("ies", "y", 4), ("ing", "", 5), ("ed", "", 4), ("es", "", 4), ("s", "", 4),
    ):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= min_len - len(suffix):
            if suffix == "s" and tok.endswith(("ss", "us", "is")):
                break
            stemmed = tok[: -len(suffix)] + repl
            return stemmed
    return tok


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(_normalize(text).lower()) if t not in _STOPWORDS]


class DesignDB:
    """Query engine over the vendored design corpora in ``design-db/``."""

    MAX_RESULTS: ClassVar[int] = 10
    MIN_SCORE: ClassVar[float] = 0.25  # below -> honest empty result

    _CONFIG: ClassVar[dict[DesignDomain, DomainConfig]] = {
        DesignDomain.STYLE: DomainConfig(
            "styles.csv",
            ("Style Category", "Style ID", "Aliases", "AI Prompt Keywords"),
            ("Keywords", "CSS/Technical Keywords", "Type"),
            ("Best For", "Effects & Animation", "Primary Colors"),
        ),
        DesignDomain.PRODUCT: DomainConfig(
            "products.csv",
            ("Product Type",),
            ("Keywords", "Primary Style Recommendation"),
            ("Key Considerations", "Landing Page Pattern"),
        ),
        DesignDomain.COLOR: DomainConfig(
            "colors.csv",
            ("Product Type",),
            ("Notes",),
        ),
        DesignDomain.TYPOGRAPHY: DomainConfig(
            "typography.csv",
            ("Font Pairing Name", "Heading Font", "Body Font"),
            ("Mood/Style Keywords", "Category"),
            ("Best For", "Notes"),
        ),
        DesignDomain.GOOGLE_FONTS: DomainConfig(
            "google-fonts.csv",
            ("Family",),
            ("Keywords", "Category", "Classifications"),
        ),
        DesignDomain.ICONS: DomainConfig(
            "icons.csv",
            ("Icon Name", "Semantic Role"),
            ("Keywords", "Category", "Library"),
            ("Usage", "Best For"),
        ),
        DesignDomain.UX: DomainConfig(
            "ux-guidelines.csv",
            ("Issue", "Category"),
            ("Description", "Do", "Don't"),
        ),
        DesignDomain.LANDING: DomainConfig(
            "landing.csv",
            ("Pattern Name", "Pattern ID", "Aliases"),
            ("Keywords",),
            ("Section Order", "Color Strategy", "Recommended Effects"),
        ),
        DesignDomain.CHART: DomainConfig(
            "charts.csv",
            ("Best Chart Type", "Data Type"),
            ("Keywords", "Secondary Options"),
            ("When to Use", "When NOT to Use", "Accessibility Notes"),
        ),
        DesignDomain.MOTION: DomainConfig(
            "motion.csv",
            ("Category", "Intensity Tier"),
            ("Keywords", "Trigger", "Easing"),
            ("Do", "Don't", "Framework Notes", "GSAP Snippet"),
        ),
        DesignDomain.REACT: DomainConfig(
            "react-performance.csv",
            ("Issue", "Category"),
            ("Keywords", "Description", "Do", "Don't"),
        ),
        DesignDomain.APP: DomainConfig(
            "app-interface.csv",
            ("Issue", "Category"),
            ("Keywords", "Platform", "Description", "Do", "Don't"),
        ),
        DesignDomain.REASONING: DomainConfig(
            "ui-reasoning.csv",
            ("UI_Category", "Recommended_Pattern"),
            ("Style_Priority", "Color_Mood", "Typography_Mood", "Key_Effects"),
            ("Anti_Patterns", "Decision_Rules", "Reasoning"),
        ),
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize with the directory holding the vendored CSVs."""
        self._dir = data_dir
        self._rows: dict[str, list[dict[str, str]]] = {}
        self._idf: dict[str, dict[str, float]] = {}
        self._doc_tokens: dict[str, list[list[tuple[str, float]]]] = {}

    # -- public API ----------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._dir is not None and self._dir.exists()

    def domains(self) -> list[str]:
        return sorted(d.value for d in self._CONFIG)

    def stacks(self) -> list[str]:
        if self._dir is None or not self._dir.exists():
            return []
        stacks_dir = self._dir / "stacks"
        if not stacks_dir.is_dir():
            return []
        return sorted(p.stem for p in stacks_dir.glob("*.csv"))

    def detect_domain(self, query: str) -> DesignDomain:
        """Pick the most likely domain from query cues; default UX."""
        q = _normalize(query).lower()
        for domain, cues in _DOMAIN_CUES:
            if any(cue in q for cue in cues):
                return domain
        return DesignDomain.UX

    def search(
        self,
        query: str,
        *,
        domain: DesignDomain | str | None = None,
        stack: str | None = None,
        max_results: int = 3,
    ) -> DesignSearchResult:
        """Ranked search over one domain corpus (or a stack guideline file).

        Returns an honest empty result (``fallback=True``) when nothing clears
        the score floor - never fabricates guidance.
        """
        query_tokens = _tokens(query)
        if not query_tokens:
            raise DesignDBError("empty query", {"query": query})
        max_results = max(1, min(max_results, self.MAX_RESULTS))

        if stack:
            name = Path(str(stack).strip().lower()).stem
            rows = self._load_stack(name)
            dom = f"stack:{name}"
            display = dom
        else:
            dom_enum = self._resolve_domain(domain) if domain else self.detect_domain(query)
            rows = self._load_domain(dom_enum)
            dom = f"domain:{dom_enum.value}"
            display = dom_enum.value

        hits = self._rank(query_tokens, rows, dom)
        hits = hits[:max_results]
        return DesignSearchResult(query=query, domain=display, hits=hits, fallback=not hits)

    def design_system(
        self,
        query: str,
        *,
        project: str = "",
        variance: int = 5,
        motion: int = 5,
        density: int = 5,
    ) -> DesignSystemResult:
        """Aggregate a coherent visual direction across domains."""
        for name, value in (("variance", variance), ("motion", motion), ("density", density)):
            if not 1 <= value <= 10:
                raise DesignDBError(f"{name} dial must be 1-10, got {value}")

        sections: dict[str, dict[str, str] | None] = {
            "product": self._top(query, DesignDomain.PRODUCT),
            "reasoning": self._top(query, DesignDomain.REASONING),
            "style": self._top(query, DesignDomain.STYLE),
            "palette": self._top(query, DesignDomain.COLOR),
            "typography": self._top(query, DesignDomain.TYPOGRAPHY),
            "landing": self._top(query, DesignDomain.LANDING),
            "motion": self._motion_pick(motion),
        }
        spacing = _DENSITY_SPACING["low" if density <= 3 else "high" if density >= 8 else "standard"]
        dials = {"variance": variance, "motion": motion, "density": density}
        return DesignSystemResult(
            query=query,
            project=project,
            dials=dials,
            sections={**sections, "spacing_scale": {
                "scale": " | ".join(spacing), "density": f"{density}/10"}},
            markdown=self._render_markdown(project or query, sections, spacing, dials),
        )

    # -- internals -----------------------------------------------------------

    def _resolve_domain(self, domain: DesignDomain | str) -> DesignDomain:
        if isinstance(domain, DesignDomain):
            return domain
        try:
            return DesignDomain(str(domain).strip().lower())
        except ValueError as exc:
            raise DesignDBError(
                f"unknown domain: {domain!r}", {"domains": self.domains()}
            ) from exc

    def _load_domain(self, domain: DesignDomain) -> list[dict[str, str]]:
        cfg = self._CONFIG[domain]
        return self._load_csv(cfg.filename, f"domain:{domain.value}", cfg)

    def _load_stack(self, stack: str) -> list[dict[str, str]]:
        name = Path(str(stack).strip().lower()).stem  # confine: stem only
        if not name or name in (".", ".."):
            raise DesignDBError(f"invalid stack name: {stack!r}")
        cfg = DomainConfig(
            f"stacks/{name}.csv",
            ("Guideline", "Category"),
            ("Description", "Do", "Don't", "Applies To"),
        )
        return self._load_csv(cfg.filename, f"stack:{name}", cfg)

    def _load_csv(self, filename: str, cache_key: str, cfg: DomainConfig) -> list[dict[str, str]]:
        if cache_key in self._rows:
            return self._rows[cache_key]
        if self._dir is None:
            raise DesignDBError("no design-db directory configured")
        path = self._dir / filename
        if not path.exists():
            self._rows[cache_key] = []
            return []
        with path.open(encoding="utf-8", newline="") as fh:
            rows = [dict(r) for r in csv.DictReader(fh)]
        self._rows[cache_key] = rows
        self._index(cache_key, rows, cfg)
        return rows

    def _index(self, key: str, rows: list[dict[str, str]], cfg: DomainConfig) -> None:
        """Build per-row weighted token lists + document-frequency table."""
        weights = (
            [(c, 3.0) for c in cfg.identity_cols]
            + [(c, 2.0) for c in cfg.keyword_cols]
            + [(c, 1.0) for c in cfg.body_cols]
        )
        docs: list[list[tuple[str, float]]] = []
        df: dict[str, int] = {}
        for row in rows:
            counts: dict[str, float] = {}
            for col, w in weights:
                for tok in _tokens(row.get(col, "") or ""):
                    counts[tok] = counts.get(tok, 0.0) + w
            docs.append(list(counts.items()))
            for tok in counts:
                df[tok] = df.get(tok, 0) + 1
        n = max(len(rows), 1)
        self._doc_tokens[key] = docs
        self._idf[key] = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _rank(
        self, query_tokens: list[str], rows: list[dict[str, str]], key: str
    ) -> list[DesignHit]:
        docs = self._doc_tokens.get(key)
        idf = self._idf.get(key)
        if not rows or docs is None or idf is None:
            return []
        scored: list[DesignHit] = []
        for idx, toks in enumerate(docs):
            token_map = dict(toks)
            score = sum(idf.get(t, 0.0) * min(token_map[t], 3.0) for t in query_tokens if t in token_map)
            coverage = sum(1 for t in set(query_tokens) if t in token_map) / max(len(set(query_tokens)), 1)
            final = score * (0.5 + 0.5 * coverage)
            if final >= self.MIN_SCORE and coverage > 0:
                scored.append(DesignHit(domain=key, score=round(final, 3), row=rows[idx]))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored

    def _top(self, query: str, domain: DesignDomain) -> dict[str, str] | None:
        result = self.search(query, domain=domain, max_results=1)
        return result.hits[0].row if result.hits else None

    def _motion_pick(self, dial: int) -> dict[str, str] | None:
        tier = next(name for name, rng in _MOTION_TIERS.items() if dial in rng)
        rows = self._load_domain(DesignDomain.MOTION)
        for row in rows:
            if row.get("Intensity Tier", "").strip().lower() == tier:
                return row
        return rows[0] if rows else None

    @staticmethod
    def _render_markdown(
        project: str,
        sections: dict[str, dict[str, str] | None],
        spacing: tuple[str, ...],
        dials: dict[str, int],
    ) -> str:
        def row(name: str, rec: dict[str, str] | None, cols: tuple[str, ...]) -> list[str]:
            if not rec:
                return [f"### {name}\n\n_no verified match - falling back to general guidance_\n"]
            lines = [f"### {name}\n"]
            for col in cols:
                value = (rec.get(col) or "").strip()
                if value:
                    lines.append(f"- **{col}:** {value}")
            lines.append("")
            return lines

        out = [f"# Design System - {project}", "",
               f"_dials: variance {dials['variance']}/10, motion {dials['motion']}/10, density {dials['density']}/10_", ""]
        out += row("Product Direction", sections.get("product"),
                   ("Product Type", "Primary Style Recommendation", "Secondary Styles",
                    "Landing Page Pattern", "Color Palette Focus", "Key Considerations"))
        out += row("Reasoning", sections.get("reasoning"),
                   ("Recommended_Pattern", "Style_Priority", "Color_Mood",
                    "Typography_Mood", "Key_Effects", "Anti_Patterns"))
        out += row("Style", sections.get("style"),
                   ("Style Category", "Primary Colors", "Secondary Colors",
                    "Effects & Animation", "Best For", "Do Not Use For",
                    "Implementation Checklist", "Design System Variables"))
        out += row("Palette", sections.get("palette"),
                   ("Product Type", "Primary", "On Primary", "Secondary", "Accent",
                    "Background", "Foreground", "Muted", "Border", "Destructive", "Ring", "Notes"))
        out += row("Typography", sections.get("typography"),
                   ("Font Pairing Name", "Heading Font", "Body Font", "CSS Import",
                    "Tailwind Config", "Best For", "Notes"))
        out += row("Page Pattern", sections.get("landing"),
                   ("Pattern Name", "Section Order", "Primary CTA Placement",
                    "Recommended Effects", "Conversion Optimization"))
        out += row("Motion", sections.get("motion"),
                   ("Category", "Intensity Tier", "Trigger", "Duration", "Easing",
                    "GSAP Snippet", "Do", "Don't", "Performance Notes"))
        out += ["### Spacing", "", f"- scale: `{' / '.join(spacing)}`", ""]
        return "\n".join(out)


class DesignDBError(AizeeError):
    """Raised when the design DB encounters an error."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("DESIGN_DB_ERROR", message, ErrorSeverity.LOW, context)
