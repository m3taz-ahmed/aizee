"""Tests for runtime/plan_builder.py — fluent DSL emitting valid call-plan JSON."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.call_plan import plan_hash, run_plan, validate_plan
from runtime.plan_builder import Plan, plan
from runtime.schemas import ValidationError


def _tools() -> dict:
    return {
        "echo": lambda **kw: kw,
        "add": lambda a, b: a + b,
        "upper": lambda s: str(s).upper(),
    }


def test_chain_builds_valid_plan() -> None:
    doc = (
        Plan()
        .let_("x", 1)
        .call("add", {"a": "$x", "b": 2}, save="y")
        .return_("$y")
        .build()
    )
    assert doc["version"] == "2.1"
    assert len(doc["steps"]) == 3
    assert validate_plan(doc).ok


def test_builder_plan_runs() -> None:
    doc = plan().call("add", {"a": 2, "b": 3}, save="s").return_("$s").build()
    result = run_plan(doc, _tools())
    assert result.status == "completed"
    assert result.value == 5


def test_fanout_subplan_callable() -> None:
    doc = (
        plan()
        .let_("items", [1, 2])
        .fanout("$items", lambda p: p.call("add", {"a": "$it", "b": 1}, save="r"), as_="it")
        .build()
    )
    fanout = doc["steps"][1]
    assert fanout["op"] == "fanout"
    assert fanout["as"] == "it"
    assert fanout["max"] > 0  # bounded by construction
    assert fanout["do"][0]["tool"] == "add"
    assert validate_plan(doc).ok


def test_fanout_subplan_instance() -> None:
    inner = Plan().call("echo", {"v": "$it"}, save="r")
    doc = plan().let_("xs", ["a"]).fanout("$xs", inner, as_="it").build()
    assert doc["steps"][1]["do"][0]["tool"] == "echo"


def test_if_then_else() -> None:
    doc = (
        plan()
        .let_("flag", True)
        .if_("$flag", lambda p: p.call("upper", {"s": "yes"}, save="o"),
             lambda p: p.call("upper", {"s": "no"}, save="o"))
        .build()
    )
    step = doc["steps"][1]
    assert step["op"] == "if" and "then" in step and "else" in step
    assert validate_plan(doc).ok


def test_suspend_emitted() -> None:
    doc = plan().call("echo", {}).suspend("review").build()
    assert doc["steps"][1]["op"] == "suspend"


def test_memo_flag_and_step_memo() -> None:
    doc = plan(memo=True).call("echo", {"a": 1}).call("echo", {"a": 2}, memo=False).build()
    assert doc["memo"] is True
    assert doc["steps"][1]["memo"] is False


def test_strict_build_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        plan().call("ok", {}).step({"op": "bogus"}).build(strict=True)
    # strict=False lets the caller inspect raw output
    doc = plan().step({"op": "bogus"}).build(strict=False)
    assert doc["steps"][0]["op"] == "bogus"


def test_to_json_and_hash(tmp_path: Path) -> None:
    p = plan().call("echo", {"a": 1})
    out = p.to_json(tmp_path / "p.json")
    doc = p.build()
    assert p.hash() == plan_hash(doc)
    assert out.exists()


def test_let_expression_string() -> None:
    doc = plan().let_("x", 1).let_("n", "$x + 1").build()
    assert doc["steps"][1] == {"op": "let", "name": "n", "expr": "$x + 1"}


def test_fanout_save_and_list_subplan() -> None:
    doc = (
        plan()
        .fanout(
            [1, 2],
            [{"op": "call", "tool": "echo", "args": {"x": "$item"}}],
            as_="item",
            save="res",
        )
        .build()
    )
    step = doc["steps"][0]
    assert step["save"] == "res"
    assert step["do"][0]["op"] == "call"


def test_fanout_callable_returning_other_plan() -> None:
    """A sub-plan callable may return a different Plan instance."""

    def _body(inner: Plan) -> Plan:
        other = Plan()
        return other.call("echo", {"x": 1})

    doc = plan().fanout([1], _body).build()
    assert doc["steps"][0]["do"][0]["tool"] == "echo"


def test_steps_len_and_build_flags() -> None:
    p = plan(budget={"tokens": 10}, memo=True).call("echo", {})
    assert len(p) == 1
    assert p.steps[0]["op"] == "call"
    doc = p.build()
    assert doc["budget"] == {"tokens": 10}
    assert doc["memo"] is True


def test_if_without_else_and_invalid_subplan() -> None:
    doc = plan().let_("x", 1).if_("$x", [{"op": "call", "tool": "echo", "args": {}}]).build()
    assert "else" not in doc["steps"][1]
    with pytest.raises(ValidationError):
        plan().fanout([1], 42)  # not a Plan / callable / list
