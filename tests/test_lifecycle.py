"""Tests for BMAD lifecycle phase detection and persona routing bias."""

from __future__ import annotations

from pathlib import Path

from runtime.lifecycle import LifecyclePhase, detect_phase
from runtime.persona import PersonaDetector, inject_persona_context


def _write_bmad(root: Path, initiative: str = "init-test") -> Path:
    bmad = root / "_bmad"
    bmad.mkdir(parents=True)
    (bmad / "config.toml").write_text(
        "[core]\n"
        'project_name = "t"\n'
        'output_folder = "{project-root}/_bmad-output"\n'
        f'active_initiative = "{initiative}"\n',
        encoding="utf-8",
    )
    init_dir = root / "_bmad-output" / initiative
    init_dir.mkdir(parents=True)
    return init_dir


# --- detect_phase ---


def test_detect_phase_no_bmad(tmp_path: Path) -> None:
    assert detect_phase(tmp_path) is None


def test_detect_phase_no_active_initiative(tmp_path: Path) -> None:
    (tmp_path / "_bmad").mkdir()
    (tmp_path / "_bmad" / "config.toml").write_text(
        "[core]\nproject_name = 't'\n", encoding="utf-8"
    )
    assert detect_phase(tmp_path) is None


def test_detect_phase_empty_initiative_is_discovery(tmp_path: Path) -> None:
    _write_bmad(tmp_path)
    assert detect_phase(tmp_path) == LifecyclePhase.DISCOVERY


def test_detect_phase_prd_marker(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    (init_dir / "prd-launch").mkdir()
    (init_dir / "prd-launch" / "prd-launch.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.PRD


def test_detect_phase_epic_is_breakdown(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    epic = init_dir / "tickets" / "epic-1"
    epic.mkdir(parents=True)
    (epic / "epic-1.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.BREAKDOWN


def test_detect_phase_story_is_implementation(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    epic = init_dir / "tickets" / "epic-1"
    epic.mkdir(parents=True)
    (epic / "epic-1.md").write_text("x", encoding="utf-8")
    (epic / "story-1.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.IMPLEMENTATION


def test_detect_phase_most_advanced_wins(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    (init_dir / "prd-old.md").write_text("x", encoding="utf-8")
    ux = init_dir / "ux-design"
    ux.mkdir()
    (ux / "ux-flows.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.UX


def test_detect_phase_architecture(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    (init_dir / "architecture-v1.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.ARCHITECTURE


def test_detect_phase_missing_initiative_dir(tmp_path: Path) -> None:
    _write_bmad(tmp_path, initiative="ghost")
    # config points at an initiative whose folder was never created
    (tmp_path / "_bmad-output" / "ghost").rmdir()
    assert detect_phase(tmp_path) is None


# --- persona bias + handoff hint ---


def _detector(phase: LifecyclePhase | None) -> PersonaDetector:
    return PersonaDetector(phase_detector=lambda: phase)


def test_implementation_phase_biases_generic_text_to_dev() -> None:
    result = _detector(LifecyclePhase.IMPLEMENTATION).detect_multiple("كمّل الشغل")
    assert "DEV" in result["personas"]
    assert result["lifecycle_phase"] == "implementation"


def test_no_phase_keeps_keyword_routing() -> None:
    result = _detector(None).detect_multiple("كمّل الشغل")
    assert result["lifecycle_phase"] is None
    # generic text with no keywords falls back to the default persona
    assert result["persona"] == result["default"]


def test_strong_keywords_still_win_over_phase_bias() -> None:
    result = _detector(LifecyclePhase.IMPLEMENTATION).detect_multiple(
        "صمم landing page جميلة وتحسين conversion"
    )
    # UX/CRO keywords should outrank the DEV phase bonus
    assert result["persona"] in {"UX", "CRO", "MARKETING", "GROWTH"}


def test_next_persona_hint_populated() -> None:
    result = _detector(None).detect_multiple(
        "صمم صفحة وحلل السوق واعمل architecture review", max_personas=1
    )
    assert result["next_persona_hint"] in PersonaDetector.PERSONAS
    assert result["next_persona_hint"] != result["persona"]


def test_inject_persona_context_propagates_phase_and_hint() -> None:
    detector = _detector(LifecyclePhase.IMPLEMENTATION)
    context = {"message": "راجع الـpull request ده"}
    inject_persona_context(detector, context)
    assert context.get("lifecycle_phase") == "implementation"
    assert "personas" in context

# --- config / scan edge cases ---


def test_detect_phase_missing_config_toml(tmp_path: Path) -> None:
    (tmp_path / "_bmad").mkdir()
    assert detect_phase(tmp_path) is None


def test_detect_phase_malformed_toml(tmp_path: Path) -> None:
    bmad = tmp_path / "_bmad"
    bmad.mkdir()
    (bmad / "config.toml").write_text("[[[ not toml", encoding="utf-8")
    assert detect_phase(tmp_path) is None


def test_detect_phase_core_not_dict(tmp_path: Path) -> None:
    bmad = tmp_path / "_bmad"
    bmad.mkdir()
    (bmad / "config.toml").write_text('core = "oops"\n', encoding="utf-8")
    assert detect_phase(tmp_path) is None


def test_detect_phase_non_str_output_folder_uses_default(tmp_path: Path) -> None:
    bmad = tmp_path / "_bmad"
    bmad.mkdir()
    (bmad / "config.toml").write_text(
        "[core]\noutput_folder = 123\nactive_initiative = \"i\"\n", encoding="utf-8"
    )
    (tmp_path / "_bmad-output" / "i").mkdir(parents=True)
    assert detect_phase(tmp_path) == LifecyclePhase.DISCOVERY


def test_detect_phase_non_marker_files_default_discovery(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    (init_dir / "notes.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.DISCOVERY


def test_detect_phase_marker_beyond_max_depth_skipped(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    deep = init_dir / "a" / "b" / "c" / "d" / "e" / "f"
    deep.mkdir(parents=True)
    (deep / "retro.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.DISCOVERY


def test_detect_phase_scan_limit_zero_breaks(tmp_path: Path, monkeypatch) -> None:
    from runtime import lifecycle

    init_dir = _write_bmad(tmp_path)
    (init_dir / "retro.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(lifecycle, "_MAX_SCAN_FILES", 0)
    assert detect_phase(tmp_path) == LifecyclePhase.DISCOVERY


def test_detect_phase_lower_rank_marker_after_higher(tmp_path: Path) -> None:
    init_dir = _write_bmad(tmp_path)
    # Alphabetical rglob order scans aaa-retro first (rank 7); every
    # lower-rank file after it exercises the rank<=best_rank branch.
    (init_dir / "aaa-retro.md").write_text("x", encoding="utf-8")
    (init_dir / "zzz-brief.md").write_text("x", encoding="utf-8")
    (init_dir / "zzz2-prd.md").write_text("x", encoding="utf-8")
    assert detect_phase(tmp_path) == LifecyclePhase.RETROSPECTIVE


def test_detect_phase_initiative_oserror(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock

    from runtime import lifecycle

    monkeypatch.setattr(lifecycle, "_initiative_dir", Mock(side_effect=OSError("boom")))
    assert detect_phase(tmp_path) is None


def test_detect_phase_scan_oserror(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock

    from runtime import lifecycle

    monkeypatch.setattr(lifecycle, "_initiative_dir", lambda _root: tmp_path)
    monkeypatch.setattr(lifecycle, "_scan_phase", Mock(side_effect=OSError("boom")))
    assert detect_phase(tmp_path) is None
