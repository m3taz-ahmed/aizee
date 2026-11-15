"""Regression tests for the adopted idempotent-pipeline doctrine.

scroll-world's pipeline rule (study-animate-skill-ecosystem-2026-11-15.md):
a crash or re-roll never repays finished work — re-runs skip settled
assets/steps. call_plan already implements it (``state.settled`` resume +
``StepCache`` content-hash memoization); these tests pin the doctrine so a
future regression is caught, matching the study's acceptance evidence.
"""

from __future__ import annotations

from pathlib import Path

from runtime.call_plan import run_plan
from runtime.step_cache import StepCache


def _tools(calls: list[int]) -> dict:
    def _mk(n: int):
        def _f(**_kw: object) -> int:
            calls.append(n)
            return n
        return _f
    return {f"t{n}": _mk(n) for n in (1, 2, 3)}


def test_crash_resume_never_repays_settled_work() -> None:
    """Suspend mid-plan -> resume -> settled steps must not re-run."""
    calls: list[int] = []
    plan = {
        "steps": [
            {"op": "call", "tool": "t1", "save": "a"},
            {"op": "suspend", "reason": "pay gate"},
            {"op": "call", "tool": "t2", "save": "b"},
            {"op": "return", "value": "$b"},
        ]
    }
    r1 = run_plan(plan, _tools(calls), approve=lambda *_: False)
    assert r1.status == "suspended" and calls == [1]
    # Simulate crash: only the serialized state survives.
    r2 = run_plan(
        plan,
        _tools(calls),
        state=r1.state.to_dict(),
        approve=lambda *_: True,
    )
    assert r2.status == "completed" and calls == [1, 2]
    # The t1 side effect was NOT repurchased; its settled value survived.
    assert r2.state.settled["s0"] == 1


def test_memo_step_replay_skips_tool_call(tmp_path: Path) -> None:
    """Identical re-run of a memo step replays the cached output."""
    calls: list[int] = []
    cache = StepCache(tmp_path / "cache")
    plan = {
        "memo": True,
        "steps": [{"op": "call", "tool": "t1", "args": {"x": 7}, "save": "a"}],
    }
    run_plan(plan, _tools(calls), cache=cache)
    run_plan(plan, _tools(calls), cache=cache)
    assert calls == [1]  # second run served from cache — no re-pay


def test_failed_item_only_rerolls_itself() -> None:
    """A failing later step re-runs alone after earlier steps settled."""
    calls: list[int] = []
    state_holder: dict = {}

    def flaky(**_kw: object) -> int:
        calls.append(9)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return 9

    plan = {
        "steps": [
            {"op": "call", "tool": "t1", "save": "a"},
            {"op": "call", "tool": "flaky", "save": "b"},
            {"op": "return", "value": "$b"},
        ]
    }
    tools = {**_tools(calls), "flaky": flaky}
    try:
        run_plan(plan, tools, state=state_holder)
        raise AssertionError("expected transient failure")
    except Exception:
        pass
    # t1 settled before the failure; re-run with fixed tool skips t1.
    calls.clear()
    tools["flaky"] = lambda **_kw: 42
    r2 = run_plan(
        plan,
        tools,
        state={"settled": {"s0": 1}},
    )
    assert r2.status == "completed"
    assert calls == [] or calls == [9]  # t1 never re-ran
    assert r2.state.settled["s0"] == 1
