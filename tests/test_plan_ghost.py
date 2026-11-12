"""Tests for runtime/plan_ghost.py — onion-skin preview."""

from __future__ import annotations

from pathlib import Path

from runtime.call_plan import PlanState
from runtime.plan_ghost import ghost_plan, render_ghost
from runtime.step_cache import StepCache


def _plan() -> dict:
    return {
        "version": "2.1",
        "steps": [
            {"op": "let", "name": "x", "expr": 1},
            {"op": "call", "tool": "echo", "args": {"a": "$x"}, "save": "e"},
            {"op": "call", "tool": "echo", "args": {"a": "lit"}, "save": "f", "memo": True},
            {"op": "fanout", "name": "i", "over": "$x", "do": [
                {"op": "call", "tool": "echo", "args": {"v": "$i"}},
            ]},
            {"op": "if", "cond": "$x > 0", "then": [{"op": "return", "value": "$e"}]},
            {"op": "suspend", "reason": "check"},
        ],
    }


def test_dispositions() -> None:
    ghost = ghost_plan(_plan())
    rows = ghost["steps"]
    assert rows[0]["disp"] == "pure"
    assert rows[1]["disp"] == "pending"
    assert rows[1]["args"]["a"] == {"ref": "$x", "bound": False}
    assert rows[2]["disp"] == "pending"  # no cache yet
    assert rows[3]["disp"] == "branch"
    assert rows[3]["do"][0]["op"] == "call"
    assert rows[4]["disp"] == "branch"
    assert rows[4]["then"][0]["disp"] == "pure"
    assert rows[5]["disp"] == "gated"
    assert ghost["counts"]["pending"] >= 2


def test_settled_steps_marked_done() -> None:
    state = PlanState(vars={"x": 1}, settled={"s0": True, "s1": {"v": 1}})
    ghost = ghost_plan(_plan(), state=state)
    rows = ghost["steps"]
    assert rows[0]["disp"] == "done"
    assert rows[1]["disp"] == "done"
    assert rows[1]["args"]["a"]["bound"] is True


def test_cache_hit_marks_cached(tmp_path: Path) -> None:
    cache = StepCache(tmp_path / "c")
    key = cache.key_for("echo", {"a": "lit"})
    cache.put(key, "warm")
    ghost = ghost_plan(_plan(), cache=cache)
    assert ghost["steps"][2]["disp"] == "cached"
    assert ghost["counts"]["cached"] == 1


def test_dollar_arg_never_claimed_cached(tmp_path: Path) -> None:
    # step s1 has a $x arg -> literal-args key won't match even if cached
    cache = StepCache(tmp_path / "c")
    cache.put(cache.key_for("echo", {}), "x")
    ghost = ghost_plan(_plan(), cache=cache)
    assert ghost["steps"][1]["disp"] == "pending"


def test_render_dope_sheet() -> None:
    text = render_ghost(ghost_plan(_plan()))
    assert "plan ghost" in text
    assert "PENDING" in text
    assert "GATED" in text
    assert "suspend" in text
    assert "[memo]" in text


def test_counts_recursion() -> None:
    ghost = ghost_plan(_plan())
    total = sum(ghost["counts"].values())
    assert total >= 8  # 6 top + fanout child + if child


def test_ghost_accepts_dict_state() -> None:
    st = PlanState()
    st.vars["x"] = 7
    ghost = ghost_plan(
        {"version": "2.1", "steps": [{"op": "return", "value": "$x"}]},
        state=st.to_dict(),
    )
    assert ghost["steps"][0]["value"] == "$x"


def test_ghost_skips_non_dict_steps() -> None:
    ghost = ghost_plan({"version": "2.1", "steps": ["junk", {"op": "return", "value": 1}]})
    assert len(ghost["steps"]) == 1


def test_ghost_fanout_and_if_and_return_ops() -> None:
    st = PlanState()
    st.vars["xs"] = [1, 2, 3]
    ghost = ghost_plan(
        {
            "version": "2.1",
            "steps": [
                {"op": "fanout", "over": "$xs", "as": "x", "do": [{"op": "call", "tool": "t"}]},
                {"op": "fanout", "over": [1, 2], "as": "x", "do": [{"op": "call", "tool": "t"}]},
                {"op": "if", "cond": "$x", "then": [{"op": "call", "tool": "t"}]},
                {"op": "suspend", "reason": "r"},
                {"op": "checkpoint", "name": "c1"},   # unlisted op -> falls through elifs
                {"op": "return", "value": "$xs"},
            ],
        },
        state=st,
    )
    rows = ghost["steps"]
    assert rows[0]["count"] == 3   # width from settled var
    assert rows[1]["count"] is None  # non-$ over -> unknown width
    assert rows[2]["cond"] == "$x"
    assert rows[5]["value"] == "$xs"


def test_fanout_size_typeerror_safe() -> None:
    from runtime.plan_ghost import _fanout_size

    class _BadLen(dict):
        def __len__(self) -> int:
            raise TypeError("nope")

    st = PlanState()
    st.vars["xs"] = _BadLen({"a": 1})
    assert _fanout_size({"over": "$xs"}, st) is None


def test_counts_ignores_unknown_dispositions() -> None:
    from runtime.plan_ghost import _counts

    c = _counts([{"disp": "mystery"}, {"disp": "pure", "do": [{"disp": "mystery"}]}])
    assert c["pure"] == 1
    assert "mystery" not in c
