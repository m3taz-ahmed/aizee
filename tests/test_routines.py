"""Tests for runtime.routines — recurring routine dossiers + durable state."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime import routines as rt


def _dossier(root: Path, name: str, triggers: list[str] | None = None, extra: str = "") -> Path:
    trig = "[" + ", ".join(triggers or []) + "]"
    path = root / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: test routine\ntriggers: {trig}\n{extra}---\n# R\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    """(os_root, home) with all three routine dirs."""
    os_root, home = tmp_path / "os", tmp_path / "home"
    for d in (
        os_root / "refs" / "routines",
        os_root / "routines",
        home / ".aizee" / "routines",
    ):
        d.mkdir(parents=True)
    return os_root, home


# --- discovery -------------------------------------------------------------


def test_discover_all_scopes(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "refs" / "routines", "proj-r")
    _dossier(os_root / "routines", "ship-r")
    _dossier(home / ".aizee" / "routines", "user-r", triggers=["وظايف"])
    names = {r.name: r.scope for r in rt.discover(os_root, home)}
    assert names == {"proj-r": "project", "ship-r": "shipped", "user-r": "user"}


def test_discover_skips_templates_and_readme(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "routines", "_template-routine")
    (os_root / "routines" / "README.md").write_text("# docs", encoding="utf-8")
    _dossier(os_root / "routines", "real-one")
    assert [r.name for r in rt.discover(os_root, home)] == ["real-one"]


def test_scope_priority_dedups_names(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "routines", "same")
    _dossier(home / ".aizee" / "routines", "same")
    _dossier(os_root / "refs" / "routines", "same")
    found = rt.discover(os_root, home)
    assert len(found) == 1 and found[0].scope == "project"


def test_invalid_name_rejected(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "routines", "Bad Name!")
    assert rt.discover(os_root, home) == []


def test_discover_missing_dirs(tmp_path: Path) -> None:
    empty = tmp_path / "bare"
    empty.mkdir()
    assert rt.discover(empty, tmp_path / "nohome") == []


# --- matching ---------------------------------------------------------------


def test_match_arabic_trigger(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "job-hunt", triggers=["وظايف", "jobs"])
    matches = rt.match_routines("عايز اتابع الوظايف", rt.discover(os_root, home))
    assert matches and matches[0].routine.name == "job-hunt"
    assert "وظايف" in matches[0].matched


def test_match_name_and_ranking(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "job-hunt", triggers=["jobs"])
    _dossier(home / ".aizee" / "routines", "job-feed", triggers=["jobs"])
    all_r = rt.discover(os_root, home)
    exact = rt.match_routines("job-hunt", all_r)
    assert exact[0].score == 100.0
    broad = rt.match_routines("show me jobs", all_r)
    assert len(broad) == 2  # both trigger-matched


def test_match_empty_query(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    assert rt.match_routines("   ", rt.discover(os_root, home)) == []


def test_resolve_name_and_scope_prefix(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "x", triggers=["nothing"])
    assert rt.resolve(os_root, "x", home).scope == "user"  # type: ignore[union-attr]
    assert rt.resolve(os_root, "user:x", home).name == "x"  # type: ignore[union-attr]
    assert rt.resolve(os_root, "project:x", home) is None
    assert rt.resolve(os_root, "totally unrelated", home) is None


# --- state lifecycle --------------------------------------------------------


def _mk(os_root: Path, home: Path, name: str = "r1") -> rt.Routine:
    _dossier(home / ".aizee" / "routines", name)
    routine = rt.resolve(os_root, name, home)
    assert routine is not None
    return routine


def test_begin_done_idempotent(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    first = rt.begin(r)
    assert first["already_ran"] is False
    second = rt.begin(r)
    assert second["already_ran"] is True and second["in_progress"] is True
    rep = rt.complete(r, summary="did things", artifact="runs/a.md")
    assert rep["runs"] == 1
    third = rt.begin(r)
    assert third["already_ran"] is True and third["in_progress"] is False
    forced = rt.begin(r, force=True)
    assert forced["already_ran"] is False and forced["resumed"] is True


def test_complete_dedups_run_id(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    rt.begin(r)
    rt.complete(r, summary="one")
    rt.begin(r, force=True)
    rep = rt.complete(r, summary="two")
    state = rt.load_state(r)
    assert rep["runs"] == 1 and state["runs"][0]["summary"] == "two"
    assert state["in_progress"] is None


def test_seen_store(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    assert rt.seen_check(r, ["a", "b"]) == {"a": False, "b": False}
    rep = rt.seen_add(r, ["a", "b", "a"])
    assert rep == {"added": 2, "total": 2}
    assert rt.seen_check(r, ["a", "c"]) == {"a": True, "c": False}


def test_corrupt_state_recovers(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    r.state_path.parent.mkdir(parents=True, exist_ok=True)
    r.state_path.write_text("{broken json", encoding="utf-8")
    state = rt.load_state(r)
    assert state["schema"] == rt.SCHEMA and state["seen"] == []


def test_shipped_state_goes_to_state_dir(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "routines", "ship")
    r = rt.resolve(os_root, "ship", home)
    assert r is not None
    assert r.state_path == os_root / "state" / "routines" / "ship.state.json"


def test_state_override_frontmatter(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(
        home / ".aizee" / "routines", "custom",
        extra="state: sub/custom-state.json\n",
    )
    r = rt.resolve(os_root, "custom", home)
    assert r is not None
    assert r.state_path.name == "custom-state.json"


# --- scaffold + catalog -----------------------------------------------------


def test_scaffold_roundtrip(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    rep = rt.scaffold("watch-thing", os_root, scope="user", home=home,
                      description="d", triggers=["watch"])
    assert Path(rep["dossier"]).exists() and Path(rep["state"]).exists()
    r = rt.resolve(os_root, "watch-thing", home)
    assert r is not None and r.triggers == ("watch",)
    with pytest.raises(ValueError):
        rt.scaffold("watch-thing", os_root, scope="user", home=home)
    with pytest.raises(ValueError):
        rt.scaffold("Bad Name", os_root, scope="user", home=home)


def test_to_descriptors_and_find(roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "job-hunt", triggers=["jobs"])
    mine = rt.discover(os_root, home)
    monkeypatch.setattr("runtime.routines.discover", lambda root, home=None: mine)
    from runtime.find import find

    results = find("show me new jobs", os_root)
    kinds = {(r.name, r.kind) for r in results}
    assert ("job-hunt", "routine") in kinds


# --- coverage: edge paths ----------------------------------------------------


def test_match_to_dict_and_name_substring(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "job-hunt")
    matches = rt.match_routines("please run job-hunt now", rt.discover(os_root, home))
    assert matches[0].score >= 60.0
    d = matches[0].to_dict()
    assert d["name"] == "job-hunt" and "job-hunt" in d["matched"]


def test_frontmatter_variants(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    routines_dir = home / ".aizee" / "routines"
    (routines_dir / "nofm.md").write_text("# no frontmatter at all\n", encoding="utf-8")
    (routines_dir / "badfm.md").write_text("---\nkey: [unclosed\n---\n", encoding="utf-8")
    (routines_dir / "listfm.md").write_text("---\n- a\n- b\n---\n", encoding="utf-8")
    names = {r.name for r in rt.discover(os_root, home)}
    assert {"nofm", "badfm", "listfm"} <= names  # all fall back to stem names


def test_load_routine_read_oserror(roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    os_root, home = roots
    p = _dossier(home / ".aizee" / "routines", "broken")

    def boom(*args: object, **kwargs: object) -> str:
        raise OSError("nope")

    monkeypatch.setattr(Path, "read_text", boom)
    assert rt._load_routine(p, "user", os_root) is None


def test_resolve_fuzzy_fallback(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(home / ".aizee" / "routines", "job-hunt", triggers=["jobs"])
    r = rt.resolve(os_root, "check new jobs please", home)
    assert r is not None and r.name == "job-hunt"


def test_load_state_wrong_schema_and_missing_keys(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    r.state_path.parent.mkdir(parents=True, exist_ok=True)
    r.state_path.write_text('{"other": 1}', encoding="utf-8")
    assert rt.load_state(r)["runs"] == []
    r.state_path.write_text('{"schema": "aizee.routine-state.v1"}', encoding="utf-8")
    state = rt.load_state(r)
    assert state["seen"] == [] and state["last_run"] is None


def test_save_state_failure_cleans_tmp(roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    r.state_path.parent.mkdir(parents=True, exist_ok=True)

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rt.os, "replace", boom)
    with pytest.raises(OSError):
        rt.save_state(r, rt._empty_state("r"))
    assert list(r.state_path.parent.glob(".state-*")) == []


def test_status_view(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    st = rt.status(r)
    assert st["ran_today"] is False and st["seen"] == 0
    assert st["today_run_id"].startswith("r1_")


def test_complete_with_notes(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    rt.begin(r)
    rt.complete(r, summary="s", notes="remember this")
    assert rt.load_state(r)["notes"] == "remember this"


def test_seen_cap_eviction(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    r = _mk(os_root, home)
    rep = rt.seen_add(r, [f"id{i}" for i in range(5001)])
    assert rep["total"] == 5000
    assert rt.seen_check(r, ["id0"]) == {"id0": False}  # oldest evicted
    assert rt.seen_check(r, ["id5000"]) == {"id5000": True}


def test_scaffold_invalid_scope(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    with pytest.raises(ValueError):
        rt.scaffold("ok-name", os_root, scope="nowhere", home=home)


def test_scaffold_template_file_and_fallback(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    tpl = os_root / "routines" / "_template-routine.md"
    tpl.write_text('---\nname: "{name}"\n---\ncustom body {name}', encoding="utf-8")
    rep = rt.scaffold("plain", os_root, scope="project", home=home)
    assert "custom body plain" in Path(rep["dossier"]).read_text(encoding="utf-8")
    tpl.write_text("no placeholder here", encoding="utf-8")
    rep2 = rt.scaffold("plain2", os_root, scope="project", home=home)
    assert "[CONTEXT]" in Path(rep2["dossier"]).read_text(encoding="utf-8")
