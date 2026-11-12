"""Onion-skin ghost view of a plan (Pencil2D adoption).

Pencil2D renders translucent neighboring frames over the current one so
the artist sees past + future without touching the live frame. The same
idea applied to orchestration: **ghost = a read-only overlay showing what
a plan *would* do** — each step annotated with its disposition against
the current world (already settled? memoizable? needs approval?) and a
preview of the arguments it would receive, all without executing.

This powers `aizee plan ghost <file>` and approval prompts: reviewers
see the whole dope sheet, not just the next step.

Usage::

    ghost = ghost_plan(plan, state=resumed_state, cache=step_cache)
    print(render_ghost(ghost))
"""

from __future__ import annotations

from typing import Any

from runtime.call_plan import PlanState
from runtime.step_cache import MISSING, StepCache

# Disposition labels — kept short for the dope-sheet column.
DONE = "done"  # already settled in state (resume skips it)
CACHED = "cached"  # content-hash hit — result would replay, not re-run
PENDING = "pending"  # would execute now
GATED = "gated"  # suspend checkpoint — human approval boundary
PURE = "pure"  # deterministic let/return — no tool execution
BRANCH = "branch"  # conditional / fanout container

_MEMO_OPS = {"call"}
_PURE_OPS = {"let", "return"}
_BRANCH_OPS = {"if", "fanout"}


def ghost_plan(
    plan: dict[str, Any],
    *,
    state: PlanState | dict[str, Any] | None = None,
    cache: StepCache | None = None,
    settle_prefix: str = "",
) -> dict[str, Any]:
    """Annotate every step with its disposition — read-only, no execution."""
    if isinstance(state, dict):
        state = PlanState.from_dict(state)
    state = state or PlanState()
    memo_default = bool(plan.get("memo", False))
    rows = _walk(plan.get("steps", []), state, cache, memo_default, settle_prefix)
    return {
        "version": plan.get("version"),
        "plan_hash": None,  # caller may attach plan_hash(plan)
        "steps": rows,
        "counts": _counts(rows),
        "cache_hits": state.cache_hits,
        "settled": sorted(state.settled),
    }


def _walk(
    steps: list[dict[str, Any]],
    state: PlanState,
    cache: StepCache | None,
    memo_default: bool,
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        key = f"{prefix}s{i}"
        row = _ghost_step(step, key, state, cache, memo_default)
        rows.append(row)
        if step.get("op") == "fanout":
            sub = _walk(step.get("do") or [], state, cache, memo_default, f"{key}/")
            rows[-1]["do"] = sub
            rows[-1]["counts"] = _counts(sub)
        elif step.get("op") == "if":
            for branch in ("then", "else"):
                sub_steps = step.get(branch)
                if sub_steps:
                    rows[-1][branch] = _walk(sub_steps, state, cache, memo_default, f"{key}/{branch[0]}")
    return rows


def _ghost_step(
    step: dict[str, Any],
    key: str,
    state: PlanState,
    cache: StepCache | None,
    memo_default: bool,
) -> dict[str, Any]:
    op = step.get("op")
    row: dict[str, Any] = {
        "key": key,
        "op": op,
        "disp": _disposition(step, key, state, cache, memo_default),
    }
    if op == "call":
        row["tool"] = step.get("tool")
        row["args"] = _preview_args(step.get("args") or {}, state)
        if "save" in step:
            row["save"] = step["save"]
        row["memo"] = bool(step.get("memo", memo_default))
    elif op == "let":
        row["name"] = step.get("name")
        row["expr"] = step.get("expr")
    elif op == "suspend":
        row["reason"] = step.get("reason", "approval required")
    elif op == "fanout":
        row["name"] = step.get("as")
        row["over"] = step.get("over")
        row["count"] = _fanout_size(step, state)
    elif op == "if":
        row["cond"] = step.get("cond")
    elif op == "return":
        row["value"] = step.get("value")
    return row


def _disposition(
    step: dict[str, Any],
    key: str,
    state: PlanState,
    cache: StepCache | None,
    memo_default: bool,
) -> str:
    if key in state.settled:
        return DONE
    op = step.get("op")
    if op == "suspend":
        return GATED
    if op in _PURE_OPS:
        return PURE
    if op in _BRANCH_OPS:
        return BRANCH
    if op in _MEMO_OPS and cache is not None and step.get("memo", memo_default):
        ck = cache.key_for(step.get("tool", ""), _literal_args(step.get("args") or {}))
        if cache.get(ck) is not MISSING:
            return CACHED
    return PENDING


def _literal_args(args: dict[str, Any]) -> dict[str, Any]:
    """Args for cache-key prediction: unresolved ``$`` refs stay symbolic.

    A ``$`` ref keeps the step PENDING rather than claiming a cache hit
    that the resolved value might not match — conservative onion skin.
    """
    return {k: v for k, v in args.items() if not (isinstance(v, str) and v.startswith("$"))}


def _preview_args(args: dict[str, Any], state: PlanState) -> dict[str, Any]:
    """Show literal args; ``$`` refs annotated with current binding if known."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("$"):
            root = v[1:].split(".", 1)[0].split("[", 1)[0]
            out[k] = {"ref": v, "bound": root in state.vars or root == "step"}
        else:
            out[k] = v
    return out


def _fanout_size(step: dict[str, Any], state: PlanState) -> int | None:
    """Best-effort fanout width from settled vars; None when unknown."""
    over = step.get("over")
    if not isinstance(over, str) or not over.startswith("$"):
        return None
    root = over[1:].split(".", 1)[0].split("[", 1)[0]
    value = state.vars.get(root)
    try:
        return len(value) if isinstance(value, (list, tuple, dict)) else None
    except TypeError:
        return None


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    c: dict[str, int] = dict.fromkeys((DONE, CACHED, PENDING, GATED, PURE, BRANCH), 0)
    for row in rows:
        disp = row.get("disp")
        if disp in c:
            c[disp] += 1
        for branch in ("do", "then", "else"):
            sub = row.get(branch)
            if sub:
                for d, n in _counts(sub).items():
                    c[d] += n
    return c


def render_ghost(ghost: dict[str, Any]) -> str:
    """Dope-sheet text render — the onion-skin view for the terminal."""
    lines = ["plan ghost (onion skin):"]
    _render_rows(ghost["steps"], lines, indent=1)
    c = ghost["counts"]
    summary = ", ".join(f"{k}={v}" for k, v in c.items() if v)
    lines.append(f"  ── {summary}")
    return "\n".join(lines)


def _render_rows(rows: list[dict[str, Any]], lines: list[str], indent: int) -> None:
    pad = "  " * indent
    for row in rows:
        disp = row["disp"].upper()
        op = row["op"]
        if op == "call":
            extra = f"{row.get('tool')}{' →' + row['save'] if row.get('save') else ''}"
            if row.get("memo"):
                extra += "  [memo]"
        elif op == "let":
            extra = f"{row.get('name')} = {row.get('expr')}"
        elif op == "suspend":
            extra = f"⏸ {row.get('reason')}"
        elif op == "fanout":
            count = row.get("count")
            extra = f"for {row.get('name')} in {row.get('over')} x{count if count is not None else '?'}"
        elif op == "if":
            extra = f"when {row.get('cond')}"
        else:
            extra = str(row.get("value", ""))
        lines.append(f"{pad}{disp:7} {op:7} {extra}")
        for branch in ("do", "then", "else"):
            sub = row.get(branch)
            if sub:
                lines.append(f"{pad}    ├ {branch}:")
                _render_rows(sub, lines, indent + 3)
