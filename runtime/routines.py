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
from datetime import datetime, timezone
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
