"""Fluent plan builder DSL (SVG.js chainability + Theatre.js sequencing).

``call_plan`` consumes inert JSON — safe but awkward to author by hand.
``Plan`` wraps it in a chainable builder (SVG.js ``SVG().rect().move()``
style): every call appends a step and returns ``self`` so plans read as
linear scripts while still producing the *same* validated, hashable,
resumable JSON document.

Usage::

    plan = (
        Plan(version="2.1")
        .let_("start", 1)
        .call("fs.read", {"path": "a.txt"}, save="doc")
        .fanout("$doc.lines", [{"op": "call", "tool": "llm.summarize",
                                "args": {"text": "$item"}}], as_="item")
        .suspend("review before write")
        .return_("$doc")
    )
    doc = plan.build()          # -> validated plan dict
    plan.to_json("plan.json")   # -> file for `aizee plan run`

``build()`` runs the same ``validate_plan`` the CLI gate uses, so a
builder-produced plan can never be less safe than a hand-written one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.call_plan import MAX_FANOUT, MAX_STEPS, PlanIssue, plan_hash, validate_plan
from runtime.schemas import ValidationError

_PLAN_VERSION = "2.1"

Steps = list[dict[str, Any]]
# Sub-plan block: a Plan, a callable(Plan)->Plan, or a raw step list.
SubPlan = Any


class Plan:
    """Chainable builder that emits validated call-plan JSON."""

    def __init__(
        self,
        *,
        version: str = _PLAN_VERSION,
        budget: dict[str, int] | None = None,
        memo: bool = False,
    ) -> None:
        self._version = version
        self._budget = dict(budget) if budget else {}
        self._memo = memo  # plan-level memoization default
        self._steps: Steps = []

    # -- steps ------------------------------------------------------------

    def let_(self, name: str, expr: Any) -> Plan:
        """Bind a variable: literal or a ``$``-prefixed expression."""
        return self._push({"op": "let", "name": name, "expr": expr})

    def call(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        save: str | None = None,
        memo: bool | None = None,
    ) -> Plan:
        """Invoke a mounted tool; ``save`` binds the result to a var."""
        step: dict[str, Any] = {"op": "call", "tool": tool, "args": dict(args or {})}
        if save:
            step["save"] = save
        if memo is not None:
            step["memo"] = memo
        return self._push(step)

    def fanout(
        self,
        over: str | list[Any],
        do: SubPlan,
        *,
        as_: str = "item",
        save: str | None = None,
        max_items: int = MAX_FANOUT,
    ) -> Plan:
        """Map ``do`` over items from ``over``; ``max`` is always bounded."""
        step: dict[str, Any] = {
            "op": "fanout",
            "over": over,
            "as": as_,
            "max": max_items,
            "do": self._sub(do),
        }
        if save:
            step["save"] = save
        return self._push(step)

    def if_(self, cond: str, then: SubPlan, else_: SubPlan | None = None) -> Plan:
        """Conditional branch over sub-step blocks."""
        step: dict[str, Any] = {"op": "if", "cond": cond, "then": self._sub(then)}
        if else_ is not None:
            step["else"] = self._sub(else_)
        return self._push(step)

    def suspend(self, reason: str = "approval required") -> Plan:
        """Human-checkpoint gate — resume via `aizee plan resume`."""
        return self._push({"op": "suspend", "reason": reason})

    def return_(self, value: Any) -> Plan:
        """Plan exit value: literal or ``$``-prefixed expression."""
        return self._push({"op": "return", "value": value})

    def step(self, raw: dict[str, Any]) -> Plan:
        """Escape hatch: append a raw step dict (still validated)."""
        return self._push(dict(raw))

    # -- assembly ---------------------------------------------------------

    def _push(self, step: dict[str, Any]) -> Plan:
        self._steps.append(step)
        return self

    def _sub(self, block: SubPlan) -> Steps:
        """Accept Plan / callable(Plan)->Plan / raw step list."""
        if isinstance(block, Plan):
            return [dict(s) for s in block._steps]
        if callable(block):
            inner = Plan()
            result = block(inner)
            if isinstance(result, Plan) and result is not inner:
                inner = result
            return [dict(s) for s in inner._steps]
        if isinstance(block, list):
            return [dict(s) for s in block]
        raise ValidationError(
            "sub-plan must be a Plan, callable, or list[dict]",
            context={"got": type(block).__name__},
        )

    @property
    def steps(self) -> Steps:
        return list(self._steps)

    # -- output -----------------------------------------------------------

    def build(self, *, strict: bool = True) -> dict[str, Any]:
        """Emit the plan dict; ``strict`` runs ``validate_plan`` first."""
        doc: dict[str, Any] = {"version": self._version, "steps": [dict(s) for s in self._steps]}
        if self._budget:
            doc["budget"] = dict(self._budget)
        if self._memo:
            doc["memo"] = True
        if strict:
            report = validate_plan(doc)
            if report.issues:
                raise ValidationError(
                    "plan failed validation",
                    context={"issues": [_issue_dict(i) for i in report.issues]},
                )
        return doc

    def to_json(self, path: Path | str, *, strict: bool = True) -> Path:
        """Write the validated plan to ``path``; returns the path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = self.build(strict=strict)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out

    def hash(self) -> str:
        """Content hash of the emitted plan — cite in approvals."""
        return plan_hash(self.build())

    def __len__(self) -> int:
        return len(self._steps)


def _issue_dict(issue: PlanIssue) -> dict[str, Any]:
    return {"code": issue.code, "message": issue.message, "step": issue.step}


def plan(
    *,
    version: str = _PLAN_VERSION,
    budget: dict[str, int] | None = None,
    memo: bool = False,
) -> Plan:
    """Factory — mirrors the ``svg.js`` lowercase entry-point convention."""
    return Plan(version=version, budget=budget, memo=memo)


__all__ = [
    "MAX_FANOUT",
    "MAX_STEPS",
    "Plan",
    "plan",
]
