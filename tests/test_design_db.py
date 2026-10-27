"""Tests for runtime.design_db - searchable design intelligence corpus."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from runtime.design_db import DesignDB, DesignDBError

DATA_DIR = Path(__file__).resolve().parents[1] / "design-db"


@pytest.fixture
def db() -> DesignDB:
    return DesignDB(DATA_DIR)


@pytest.fixture
def empty_db(tmp_path: Path) -> DesignDB:
    return DesignDB(tmp_path)


def _write_csv(path: Path, cols: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)


# --- Corpus presence ---

def test_corpus_available(db: DesignDB) -> None:
    assert db.available
    assert "style" in db.domains()
    assert "ux" in db.domains()


def test_stacks_listed(db: DesignDB) -> None:
    stacks = db.stacks()
    assert "react" in stacks
    assert "laravel" in stacks


# --- Search ---

def test_search_style_returns_ranked_hits(db: DesignDB) -> None:
    res = db.search("saas analytics dashboard", domain="style", max_results=3)
    assert not res.fallback
    assert 1 <= len(res.hits) <= 3
    assert res.hits[0].score >= res.hits[-1].score
    assert res.hits[0].title
    assert res.domain == "style"


def test_search_auto_detects_domain(db: DesignDB) -> None:
    res = db.search("form validation error placement")
    assert res.domain == "ux"
    assert not res.fallback


def test_search_typography(db: DesignDB) -> None:
    res = db.search("elegant editorial serif", domain="typography", max_results=2)
    assert not res.fallback


def test_search_stack_guidelines(db: DesignDB) -> None:
    res = db.search("lazy load components", stack="react", max_results=2)
    assert res.domain == "stack:react"
    assert not res.fallback


def test_search_honest_empty_on_no_match(db: DesignDB) -> None:
    res = db.search("xyzzy quantum flux capacitor", domain="icons")
    assert res.fallback
    assert res.hits == []


def test_search_empty_query_raises(db: DesignDB) -> None:
    with pytest.raises(DesignDBError):
        db.search("", domain="style")


def test_search_unknown_domain_raises(db: DesignDB) -> None:
    with pytest.raises(DesignDBError):
        db.search("x", domain="not-a-domain")


def test_search_missing_corpus_returns_empty(empty_db: DesignDB) -> None:
    res = empty_db.search("anything", domain="style")
    assert res.fallback


# --- Design system aggregation ---

def test_design_system_sections(db: DesignDB) -> None:
    res = db.design_system("b2b saas analytics", project="Acme")
    assert res.dials == {"variance": 5, "motion": 5, "density": 5}
    assert "# Design System - Acme" in res.markdown
    assert "### Motion" in res.markdown
    assert "### Spacing" in res.markdown


def test_design_system_dial_validation(db: DesignDB) -> None:
    with pytest.raises(DesignDBError):
        db.design_system("x", variance=11)
    with pytest.raises(DesignDBError):
        db.design_system("x", density=0)


def test_design_system_motion_tier_scales(db: DesignDB) -> None:
    low = db.design_system("saas", motion=2).sections["motion"]
    high = db.design_system("saas", motion=9).sections["motion"]
    if low and high:
        assert low.get("Intensity Tier", "").lower() != high.get("Intensity Tier", "").lower()


def test_design_system_density_scales_spacing(db: DesignDB) -> None:
    tight = db.design_system("saas", density=9).sections["spacing_scale"]
    airy = db.design_system("saas", density=1).sections["spacing_scale"]
    assert tight != airy


# --- Stemming / normalization ---

def test_plural_matches_singular(db: DesignDB) -> None:
    # 'dashboards' in corpus should match query 'dashboard'
    res = db.search("dashboard", domain="style", max_results=3)
    assert not res.fallback


def test_missing_stack_file_raises_or_empty(db: DesignDB) -> None:
    res = db.search("x", stack="nonexistent-stack")
    assert res.fallback


def test_stack_traversal_rejected(db: DesignDB) -> None:
    # Path("..").stem is '..' -> rejected by the guard
    with pytest.raises(DesignDBError):
        db.search("x", stack="..")


# --- Coverage: fallback paths ---

def test_hit_title_fallback() -> None:
    from runtime.design_db import DesignHit

    hit = DesignHit(domain="x", score=1.0, row={"No": "5", "Notes": "misc"})
    assert hit.title == "5"


def test_stacks_none_dir() -> None:
    assert DesignDB(None).stacks() == []


def test_stacks_dir_missing(empty_db: DesignDB) -> None:
    assert empty_db.stacks() == []


def test_detect_domain_fallthrough(db: DesignDB) -> None:
    assert db.detect_domain("zzz qqq").value == "ux"


def test_search_no_dir_raises() -> None:
    with pytest.raises(DesignDBError):
        DesignDB(None).search("x", domain="style")


def test_design_system_empty_corpus(empty_db: DesignDB) -> None:
    res = empty_db.design_system("anything")
    assert res.sections["product"] is None
    assert res.sections["motion"] is None
    assert "_no verified match" in res.markdown


def test_motion_pick_tier_fallback(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "motion.csv",
        ["Category", "Intensity Tier", "Trigger"],
        [["General", "WeirdTier", "load"]],
    )
    db = DesignDB(tmp_path)
    pick = db._motion_pick(5)
    assert pick is not None and pick["Category"] == "General"


def test_render_markdown_skips_empty_cells() -> None:
    md = DesignDB._render_markdown(
        "P",
        {
            "product": {"Product Type": "SaaS", "Keywords": ""},
            "reasoning": None, "style": None, "palette": None,
            "typography": None, "landing": None, "motion": None,
        },
        ("8px", "16px"),
        {"variance": 5, "motion": 5, "density": 5},
    )
    assert "**Product Type:** SaaS" in md
    assert "Keywords" not in md
