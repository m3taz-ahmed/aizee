"""Recurring routines — named, invocable personal workflows with durable state.

A *routine* is a private dossier (markdown + YAML frontmatter) plus a JSON
state file. It answers the recurring-task problem: context is written once,
then any later session invokes the routine by name or trigger word, reads
where it left off, and writes back before closing.

Three discovery scopes (priority order for name resolution):

- ``project`` — ``<os_root>/refs/routines/`` private, gitignored, OS-bound
- ``user``    — ``~/.aizee/routines/``       private, follows the operator
- ``shipped`` — ``<os_root>/routines/``      public templates/examples

State schema ``aizee.routine-state.v1`` lives next to the dossier::

    {
      "schema": "aizee.routine-state.v1",
      "routine": "job-hunt",
      "last_run": "2026-11-13T09:00:00+00:00",
      "in_progress": {"run_id": "job-hunt_2026-11-13", "started": "..."},
      "runs": [{"run_id", "finished", "summary", "artifact"}],
      "seen": ["<item-id>", ...],
      "notes": "free text"
    }
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "aizee.routine-state.v1"
SCOPE_PROJECT = "project"
SCOPE_USER = "user"
SCOPE_SHIPPED = "shipped"
SCOPE_ORDER = (SCOPE_PROJECT, SCOPE_USER, SCOPE_SHIPPED)

_SEEN_CAP = 5000
_RUNS_CAP = 50
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class Routine:
    """A discovered routine dossier."""

    name: str
    scope: str
    path: Path
    description: str = ""
    triggers: tuple[str, ...] = ()
    schedule: str = "manual"
    state_path: Path = Path()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "path": str(self.path),
            "description": self.description,
            "triggers": list(self.triggers),
            "schedule": self.schedule,
            "state": str(self.state_path),
        }


@dataclass(frozen=True)
class RoutineMatch:
    """A scored routine match for a free-text query."""

    routine: Routine
    score: float
    matched: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {**self.routine.to_dict(), "score": self.score, "matched": list(self.matched)}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _routine_dirs(os_root: Path, home: Path | None = None) -> list[tuple[Path, str]]:
    home = home or Path.home()
    return [
        (os_root / "refs" / "routines", SCOPE_PROJECT),
        (home / ".aizee" / "routines", SCOPE_USER),
        (os_root / "routines", SCOPE_SHIPPED),
    ]


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _default_state_path(scope: str, dossier: Path, os_root: Path, name: str) -> Path:
    if scope == SCOPE_SHIPPED:
        return os_root / "state" / "routines" / f"{name}.state.json"
    return dossier.parent / name / "state.json"


def _load_routine(md_file: Path, scope: str, os_root: Path) -> Routine | None:
    """Parse one dossier file. Returns None on unreadable/invalid files."""
    try:
        text = md_file.read_text(encoding="utf-8")
    except OSError:
        return None
    meta = _parse_frontmatter(text)
    name = str(meta.get("name") or md_file.stem)
    if name.startswith("_") or not _NAME_RE.match(name):
        return None
    triggers = meta.get("triggers")
    trig_tuple = tuple(str(t) for t in triggers) if isinstance(triggers, list) else ()
    override = meta.get("state")
    state_path = (
        Path(str(override)).expanduser()
        if override
        else _default_state_path(scope, md_file, os_root, name)
    )
    if not state_path.is_absolute():
        state_path = (md_file.parent / state_path).resolve()
    return Routine(
        name=name,
        scope=scope,
        path=md_file,
        description=str(meta.get("description") or ""),
        triggers=trig_tuple,
        schedule=str(meta.get("schedule") or "manual"),
        state_path=state_path,
    )


def discover(os_root: Path, home: Path | None = None) -> list[Routine]:
    """Find all routines across the three scopes, deduped by name."""
    found: dict[str, Routine] = {}
    for directory, scope in _routine_dirs(os_root, home):
        if not directory.is_dir():
            continue
        for md_file in sorted(directory.glob("*.md")):
            if md_file.name in ("README.md",) or md_file.stem.startswith("_"):
                continue
            routine = _load_routine(md_file, scope, os_root)
            if routine is not None and routine.name not in found:
                found[routine.name] = routine
    return list(found.values())


# ---------------------------------------------------------------------------
# Matching — substring-based so Arabic triggers work (no latin tokeniser)
# ---------------------------------------------------------------------------


def match_routines(query: str, routines: list[Routine], limit: int = 5) -> list[RoutineMatch]:
    """Rank routines for a free-text query. Name hits dominate trigger hits."""
    q = query.lower().strip()
    if not q:
        return []
    results: list[RoutineMatch] = []
    for r in routines:
        score, matched = _score_routine(r, q)
        if score > 0:
            results.append(RoutineMatch(routine=r, score=score, matched=tuple(matched)))
    results.sort(key=lambda m: (-m.score, m.routine.name))
    return results[:limit]


def _score_routine(r: Routine, q: str) -> tuple[float, list[str]]:
    matched: list[str] = []
    score = 0.0
    name = r.name.lower()
    if q == name:
        return 100.0, [r.name]
    if name in q:
        score += 60.0
        matched.append(r.name)
    for trig in r.triggers:
        t = trig.lower().strip()
        if t and t in q:
            score += 20.0
            matched.append(trig)
    for token in re.split(r"[-_\s]+", name):
        if len(token) >= 3 and token in q and token not in matched:
            score += 5.0
            matched.append(token)
    return score, matched


def resolve(os_root: Path, name_or_query: str, home: Path | None = None) -> Routine | None:
    """Resolve a routine by exact ``name`` or ``scope:name``, else top match."""
    scope_prefix, _, bare = name_or_query.partition(":")
    scoped = scope_prefix in SCOPE_ORDER
    wanted = bare if scoped else name_or_query
    routines = discover(os_root, home)
    for r in routines:
        if r.name == wanted.strip() and (not scoped or r.scope == scope_prefix):
            return r
    if scoped:
        return None  # explicit scope prefix — never fuzzy-match across scopes
    matches = match_routines(name_or_query, routines, limit=1)
    if matches and matches[0].score >= 20.0:
        return matches[0].routine
    return None


# ---------------------------------------------------------------------------
# State — atomic JSON writes, schema-versioned
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Scheduling — declarative `schedule:` frontmatter (openclaw/agent-compose
# model: manual | every:<n><unit> | cron:<5-field> | at:<ISO>)
# ---------------------------------------------------------------------------

_INTERVAL_RE = re.compile(r"^every\s*:?\s*(\d+)\s*([smhdw])$", re.IGNORECASE)
_INTERVAL_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
_CRON_LOOKAHEAD_DAYS = 400


def _cron_field(spec: str, lo: int, hi: int) -> set[int] | None:
    """Parse one cron field into an allowed-value set; None on bad syntax."""
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            return None
        step = 1
        if "/" in part:
            part, _, step_s = part.partition("/")
            try:
                step = int(step_s)
            except ValueError:
                return None
            if step < 1:
                return None
        if part in ("*", ""):
            lo_v, hi_v = lo, hi
        elif "-" in part:
            a, _, b = part.partition("-")
            try:
                lo_v, hi_v = int(a), int(b)
            except ValueError:
                return None
        else:
            try:
                lo_v = hi_v = int(part)
            except ValueError:
                return None
        if lo_v < lo or hi_v > hi or lo_v > hi_v:
            return None
        values.update(range(lo_v, hi_v + 1, step))
    return values


def _cron_next(expr: str, after: datetime) -> datetime | None:
    """Next fire instant strictly after `after` for a 5-field cron expr.

    Standard cron semantics: DOW 0/7 = Sunday (mapped to python weekday 6);
    when DOM and DOW are both restricted the day matches on EITHER field.
    """
    fields = expr.split()
    if len(fields) != 5:
        return None
    sets = [_cron_field(f, lo, hi) for f, (lo, hi) in zip(fields, _CRON_RANGES, strict=True)]
    if any(s is None for s in sets):
        return None
    minute_s, hour_s, dom_s, month_s, dow_s = sets
    assert minute_s is not None and hour_s is not None and dom_s is not None
    assert month_s is not None and dow_s is not None
    # cron DOW 0..7 (0 and 7 = Sunday) -> python weekday (Mon=0 .. Sun=6)
    weekdays = {((d - 1) % 7) for d in dow_s}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    start = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(_CRON_LOOKAHEAD_DAYS):
        if start.month in month_s:
            if dom_restricted and dow_restricted:
                day_ok = start.day in dom_s or start.weekday() in weekdays
            else:
                day_ok = start.day in dom_s and start.weekday() in weekdays
            if day_ok:
                for hour in sorted(hour_s):
                    for minute in sorted(minute_s):
                        candidate = start.replace(hour=hour, minute=minute)
                        if candidate >= start:
                            return candidate
        start = (start + timedelta(days=1)).replace(hour=0, minute=0)
    return None


def parse_schedule(raw: str) -> tuple[str, str]:
    """Normalize a schedule string -> (kind, value).

    Kinds: ``manual`` | ``every`` (value=seconds str) | ``cron`` (expr) |
    ``at`` (ISO datetime). Unknown/empty -> ``manual``.
    """
    raw = (raw or "manual").strip()
    m = _INTERVAL_RE.match(raw)
    if m:
        seconds = int(m.group(1)) * _INTERVAL_SECONDS[m.group(2).lower()]
        return ("every", str(seconds))
    if raw.lower().startswith("cron:"):
        return ("cron", raw[5:].strip())
    if raw.lower().startswith("at:"):
        return ("at", raw[3:].strip())
    return ("manual", "")


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _anchor_dt(routine: Routine, state: dict[str, Any]) -> datetime:
    """Anchor for next-fire computation: last_run, else dossier mtime."""
    dt = _parse_iso(state.get("last_run"))
    if dt is not None:
        return dt
    try:
        return datetime.fromtimestamp(routine.path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)


def next_fire(routine: Routine, state: dict[str, Any] | None = None) -> datetime | None:
    """Next scheduled fire instant after the anchor (last_run/mtime)."""
    kind, value = parse_schedule(routine.schedule)
    if kind == "manual":
        return None
    state = load_state(routine) if state is None else state
    anchor = _anchor_dt(routine, state)
    if kind == "every":
        return anchor + timedelta(seconds=int(value))
    if kind == "at":
        # One-shot: fires at the absolute instant unless last_run already
        # covered it (anchor for `at` is last_run, never file mtime).
        fire = _parse_iso(value)
        last = _parse_iso(state.get("last_run"))
        return fire if fire is not None and (last is None or fire > last) else None
    if kind == "cron":
        return _cron_next(value, anchor)
    return None  # unreachable — parse_schedule maps to the four kinds


def due(routine: Routine, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Is this routine's schedule past its fire instant?

    OpenClaw model: schedules are declarative; a scheduler (or the user via
    ``aizee routine due``) checks whether a fire instant elapsed since the
    last completed run. One-shot ``at:`` schedules are never due twice.
    """
    state = load_state(routine) if state is None else state
    kind, _ = parse_schedule(routine.schedule)
    if kind == "manual":
        return {"routine": routine.name, "schedule": "manual", "due": False, "next_fire": None}
    fire = next_fire(routine, state)
    now = datetime.now(timezone.utc)
    is_due = fire is not None and fire <= now
    return {
        "routine": routine.name,
        "schedule": routine.schedule,
        "due": is_due,
        "next_fire": fire.isoformat(timespec="seconds") if fire else None,
        "last_run": state.get("last_run"),
    }


def due_routines(os_root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    """All scheduled routines with due status, soonest next_fire first."""
    rows = []
    for routine in discover(os_root, home):
        kind, _ = parse_schedule(routine.schedule)
        if kind == "manual":
            continue
        state = load_state(routine)
        rows.append({**due(routine, state), "scope": routine.scope})
    rows.sort(key=lambda r: (not r["due"], r["next_fire"] or "9999"))
    return rows


def run_id(name: str, when: datetime | None = None) -> str:
    day = (when or datetime.now(timezone.utc)).date().isoformat()
    return f"{name}_{day}"


def _empty_state(name: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "routine": name,
        "last_run": None,
        "in_progress": None,
        "runs": [],
        "seen": [],
        "notes": "",
    }


def load_state(routine: Routine) -> dict[str, Any]:
    """Read the routine state file; return a fresh state when missing/corrupt."""
    try:
        data = json.loads(routine.state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state(routine.name)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return _empty_state(routine.name)
    for key, default in _empty_state(routine.name).items():
        data.setdefault(key, default)
    return data


def save_state(routine: Routine, state: dict[str, Any]) -> None:
    """Atomically persist state (temp file + os.replace)."""
    routine.state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(routine.state_path.parent), suffix=".tmp", prefix=".state-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, routine.state_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def status(routine: Routine) -> dict[str, Any]:
    """Compact status view for CLI/agents."""
    state = load_state(routine)
    rid = run_id(routine.name)
    return {
        **routine.to_dict(),
        "last_run": state["last_run"],
        "in_progress": state["in_progress"],
        "ran_today": any(r.get("run_id") == rid for r in state["runs"]),
        "runs": len(state["runs"]),
        "seen": len(state["seen"]),
        "today_run_id": rid,
    }


def begin(routine: Routine, force: bool = False) -> dict[str, Any]:
    """Claim today's run (claim-before-start). Refuses duplicates without force.

    Blocks on a finished today's run *and* on a live ``in_progress`` claim —
    resuming a crashed run needs ``force`` (the claim is re-stamped).
    """
    state = load_state(routine)
    rid = run_id(routine.name)
    finished = any(r.get("run_id") == rid for r in state["runs"])
    in_prog = (state.get("in_progress") or {}).get("run_id") == rid
    if (finished or in_prog) and not force:
        return {
            "run_id": rid,
            "already_ran": True,
            "in_progress": in_prog and not finished,
            "state": state,
            "routine": routine.to_dict(),
        }
    state["in_progress"] = {"run_id": rid, "started": _now(), "forced": force and (finished or in_prog)}
    save_state(routine, state)
    return {
        "run_id": rid,
        "already_ran": False,
        "resumed": bool(finished),
        "state": state,
        "routine": routine.to_dict(),
    }


def complete(
    routine: Routine, summary: str, artifact: str = "", notes: str | None = None
) -> dict[str, Any]:
    """Finalize the in-progress run: append run record, update last_run."""
    state = load_state(routine)
    rid = (state.get("in_progress") or {}).get("run_id") or run_id(routine.name)
    state["runs"] = [r for r in state["runs"] if r.get("run_id") != rid]
    state["runs"].append(
        {
            "run_id": rid,
            "finished": _now(),
            "summary": summary.strip(),
            "artifact": artifact,
        }
    )
    state["runs"] = state["runs"][-_RUNS_CAP:]
    state["last_run"] = _now()
    state["in_progress"] = None
    if notes is not None:
        state["notes"] = notes
    save_state(routine, state)
    return {"run_id": rid, "last_run": state["last_run"], "runs": len(state["runs"])}


def seen_check(routine: Routine, ids: list[str]) -> dict[str, bool]:
    """Report which item ids were already recorded."""
    known = set(load_state(routine)["seen"])
    return {i: (i in known) for i in ids}


def seen_add(routine: Routine, ids: list[str]) -> dict[str, Any]:
    """Record item ids as seen. Deduped; capped (oldest evicted)."""
    state = load_state(routine)
    seen: list[str] = state["seen"]
    known = set(seen)
    added: list[str] = []
    for i in ids:
        if i not in known:
            known.add(i)
            added.append(i)
    seen.extend(added)
    if len(seen) > _SEEN_CAP:
        seen = seen[-_SEEN_CAP:]
    state["seen"] = seen
    save_state(routine, state)
    return {"added": len(added), "total": len(seen)}


# ---------------------------------------------------------------------------
# Scaffold + catalog integration
# ---------------------------------------------------------------------------

_EMBEDDED_TEMPLATE = """---
name: "{name}"
description: "Recurring routine"
triggers: []
# manual | every:30m|2h|1d|1w | cron:0 9 * * 1-5 | at:2026-12-01T09:00
schedule: manual
---
# Routine: {name}

## [CONTEXT]
<!-- Standing facts the agent needs every run — curated, not collected.
     No credentials, no transcripts. -->

## [PROTOCOL]
1.

## [RULES]
- Never send messages or make purchases without explicit user approval.

## [STATE]
- last_run: never
- next_actions: first run — collect missing context with the user.
"""


def scaffold(
    name: str,
    os_root: Path,
    scope: str = SCOPE_USER,
    home: Path | None = None,
    description: str = "",
    triggers: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new routine dossier + empty state. Refuses overwrites."""
    if not _NAME_RE.match(name):
        raise ValueError(f"invalid routine name {name!r} — use kebab-case [a-z0-9-]")
    if scope not in SCOPE_ORDER:
        raise ValueError(f"invalid scope {scope!r} — one of {SCOPE_ORDER}")
    directory = {s: d for d, s in _routine_dirs(os_root, home)}[scope]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    if path.exists():
        raise ValueError(f"routine already exists: {path}")
    template = _load_template(os_root)
    body = template.replace("{name}", name)
    if description:
        body = body.replace('description: "Recurring routine"', f'description: "{description}"', 1)
    if triggers:
        trig_yaml = "[" + ", ".join(triggers) + "]"
        body = body.replace("triggers: []", f"triggers: {trig_yaml}", 1)
    path.write_text(body, encoding="utf-8")
    routine = _load_routine(path, scope, os_root)
    assert routine is not None  # we just wrote a valid dossier
    save_state(routine, _empty_state(name))
    return {"name": name, "scope": scope, "dossier": str(path), "state": str(routine.state_path)}


def _load_template(os_root: Path) -> str:
    tpl = os_root / "routines" / "_template-routine.md"
    try:
        text = tpl.read_text(encoding="utf-8")
    except OSError:
        return _EMBEDDED_TEMPLATE
    return text if "{name}" in text else _EMBEDDED_TEMPLATE


def to_descriptors(routines: list[Routine]) -> list[Any]:
    """Convert routines to ServiceDescriptors so ``aizee find`` indexes them."""
    from runtime.service_catalog import ServiceDescriptor

    return [
        ServiceDescriptor(
            name=r.name,
            kind="routine",
            triggers=frozenset({t.lower() for t in r.triggers}) | {r.name.replace("-", " ")},
            file_path=str(r.path),
            description=r.description,
        )
        for r in routines
    ]
