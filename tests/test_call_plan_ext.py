"""Tests for call_plan extensions: memoization, $step/$mem bindings,
prefetch lookahead, and lifecycle event taps."""

from __future__ import annotations

from pathlib import Path

from runtime.call_plan import run_plan, validate_plan
from runtime.step_cache import StepCache


def _tools(calls: list[str] | None = None) -> dict:
    log = calls if calls is not None else []
    return {
        "add": lambda a, b: log.append("add") or a + b,
        "echo": lambda **kw: log.append("echo") or kw,
        "fail": lambda: log.append("fail") or (_ for _ in ()).throw(RuntimeError("x")),
    }


# -- memoization (F2) -------------------------------------------------------


def test_memo_replays_identical_call(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    calls: list[str] = []
    plan = {"version": "2.1", "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 2}, "save": "r"}]}
    r1 = run_plan(plan, _tools(calls), cache=cache, memo_default=True)
    assert r1.status == "completed" and calls == ["add"]
    r2 = run_plan(plan, _tools(calls), cache=cache, memo_default=True)
    assert r2.status == "completed"
    assert calls == ["add"]  # tool NOT re-invoked
    assert r2.state.cache_hits == 1
    assert r2.state.vars["r"] == 3


def test_memo_per_step_opt_out(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    calls: list[str] = []
    plan = {
        "version": "2.1",
        "memo": True,
        "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}, "memo": False}],
    }
    run_plan(plan, _tools(calls), cache=cache)
    run_plan(plan, _tools(calls), cache=cache)
    assert calls == ["add", "add"]  # memo=False bypassed the cache


def test_memo_off_by_default(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    calls: list[str] = []
    plan = {"version": "2.1", "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    run_plan(plan, _tools(calls), cache=cache)  # memo_default False
    run_plan(plan, _tools(calls), cache=cache)
    assert calls == ["add", "add"]


def test_memo_changed_args_miss(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    calls: list[str] = []
    p1 = {"version": "2.1", "memo": True, "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    p2 = {"version": "2.1", "memo": True, "steps": [{"op": "call", "tool": "add", "args": {"a": 9, "b": 1}}]}
    run_plan(p1, _tools(calls), cache=cache)
    run_plan(p2, _tools(calls), cache=cache)
    assert calls == ["add", "add"]  # different args -> miss


# -- value-node bindings (F8) -----------------------------------------------


def test_step_binding_reads_settled() -> None:
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "call", "tool": "add", "args": {"a": 1, "b": 2}, "save": "r"},
            {"op": "call", "tool": "add", "args": {"a": "$step.s0", "b": 10}, "save": "t"},
            {"op": "return", "value": "$t"},
        ],
    }
    result = run_plan(plan, _tools())
    assert result.status == "completed"
    assert result.value == 13  # step.s0 result (3) + 10


def test_mem_binding_lookup() -> None:
    mem = {"threshold": 7}
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "let", "name": "v", "expr": "$mem.threshold + 1"},
            {"op": "return", "value": "$v"},
        ],
    }
    result = run_plan(plan, _tools(), mem=mem.get)
    assert result.value == 8


def test_mem_binding_unattached_errors() -> None:
    plan = {"version": "2.1", "steps": [{"op": "let", "name": "v", "expr": "$mem.x"}]}
    result = run_plan(plan, _tools())
    assert result.status == "failed"
    assert result.error is not None and result.error.code == "UNBOUND_VAR"


def test_binding_roots_validate() -> None:
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "let", "name": "a", "expr": "$step.s0 + $mem.k"},
            {"op": "return", "value": "$a"},
        ],
    }
    report = validate_plan(plan)
    assert report.ok  # $step/$mem roots are bound namespaces


def test_write_stays_on_vars() -> None:
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "let", "name": "x", "expr": 5},
            {"op": "call", "tool": "add", "args": {"a": "$x", "b": "$step.s1" if False else 1}},
            {"op": "return", "value": "$x"},
        ],
    }
    result = run_plan(plan, _tools())
    assert result.status == "completed"
    assert result.state.vars["x"] == 5
    assert "step" not in result.state.vars  # namespaces never leak into vars


# -- prefetch lookahead (F4) -------------------------------------------------


def test_prefetch_receives_upcoming_calls() -> None:
    seen: list[list[dict]] = []
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "call", "tool": "add", "args": {"a": 1, "b": 1}},
            {"op": "call", "tool": "echo", "args": {"x": 1}},
            {"op": "let", "name": "z", "expr": 3},
            {"op": "call", "tool": "echo", "args": {"x": 2}},
        ],
    }
    result = run_plan(plan, _tools(), prefetch=seen.append, lookahead=2)
    assert result.status == "completed"
    suggested = [s for batch in seen for s in batch]
    # s1 suggested while s0 ran; s3 suggested while s1 ran (lets skipped)
    tools = [s.get("tool") for s in suggested]
    assert "echo" in tools
    assert all(s["op"] == "call" for s in suggested)


def test_prefetch_failure_isolated() -> None:
    def _bad(_steps: list[dict]) -> None:
        raise RuntimeError("speculation blew up")

    plan = {"version": "2.1", "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    result = run_plan(plan, _tools(), prefetch=_bad, lookahead=3)
    assert result.status == "completed"  # prefetch never breaks the run


# -- lifecycle events (F1 integration) ---------------------------------------


def test_on_event_emits_step_events() -> None:
    events: list[dict] = []
    plan = {
        "version": "2.1",
        "steps": [
            {"op": "let", "name": "x", "expr": 1},
            {"op": "call", "tool": "add", "args": {"a": 1, "b": 2}},
        ],
    }
    result = run_plan(plan, _tools(), on_event=events.append)
    assert result.status == "completed"
    types = [e["type"] for e in events]
    assert "step.settled" in types
    call_event = next(e for e in events if e.get("tool") == "add")
    assert call_event["op"] == "call"


def test_on_event_failure_isolated() -> None:
    def _bad(_e: dict) -> None:
        raise RuntimeError("tap blew up")

    plan = {"version": "2.1", "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    assert run_plan(plan, _tools(), on_event=_bad).status == "completed"


def test_cache_hit_event(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    events: list[dict] = []
    plan = {"version": "2.1", "memo": True, "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    run_plan(plan, _tools(), cache=cache, on_event=events.append)
    run_plan(plan, _tools(), cache=cache, on_event=events.append)
    assert any(e["type"] == "step.cached" for e in events)


def test_cache_hits_in_state_roundtrip(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    plan = {"version": "2.1", "memo": True, "steps": [{"op": "call", "tool": "add", "args": {"a": 1, "b": 1}}]}
    run_plan(plan, _tools(), cache=cache)
    r2 = run_plan(plan, _tools(), cache=cache)
    blob = r2.state.to_dict()
    assert blob["cache_hits"] == 1
    from runtime.call_plan import PlanState

    assert PlanState.from_dict(blob).cache_hits == 1


def test_step_binding_by_declared_id() -> None:
    """REGRESSION: $step.<id> resolves a step's declared id, not only sN keys."""
    plan = {
        "version": "1.0",
        "steps": [
            {"op": "call", "id": "calc", "tool": "mul", "args": {"a": 3, "b": 4}},
            {"op": "return", "expr": "$step.calc"},
        ],
    }
    result = run_plan(plan, {"mul": lambda a, b: a * b})
    assert result.status == "completed"
    assert result.value == 12


def test_step_binding_still_supports_positional() -> None:
    plan = {
        "version": "1.0",
        "steps": [
            {"op": "call", "tool": "mul", "args": {"a": 2, "b": 5}},
            {"op": "return", "expr": "$step.s0"},
        ],
    }
    assert run_plan(plan, {"mul": lambda a, b: a * b}).value == 10


def test_bare_step_root_rejected() -> None:
    """REGRESSION: bare `$step` returned the resolver view (broke state save)."""
    plan = {"version": "2.1", "steps": [{"op": "let", "name": "x", "expr": "$step"}]}
    r = run_plan(plan, _tools())
    assert r.status == "failed"
    assert r.error is not None and r.error.code == "UNBOUND_VAR"


def test_bare_mem_root_rejected() -> None:
    plan = {"version": "2.1", "steps": [{"op": "let", "name": "x", "expr": "$mem"}]}
    r = run_plan(plan, _tools(), mem=lambda k: "v")
    assert r.status == "failed"
    assert r.error is not None and r.error.code == "UNBOUND_VAR"


def test_func_on_binding_root_rejected() -> None:
    """`keys($step)` used to escape as an uncaught AttributeError."""
    plan = {"version": "2.1", "steps": [{"op": "let", "name": "x", "expr": "keys($step)"}]}
    r = run_plan(plan, _tools())
    assert r.status == "failed"
    assert r.error is not None and r.error.code == "UNBOUND_VAR"


# -- view/env internals ------------------------------------------------------


def test_mem_view_lookup_error_wrapped() -> None:
    import pytest

    from runtime.call_plan import PlanError, _MemView

    view = _MemView(lambda k: (_ for _ in ()).throw(ValueError("db down")))
    with pytest.raises(PlanError) as exc:
        view["key"]
    assert exc.value.code == "PATH_MISS"


def test_mem_view_plan_error_propagates_unchanged() -> None:
    import pytest

    from runtime.call_plan import PlanError, _MemView

    def _raise(k: str) -> None:
        raise PlanError("CUSTOM", "nope")

    with pytest.raises(PlanError) as exc:
        _MemView(_raise)["k"]
    assert exc.value.code == "CUSTOM"


def test_step_view_id_match_and_miss() -> None:
    import pytest

    from runtime.call_plan import _StepView

    view = _StepView({}, [{"id": "build"}])
    with pytest.raises(KeyError):
        view["build"]  # id exists but s0 never settled -> break -> KeyError
    with pytest.raises(KeyError):
        view["ghost"]


def test_bound_env_vars_roots_and_miss() -> None:
    import pytest

    from runtime.call_plan import _BoundEnv

    env = _BoundEnv({"x": 1}, {"step": "view"})
    assert env["x"] == 1
    assert env["step"] == "view"
    assert "x" in env and "step" in env and "zzz" not in env
    with pytest.raises(KeyError):
        env["zzz"]


def test_plan_missing_steps_key_fails_shape() -> None:
    """KeyError escaping _exec_block maps to a SHAPE failure, not a crash."""
    r = run_plan({"version": "2.1"}, _tools())
    assert r.status == "failed"
    assert r.error is not None and r.error.code == "SHAPE"
