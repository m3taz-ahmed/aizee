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


# --- scheduling (openclaw-style declarative schedules) ---------------------


def test_parse_schedule_variants() -> None:
    assert rt.parse_schedule("manual") == ("manual", "")
    assert rt.parse_schedule("every:30m") == ("every", "1800")
    assert rt.parse_schedule("every 2h") == ("every", "7200")
    assert rt.parse_schedule("every:1w") == ("every", "604800")
    assert rt.parse_schedule("cron:0 9 * * *") == ("cron", "0 9 * * *")
    assert rt.parse_schedule("at:2026-12-01T09:00") == ("at", "2026-12-01T09:00")
    assert rt.parse_schedule("bogus") == ("manual", "")
    assert rt.parse_schedule("") == ("manual", "")


def test_cron_next_daily() -> None:
    from datetime import datetime, timezone

    after = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)  # Saturday 08:00
    nxt = rt._cron_next("0 9 * * *", after)
    assert nxt == datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
    # Same day already past -> tomorrow
    after2 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    assert rt._cron_next("0 9 * * *", after2) == datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)


def test_cron_next_weekday_and_dow() -> None:
    from datetime import datetime, timezone

    # Saturday -> next Monday 09:00 for 1-5
    sat = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    nxt = rt._cron_next("0 9 * * 1-5", sat)
    assert nxt == datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)  # Monday
    # cron DOW 0 = Sunday
    assert rt._cron_next("0 9 * * 0", sat) == datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
    # cron DOW 7 = Sunday too
    assert rt._cron_next("0 9 * * 7", sat) == datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)


def test_cron_next_or_semantics() -> None:
    from datetime import datetime, timezone

    # DOM and DOW both restricted -> OR: day 15 OR Monday
    sat = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)  # Sat Nov 14
    nxt = rt._cron_next("0 9 15 * 1", sat)
    assert nxt == datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)  # Sunday=DOM15 wins


def test_cron_next_step_and_bad() -> None:
    from datetime import datetime, timezone

    after = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    assert rt._cron_next("*/15 * * * *", after) == datetime(2026, 11, 14, 8, 15, tzinfo=timezone.utc)
    assert rt._cron_next("0 9", after) is None
    assert rt._cron_next("99 9 * * *", after) is None


def test_due_every_and_manual(roots: tuple[Path, Path]) -> None:
    os_root, _ = roots
    manual = _dossier(os_root / "refs" / "routines", "m1", extra="schedule: manual\n")
    r = rt._load_routine(manual, "project", os_root)
    assert r is not None
    assert rt.due(r)["due"] is False
    ev = _dossier(os_root / "refs" / "routines", "e1", extra="schedule: every:1m\n")
    r2 = rt._load_routine(ev, "project", os_root)
    assert r2 is not None
    # deterministic: last_run far in the past -> interval elapsed -> due
    rt.save_state(r2, {**rt._empty_state(r2.name), "last_run": "2020-01-01T00:00:00+00:00"})
    assert rt.due(r2)["due"] is True


def test_due_at_one_shot(roots: tuple[Path, Path]) -> None:
    os_root, _ = roots
    past = _dossier(os_root / "refs" / "routines", "a1", extra="schedule: at:2020-01-01T00:00\n")
    r = rt._load_routine(past, "project", os_root)
    assert r is not None
    assert rt.due(r)["due"] is True
    # after a completed run the one-shot schedule never fires again
    rt.save_state(r, {**rt._empty_state(r.name), "last_run": "2026-11-14T10:00:00+00:00"})
    assert rt.due(r)["due"] is False


def test_due_routines_lists_scheduled(roots: tuple[Path, Path]) -> None:
    os_root, home = roots
    _dossier(os_root / "refs" / "routines", "manual-r", extra="schedule: manual\n")
    _dossier(os_root / "refs" / "routines", "cron-r", extra="schedule: cron:0 0 * * *\n")
    rows = rt.due_routines(os_root, home)
    names = [r["routine"] for r in rows]
    assert "cron-r" in names
    assert "manual-r" not in names


# --- schedule coverage: parser edges + failure paths -----------------------

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402


def test_cron_field_bad_parts() -> None:
    assert rt._cron_field("", 0, 59) is None          # empty
    assert rt._cron_field("1,,2", 0, 59) is None      # empty segment
    assert rt._cron_field("*/x", 0, 59) is None       # non-int step
    assert rt._cron_field("*/0", 0, 59) is None       # zero step
    assert rt._cron_field("a-b", 0, 59) is None       # non-int range
    assert rt._cron_field("x", 0, 59) is None         # non-int single
    assert rt._cron_field("9-2", 0, 59) is None       # reversed range
    assert rt._cron_field("1-59/5", 0, 59) == {1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56}


def test_cron_next_month_skip_and_exhaust() -> None:
    # month-restricted expr skips non-matching days (Nov -> Mar)
    after = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)
    nxt = rt._cron_next("0 9 * 3 *", after)
    assert nxt is not None and nxt.month == 3 and nxt.hour == 9
    # Feb 30 can never fire -> lookahead exhausted -> None
    assert rt._cron_next("0 9 30 2 *", after) is None
    # bad field anywhere -> None
    assert rt._cron_next("0 9 * * x", after) is None


def test_parse_iso_and_anchor_edges(roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    os_root, _ = roots
    assert rt._parse_iso("not-a-date") is None
    assert rt._parse_iso(123) is None
    assert rt._parse_iso(None) is None
    # naive ISO gains UTC tzinfo
    assert rt._parse_iso("2026-11-14T09:00").tzinfo == timezone.utc
    # _anchor_dt falls back to now() when the dossier can't be stat'ed
    ghost = rt.Routine(
        name="g", scope="project", path=os_root / "missing.md",
        description="", triggers=(), schedule="every:1h",
        state_path=os_root / "g" / "state.json",
    )
    anchor = rt._anchor_dt(ghost, rt._empty_state("g"))
    assert anchor.tzinfo is not None


def test_next_fire_manual_and_unknown_kind(
    roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    os_root, _ = roots
    f = _dossier(os_root / "refs" / "routines", "nf", extra="schedule: manual\n")
    r = rt._load_routine(f, "project", os_root)
    assert r is not None
    assert rt.next_fire(r) is None
    # defensive tail: an unmapped schedule kind yields no fire
    monkeypatch.setattr(rt, "parse_schedule", lambda raw: ("mystery", "x"))
    assert rt.next_fire(r, rt._empty_state(r.name)) is None
