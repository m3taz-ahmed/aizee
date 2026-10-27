"""Design Library - brand design systems loaded on demand.

Inspired by zeta92/design-library-plugin. Brand systems live as
``design-library/<brand>/DESIGN.md`` files with tokens (colors, typography,
spacing, radii, shadows, grid) and design principles. ``CATALOG`` lists
well-known brand names as reference suggestions; only brands with a real
file on disk (bundled seeds or imported via :meth:`DesignLibrary.import_brand`)
can be loaded and mixed.

The library supports:
- **Single brand** - load one brand's full design system
- **Simple mix** - combine 2-3 brands (colors from A, typography from B)
- **Granular mix** - mix specific sections (A:colors + B:typography)
- **Auto-detect** - scan project and suggest best-fit brands
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar

from runtime.schemas import AizeeError, ErrorSeverity


class DesignSection(str, Enum):
    """Sections of a brand design system."""

    COLORS = "colors"
    TYPOGRAPHY = "typography"
    COMPONENTS = "components"
    LAYOUT = "layout"
    ELEVATION = "elevation"


class ProjectType(str, Enum):
    """Detected project type for auto-suggestion."""

    LANDING_PAGE = "landing_page"
    SAAS_APP = "saas_app"
    DESIGN_SYSTEM = "design_system"
    ECOMMERCE = "ecommerce"
    PORTFOLIO = "portfolio"
    BLOG = "blog"
    DASHBOARD = "dashboard"
    MOBILE_APP = "mobile_app"
    UNKNOWN = "unknown"


@dataclass
class BrandDesignSystem:
    """A loaded brand design system."""

    name: str
    path: Path
    content: str = ""
    sections: dict[str, str] = field(default_factory=dict)

    def get_section(self, section: DesignSection) -> str:
        """Extract a specific section from the DESIGN.md content."""
        if section.value in self.sections:
            return self.sections[section.value]
        # Try to extract from content
        pattern = f"## {section.value.title()}"
        idx = self.content.lower().find(pattern.lower())
        if idx == -1:
            return ""
        end_idx = self.content.find("\n## ", idx + 1)
        extracted = self.content[idx:] if end_idx == -1 else self.content[idx:end_idx]
        self.sections[section.value] = extracted
        return extracted


@dataclass
class FusionResult:
    """Result of mixing multiple brand design systems."""

    brands: list[str]
    section_mapping: dict[str, str]  # section -> brand name
    content: str
    rationale: str


@dataclass
class DesignLint:
    """Result of linting one brand's DESIGN.md (google-labs-code/design.md spec)."""

    brand: str
    ok: bool
    has_frontmatter: bool
    token_count: int
    issues: list[str] = field(default_factory=list)  # each prefixed "error:"/"warning:"


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio between two #rrggbb colors (1-21)."""
    def lum(h: str) -> float:
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (1, 3, 5))
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    l1, l2 = sorted((lum(hex_a), lum(hex_b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


class DesignLibrary:
    """Catalog of brand design systems with loading and mixing capabilities.

    Brand DESIGN.md files live in ``<root>/design-library/<brand>/DESIGN.md``.
    The library lazily loads brands on first access and caches them.
    """

    DESIGN_FILE: ClassVar[str] = "DESIGN.md"

    # Curated catalog of 56 unique brand design systems.
    # In production, these would be downloaded from the awesome-design-md repo.
    CATALOG: ClassVar[list[str]] = [
        "stripe", "linear", "vercel", "figma", "google", "anthropic",
        "apple", "microsoft", "github", "notion", "slack", "discord",
        "spotify", "airbnb", "uber", "shopify", "framer", "supabase",
        "clerk", "resend", "posthog", "plane", "calcom", "dub",
        "openai", "perplexity", "mistral", "cohere", "huggingface",
        "sentry", "datadog", "cloudflare", "netlify", "railway",
        "fly", "render", "heroku", "digitalocean", "linode",
        "tailwind", "shadcn", "radix", "cmdk", "vaul", "sonner",
        "astria", "creatio", "envshare", "nutlope",
        "react-email", "koala", "flightscope",
        "chronark", "leerob", "steven-tey", "shadcn-personal",
    ]

    # Project type -> recommended brands mapping
    PROJECT_SUGGESTIONS: ClassVar[dict[ProjectType, list[str]]] = {
        ProjectType.LANDING_PAGE: ["linear", "vercel", "framer", "dub"],
        ProjectType.SAAS_APP: ["stripe", "linear", "supabase", "clerk"],
        ProjectType.DESIGN_SYSTEM: ["figma", "shadcn", "radix", "tailwind"],
        ProjectType.ECOMMERCE: ["shopify", "stripe", "airbnb"],
        ProjectType.PORTFOLIO: ["vercel", "framer", "chronark", "leerob"],
        ProjectType.BLOG: ["vercel", "leerob", "steven-tey"],
        ProjectType.DASHBOARD: ["linear", "sentry", "datadog", "posthog"],
        ProjectType.MOBILE_APP: ["apple", "google", "spotify", "airbnb"],
        ProjectType.UNKNOWN: ["vercel", "linear", "stripe"],
    }

    def __init__(self, library_dir: Path | None = None) -> None:
        """Initialize the design library.

        Args:
            library_dir: Directory containing brand folders. Defaults to
                ``<root>/design-library/``.
        """
        self._dir = library_dir
        self._cache: dict[str, BrandDesignSystem] = {}

    @property
    def available_brands(self) -> list[str]:
        """List all available brand names (catalog + filesystem).

        WARNING: this is the union of the advertised CATALOG and on-disk
        brands. Use :attr:`installed_brands` when you need what can actually
        be loaded; :attr:`catalog_brands` for importable-but-absent names.
        """
        return sorted(set(self.CATALOG) | set(self.installed_brands))

    @property
    def installed_brands(self) -> list[str]:
        """Brands with a real DESIGN.md on disk (loadable)."""
        if not self._dir or not self._dir.exists():
            return []
        return sorted(
            d.name.lower()
            for d in self._dir.iterdir()
            if d.is_dir() and (d / self.DESIGN_FILE).exists()
        )

    @property
    def catalog_brands(self) -> list[str]:
        """Advertised catalog names not yet installed on disk."""
        return sorted(set(self.CATALOG) - set(self.installed_brands))

    def validate(self, brand: str) -> DesignLint:
        """Lint one brand's DESIGN.md against the structured-spec checklist.

        Checks: file exists, YAML frontmatter present (machine-readable
        tokens), hex color tokens present, text/background contrast pairs
        meeting WCAG AA (4.5:1), and a typography section.
        """
        issues: list[str] = []
        system = self.load(brand)
        if system is None:
            return DesignLint(brand=brand.lower(), ok=False, has_frontmatter=False,
                              token_count=0, issues=["error: no DESIGN.md on disk"])

        content = system.content
        fm = re.search(r"\A---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        has_fm = fm is not None
        if not has_fm:
            issues.append("warning: no YAML frontmatter - tokens not machine-readable "
                          "(see google-labs-code/design.md spec)")
        fm_text = fm.group(1) if fm else ""

        tokens = re.findall(r"#[0-9a-fA-F]{6}\b", fm_text or content)
        if not tokens:
            issues.append("warning: no hex color tokens found")
        if not re.search(r"(?i)(font|typograph)", content):
            issues.append("warning: no typography guidance found")

        if has_fm:
            issues.extend(self._check_contrast_pairs(fm_text))
        if not re.search(r"^#\s", content, re.MULTILINE):
            issues.append("warning: no top-level heading")
        ok = not any(i.startswith("error:") for i in issues)
        return DesignLint(brand=brand.lower(), ok=ok, has_frontmatter=has_fm,
                          token_count=len(tokens), issues=issues)

    def _check_contrast_pairs(self, fm_text: str) -> list[str]:
        """Find background/foreground-style hex pairs in frontmatter and check WCAG AA."""
        issues: list[str] = []
        pairs = re.findall(
            r"(?i)(background|surface|bg|base)\w*\s*[:=]\s*['\"]?(#[0-9a-fA-F]{6})"
            r"|(foreground|text|fg|ink|on[_-]?\w+)\w*\s*[:=]\s*['\"]?(#[0-9a-fA-F]{6})",
            fm_text,
        )
        bg_hexes = [g[1] for g in pairs if g[1]]
        fg_hexes = [g[3] for g in pairs if g[3]]
        for bg in bg_hexes:
            for fg in fg_hexes:
                ratio = _contrast_ratio(bg, fg)
                if ratio < 4.5:
                    issues.append(
                        f"warning: contrast {ratio:.2f}:1 between {fg} and {bg} "
                        "fails WCAG AA (4.5:1)")
        return issues

    def load(self, brand: str) -> BrandDesignSystem | None:
        """Load a single brand's design system.

        Args:
            brand: Brand name (case-insensitive, e.g., "Stripe" -> "stripe").

        Returns:
            BrandDesignSystem or None if not found.
        """
        key = brand.lower().strip()
        # Confine brand key: reject path traversal and separators.
        if not key or key in (".", "..") or ".." in key or "/" in key or "\\" in key:
            return None
        if key in self._cache:
            return self._cache[key]

        if self._dir is None:
            return None

        brand_path = self._dir / key / self.DESIGN_FILE
        if not brand_path.exists():
            return None

        try:
            content = brand_path.read_text(encoding="utf-8")
        except OSError:
            return None

        system = BrandDesignSystem(name=key, path=brand_path, content=content)
        self._cache[key] = system
        return system

    def mix(
        self,
        brands: list[str],
        section_mapping: dict[DesignSection, str] | None = None,
    ) -> FusionResult | None:
        """Mix multiple brand design systems.

        Args:
            brands: List of 2-3 brand names to mix.
            section_mapping: Optional explicit section->brand mapping.
                If None, uses defaults (colors/components/elevation from first,
                typography/layout from second).

        Returns:
            FusionResult or None if any brand is missing.
        """
        loaded: list[BrandDesignSystem] = []
        for b in brands:
            system = self.load(b)
            if system is None:
                return None
            loaded.append(system)

        if section_mapping is None:
            section_mapping = self._default_mapping(brands)

        sections_content: list[str] = []
        mapping_str: dict[str, str] = {}
        for section, brand_name in section_mapping.items():
            # Fail-closed: unknown brand in mapping -> abort mix (return None).
            system = next((s for s in loaded if s.name == brand_name.lower()), None)
            if system is None:
                return None
            section_text = system.get_section(section)
            if section_text:
                sections_content.append(section_text)
                mapping_str[section.value] = brand_name

        rationale = self._build_rationale(brands, mapping_str)
        return FusionResult(
            brands=brands,
            section_mapping=mapping_str,
            content="\n\n---\n\n".join(sections_content),
            rationale=rationale,
        )

    def import_brand(
        self, name: str, source: str | Path, *, overwrite: bool = False
    ) -> BrandDesignSystem:
        """Import an external DESIGN.md into the library (e.g., a Refero export).

        Args:
            name: Brand key (confined like ``load`` — no separators/traversal).
            source: Path to a ``DESIGN.md`` file, or raw markdown content.
            overwrite: Replace an existing imported brand.

        Returns:
            The loaded ``BrandDesignSystem``.

        Raises:
            DesignLibraryError: invalid name/source, duplicate without
                ``overwrite``, or no library directory configured.

        Note: imported content is stored as reference data only — it is
        never executed. Validation checks structure (a markdown heading),
        not semantics.
        """
        if self._dir is None:
            raise DesignLibraryError("no library directory configured")
        key = name.lower().strip()
        if not key or key in (".", "..") or ".." in key or "/" in key or "\\" in key:
            raise DesignLibraryError(f"invalid brand name: {name!r}")

        content = self._read_source(source)
        if "#" not in content.split("\n", 1)[0] and "\n#" not in content:
            raise DesignLibraryError("source does not look like a DESIGN.md (no markdown heading)")
        if len(content) > 512 * 1024:
            raise DesignLibraryError("source too large (>512KB)")

        brand_dir = self._dir / key
        dest = brand_dir / self.DESIGN_FILE
        if dest.exists() and not overwrite:
            raise DesignLibraryError(f"brand already exists: {key}", {"path": str(dest)})
        try:
            brand_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise DesignLibraryError(f"cannot write brand file: {exc}") from exc
        self._cache.pop(key, None)
        system = self.load(key)
        if system is None:  # pragma: no cover - file was just written
            raise DesignLibraryError(f"imported brand failed to load: {key}")
        return system

    def _read_source(self, source: str | Path) -> str:
        """Resolve ``source`` to markdown text: file path wins, else raw text."""
        if isinstance(source, Path):
            try:
                return source.read_text(encoding="utf-8")
            except OSError as exc:
                raise DesignLibraryError(f"cannot read source file: {exc}") from exc
        with contextlib.suppress(OSError, ValueError):
            candidate = Path(source)
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        return source

    def suggest(self, project_type: ProjectType) -> list[str]:
        """Suggest best-fit brands for a project type."""
        return list(self.PROJECT_SUGGESTIONS.get(project_type, self.PROJECT_SUGGESTIONS[ProjectType.UNKNOWN]))

    def detect_project_type(self, project_dir: Path) -> ProjectType:
        """Detect project type from directory contents."""
        if not project_dir.exists():
            return ProjectType.UNKNOWN

        indicators: list[tuple[ProjectType, list[str]]] = [
            (ProjectType.ECOMMERCE, ["shop", "product", "cart", "checkout", "woocommerce"]),
            (ProjectType.DASHBOARD, ["dashboard", "admin", "panel", "analytics"]),
            (ProjectType.LANDING_PAGE, ["landing", "hero", "marketing", "pitch"]),
            (ProjectType.BLOG, ["blog", "article", "post", "markdown"]),
            (ProjectType.PORTFOLIO, ["portfolio", "resume", "cv", "about"]),
            (ProjectType.MOBILE_APP, ["flutter", "react-native", "expo", "ios", "android"]),
            (ProjectType.DESIGN_SYSTEM, ["design-system", "tokens", "storybook", "components"]),
            (ProjectType.SAAS_APP, ["app", "saas", "auth", "dashboard", "api"]),
        ]

        all_files: list[str] = []
        # Bounded scan: max 2000 files, skip vendored dirs, no symlink follow.
        _skip_dirs = {"node_modules", ".git", ".venv", "__pycache__"}
        _count = 0
        _stack: list[Path] = [project_dir]
        while _stack and _count < 2000:
            current = _stack.pop()
            try:
                if current.is_symlink():
                    continue
                if current.is_dir():
                    if current.name in _skip_dirs and current != project_dir:
                        continue
                    try:
                        with os.scandir(current) as it:
                            entries = list(it)
                    except OSError:
                        continue
                    for entry in entries:
                        try:
                            if entry.is_symlink():
                                continue
                        except OSError:
                            continue
                        _stack.append(Path(entry.path))
                elif current.is_file():
                    _count += 1
                    all_files.append(str(current).lower())
            except OSError:
                continue

        scores: dict[ProjectType, int] = {}
        for ptype, keywords in indicators:
            score = sum(1 for kw in keywords if any(kw in fp for fp in all_files))
            if score > 0:
                scores[ptype] = score

        if not scores:
            return ProjectType.UNKNOWN
        return max(scores, key=lambda k: scores[k])

    def _default_mapping(self, brands: list[str]) -> dict[DesignSection, str]:
        """Default section->brand mapping for simple mixes."""
        first = brands[0] if brands else ""
        second = brands[1] if len(brands) > 1 else first
        return {
            DesignSection.COLORS: first,
            DesignSection.COMPONENTS: first,
            DesignSection.ELEVATION: first,
            DesignSection.TYPOGRAPHY: second,
            DesignSection.LAYOUT: second,
        }

    def _build_rationale(self, brands: list[str], mapping: dict[str, str]) -> str:
        """Build a human-readable rationale for the fusion."""
        lines = [f"Fusion: {' + '.join(brands)}"]
        for section, brand in sorted(mapping.items()):
            lines.append(f"  {section} -> {brand}")
        lines.append(f"Rationale: This combination pairs {'visual identity from ' + brands[0] if brands else ''}"
                     f" with {'structural rhythm from ' + brands[1] if len(brands) > 1 else 'cohesive design'}.")
        return "\n".join(lines)


# -- Exception -----------------------------------------------------------------


class DesignLibraryError(AizeeError):
    """Raised when the design library encounters an error."""

    def __init__(self, message: str, context: dict[str, object] | None = None) -> None:
        super().__init__("DESIGN_LIBRARY_ERROR", message, ErrorSeverity.LOW, context)
