"""Tests for runtime/call_plan — inert plan validation, bounds, resume."""

from __future__ import annotations

from runtime.call_plan import (
    PlanError,
    PlanRunner,
    PlanState,
    eval_expr,
    expr_vars,
    plan_hash,
    run_plan,
    validate_plan,
)


def _tools() -> dict:
    return {
        "add": lambda a, b: a + b,
        "fail": lambda: 1 / 0,
        "echo": lambda **kw: kw,
    }


# --- expressions ---------------------------------------------------------


class TestExpr:
    def test_literals(self) -> None:
        assert eval_expr("42", {}) == 42
        assert eval_expr("1.5", {}) == 1.5
        assert eval_expr('"hi"', {}) == "hi"
        assert eval_expr("true", {}) is True
        assert eval_expr("null", {}) is None
        assert eval_expr("[1, 2, 3]", {}) == [1, 2, 3]

    def test_arith_compare_bool(self) -> None:
        assert eval_expr("1 + 2 * 3", {}) == 7
        assert eval_expr("(1 + 2) * 3", {}) == 9
        assert eval_expr("7 % 3", {}) == 1
        assert eval_expr("-4", {}) == -4
        assert eval_expr("1 < 2 and 3 >= 3", {}) is True
        assert eval_expr("not (1 == 2)", {}) is True
        assert eval_expr("2 in [1, 2, 3]", {}) is True
        assert eval_expr("1 != 2 or false", {}) is True

    def test_vars_paths_funcs(self) -> None:
        env = {"x": {"a": [10, 20]}, "items": [{"n": 1}, {"n": 2}]}
        assert eval_expr("$x.a[1]", env) == 20
        assert eval_expr("len($items)", env) == 2
        assert eval_expr("int('5') + float('0.5')", env) == 5.5
        assert eval_expr("sum([1,2]) * max([3,4])", env) == 12
        assert eval_expr("min([5,2]) + abs(-1)", env) == 3
        assert eval_expr("keys({'a': 1})", env) == ["a"]
        assert eval_expr("values({'a': 2})", env) == [2]
        assert eval_expr("sorted([3,1])", env) == [1, 3]
        assert eval_expr("round(1.6) + int('7')", env) == 9
        assert eval_expr("str(7)", env) == "7"
        assert eval_expr("'b' in 'abc'", env) is True

    def test_errors(self) -> None:
        for bad in ("$", "1 +", "foo(", "len(", "[1,", "(1", "1 2", "@", "x ==", "$missing"):
            try:
                eval_expr(bad, {})
            except PlanError as e:
                assert e.code
            else:
                raise AssertionError(f"{bad} should fail")
        try:
            eval_expr("1 / 0", {})
        except PlanError as e:
            assert e.code == "EXPR_DIV0"
        try:
            eval_expr("1 % 0", {})
        except PlanError as e:
            assert e.code == "EXPR_DIV0"
        try:
            eval_expr("'a' < 1", {})
        except PlanError as e:
            assert e.code == "EXPR_TYPE"
        try:
            eval_expr("len(1, 2)", {})
        except PlanError as e:
            assert e.code == "EXPR_CALL"
        try:
            eval_expr("$x.nothere", {"x": {"a": 1}})
        except PlanError as e:
            assert e.code == "PATH_MISS"
        try:
            eval_expr("$x[5]", {"x": [1]})
        except PlanError as e:
            assert e.code == "PATH_MISS"
        try:
            eval_expr("$x.k", {"x": [1]})
        except PlanError as e:
            assert e.code == "PATH_MISS"

    def test_expr_vars(self) -> None:
        assert expr_vars("$a + $b.c[0]") == {"a", "b"}
        assert expr_vars("1") == set()
        assert expr_vars("len($items) and $flag") == {"items", "flag"}

    def test_string_escape(self) -> None:
        assert eval_expr(r'"a\nb"', {}) == "a\nb"
        assert eval_expr("'q'", {}) == "q"

    def test_dict_literals_and_more(self) -> None:
        assert eval_expr("{'a': 1, 'b': 2}", {}) == {"a": 1, "b": 2}
        assert eval_expr("{x: $v}", {"v": 9}) == {"x": 9}
        assert eval_expr("1 <= 1 and 2 >= 1", {}) is True
        assert eval_expr("5 - 8", {}) == -3
        assert eval_expr("6 / 2", {}) == 3
        assert eval_expr("$a..b", {"a": {"b": 7}}) == 7
        assert eval_expr("$a.[0]", {"a": [4]}) == 4
        try:
            eval_expr("{5: 1}", {})
        except PlanError as e:
            assert e.code == "EXPR_SYNTAX"
        try:
            eval_expr("(1 2)", {})
        except PlanError as e:
            assert e.code == "EXPR_SYNTAX"
        try:
            eval_expr("'a' - 1", {})
        except PlanError as e:
            assert e.code == "EXPR_TYPE"
        try:
            eval_expr("1 )", {})
        except PlanError as e:
            assert e.code == "EXPR_SYNTAX"
        # direct _eval on a bad node tag
        from runtime.call_plan import _eval
        try:
            _eval(("zzz",), {})
        except PlanError as e:
            assert e.code == "EXPR_SYNTAX"
        assert _eval(5, {}) == 5  # non-tuple passthrough
        assert eval_expr("3 > 2", {}) is True
        assert expr_vars("{k: $v, j: [$w]}") == {"v", "w"}
        err = PlanError("C", "m", step=2)
        assert err.to_dict() == {"code": "C", "message": "m", "step": 2}


# --- validation -----------------------------------------------------------


class TestValidate:
    def test_valid(self) -> None:
        plan = {"steps": [
            {"op": "let", "name": "x", "expr": "1 + 2"},
            {"op": "call", "tool": "add", "args": {"a": "$x", "b": 1}, "save": "y"},
            {"op": "fanout", "over": "[1, 2]", "as": "i", "max": 5,
             "do": [{"op": "call", "tool": "echo", "args": {"v": "$i"}}], "save": "out"},
            {"op": "if", "cond": "$y > 0", "then": [{"op": "return", "value": "$out"}],
             "else": [{"op": "return", "value": "0"}]},
        ]}
        r = validate_plan(plan, _tools())
        assert r.ok and not r.issues
        assert r.tools_used == ["add", "echo"]
        assert r.plan_hash

    def test_all_issues_at_once(self) -> None:
        plan = {"steps": [
            {"op": "nope"},
            "not a dict",
            {"op": "call", "tool": "ghost", "args": "bad", "save": 5},
            {"op": "call", "tool": 3},
            {"op": "fanout", "over": "$missing", "do": [{"op": "call", "tool": "add", "args": {}}]},
            {"op": "fanout", "over": "[]", "as": "i", "max": 0, "do": [{"op": "suspend"}]},
            {"op": "fanout", "over": "[]", "as": "i", "max": 99999, "do": [{"op": "suspend"}]},
            {"op": "fanout", "over": "[]", "as": "i", "max": "x", "do": [{"op": "suspend"}]},
            {"op": "if", "cond": "$nope"},
            {"op": "if", "cond": "true", "then": []},
            {"op": "if", "cond": "true", "then": [{"op": "suspend"}], "else": "bad"},
            {"op": "let", "name": "", "expr": "$undefined"},
            {"op": "let", "name": 1, "expr": 5},
            {"op": "return", "value": "$gone"},
            {"op": "call", "tool": "add", "args": {"a": "$unbound"}},
            {"op": "suspend"},
        ]}
        r = validate_plan(plan, _tools())
        codes = {i.code for i in r.issues}
        assert not r.ok
        assert {"BAD_OP", "SHAPE", "UNKNOWN_TOOL", "UNBOUNDED",
                "BOUND_FANOUT", "UNBOUND_VAR", "EXPR_TYPE"} <= codes

    def test_bad_shape(self) -> None:
        r = validate_plan({"steps": "no"})
        assert not r.ok and r.issues[0].code == "SHAPE"
        r = validate_plan([])
        assert not r.ok  # type: ignore[arg-type]
        d = validate_plan({"steps": [{"op": "suspend"}]}).to_dict()
        assert d["ok"] is True and d["plan_hash"] and d["issues"] == []

    def test_fanout_missing_do_and_default_return(self) -> None:
        r = validate_plan({"steps": [{"op": "fanout", "over": "[]", "as": "i", "max": 2}]})
        assert any("do" in i.message for i in r.issues)
        assert r.issues[0].to_dict()["code"] == "SHAPE"
        r = validate_plan({"steps": [{"op": "return"}]})
        assert r.ok  # default value "null"
        # return mid-list keeps validating subsequent steps
        r = validate_plan({"steps": [{"op": "return", "value": "1"},
                                     {"op": "suspend"}]})
        assert r.ok

    def test_too_many_steps(self) -> None:
        plan = {"steps": [{"op": "suspend"}] * 501}
        r = validate_plan(plan)
        assert any(i.code == "BOUND_STEPS" for i in r.issues)

    def test_expr_syntax_in_plan(self) -> None:
        r = validate_plan({"steps": [{"op": "let", "name": "x", "expr": "@@@"}]})
        assert any(i.code == "EXPR_SYNTAX" for i in r.issues)
        r = validate_plan({"steps": [{"op": "call", "tool": "t", "args": {"a": "$$"}}]}, {"t": int})
        assert any(i.code in ("EXPR_SYNTAX", "UNBOUND_VAR") for i in r.issues)


# --- execution ------------------------------------------------------------


class TestRun:
    def test_basic(self) -> None:
        plan = {"steps": [
            {"op": "let", "name": "x", "expr": "2 * 3"},
            {"op": "call", "tool": "add", "args": {"a": "$x", "b": 4}, "save": "y"},
            {"op": "return", "value": "$y"},
        ]}
        r = run_plan(plan, _tools())
        assert r.status == "completed" and r.value == 10 and r.calls == 1
        assert r.to_dict()["state"]["vars"]["y"] == 10

    def test_fanout_bounded(self) -> None:
        plan = {"steps": [
            {"op": "fanout", "over": "[1, 2, 3, 4, 5]", "as": "i", "max": 3,
             "do": [{"op": "call", "tool": "add", "args": {"a": "$i", "b": 10}}],
             "save": "out"},
            {"op": "return", "value": "$out"},
        ]}
        r = run_plan(plan, _tools())
        assert r.status == "completed" and r.value == [11, 12, 13]

    def test_if_else(self) -> None:
        for cond, want in [("true", 1), ("false", 2)]:
            plan = {"steps": [
                {"op": "if", "cond": cond,
                 "then": [{"op": "return", "value": "1"}],
                 "else": [{"op": "return", "value": "2"}]}]}
            assert run_plan(plan, _tools()).value == want
        # no else → falls through
        plan = {"steps": [{"op": "if", "cond": "false", "then": [{"op": "return", "value": "9"}]},
                          {"op": "return", "value": "7"}]}
        assert run_plan(plan, _tools()).value == 7

    def test_call_budget(self) -> None:
        plan = {"steps": [{"op": "call", "tool": "echo", "args": {"n": 1}}] * 3}
        r = run_plan(plan, _tools(), max_calls=2)
        assert r.status == "failed" and r.error and r.error.code == "BOUND_CALLS"

    def test_tool_failure(self) -> None:
        plan = {"steps": [{"op": "call", "tool": "fail", "args": {}}]}
        r = run_plan(plan, _tools())
        assert r.status == "failed" and r.error and r.error.code == "TOOL_FAIL"

    def test_unknown_tool_at_runtime(self) -> None:
        plan = {"steps": [{"op": "call", "tool": "ghost", "args": {}}]}
        r = run_plan(plan, _tools())
        assert r.status == "failed" and r.error and r.error.code == "UNKNOWN_TOOL"

    def test_tool_planerror_passthrough(self) -> None:
        def boom() -> None:
            raise PlanError("CUSTOM", "tool raised PlanError")
        plan = {"steps": [{"op": "call", "tool": "boom", "args": {}}]}
        r = run_plan(plan, {"boom": boom})
        assert r.error and r.error.code == "CUSTOM"

    def test_suspend_resume_no_rerun(self) -> None:
        calls: list[int] = []
        def counted(v: int) -> int:
            calls.append(v)
            return v * 10
        plan = {"steps": [
            {"op": "call", "tool": "counted", "args": {"v": 1}, "save": "a"},
            {"op": "suspend", "reason": "approve?"},
            {"op": "call", "tool": "counted", "args": {"v": 2}, "save": "b"},
            {"op": "return", "value": "$b"},
        ]}
        tools = {"counted": counted}
        deny = PlanRunner(tools, approve=lambda _i, _s: False)
        r1 = deny.run(plan)
        assert r1.status == "suspended" and calls == [1]
        # resume with approval — step 0 must NOT re-run
        allow = PlanRunner(tools, approve=lambda _i, _s: True)
        r2 = allow.run(plan, r1.state)
        assert r2.status == "completed" and r2.value == 20
        assert calls == [1, 2]  # settled call not repeated

    def test_state_roundtrip(self) -> None:
        s = PlanState(vars={"x": 1}, settled={"s9": True}, calls=3,
                      suspended_at=1, suspend_reason="why")
        s2 = PlanState.from_dict(s.to_dict())
        assert s2.vars == {"x": 1} and s2.calls == 3 and s2.suspended_at == 1
        # dict-state convenience path
        r = run_plan({"steps": [{"op": "return", "value": "$x"}]}, {}, state=s.to_dict())
        assert r.value == 1

    def test_suspend_then_approve_inline(self) -> None:
        plan = {"steps": [
            {"op": "suspend", "reason": "ok"},
            {"op": "return", "value": "1"},
        ]}
        r = PlanRunner(_tools(), approve=lambda _i, _s: True).run(plan)
        assert r.status == "completed" and r.value == 1

    def test_fanout_suspend(self) -> None:
        plan = {"steps": [
            {"op": "fanout", "over": "[1, 2, 3]", "as": "i", "max": 5,
             "do": [{"op": "suspend"}]},
            {"op": "return", "value": "0"},
        ]}
        r = PlanRunner(_tools(), approve=lambda _i, _s: False).run(plan)
        assert r.status == "suspended"
        # resume continues the suspended iteration (idx<start skipped)
        r2 = PlanRunner(_tools(), approve=lambda _i, _s: True).run(plan, r.state)
        assert r2.status == "completed" and r2.value == 0

    def test_fanout_suspend_mid_iteration(self) -> None:
        calls: list[int] = []
        def counted(v: int) -> int:
            calls.append(v)
            return v
        # suspends only on i==3 → iterations 0,1 done; resume skips them
        plan = {"steps": [
            {"op": "fanout", "over": "[1, 2, 3]", "as": "i", "max": 5,
             "do": [
                {"op": "call", "tool": "counted", "args": {"v": "$i"}},
                {"op": "if", "cond": "$i == 3", "then": [{"op": "suspend"}]},
             ]},
            {"op": "return", "value": "0"},
        ]}
        tools = {"counted": counted}
        r = PlanRunner(tools, approve=lambda _i, _s: False).run(plan)
        assert r.status == "suspended" and calls == [1, 2, 3]
        calls.clear()
        r2 = PlanRunner(tools, approve=lambda _i, _s: True).run(plan, r.state)
        assert r2.status == "completed"
        assert calls == []  # earlier iterations fully skipped via #done

    def test_fanout_type_error(self) -> None:
        plan = {"steps": [{"op": "fanout", "over": "5", "as": "i", "max": 2,
                           "do": [{"op": "suspend"}]}]}
        r = run_plan(plan, _tools())
        assert r.error and r.error.code == "EXPR_TYPE"

    def test_runtime_errors(self) -> None:
        r = run_plan({"steps": [{"op": "let", "name": "x", "expr": "$no"}]}, {})
        assert r.status == "failed"
        r = run_plan({"steps": [{"op": "bogus"}]}, {})
        assert r.error and r.error.code == "BAD_OP"
        r = run_plan({"steps": [{"op": "fanout", "over": "[1]", "as": "i",
                                 "max": 2, "do": [{"op": "return", "value": "9"}],
                                 "save": "r"},
                                {"op": "return", "value": "$r"}]}, {})
        assert r.status == "completed" and r.value == [9]

    def test_plan_hash_stable(self) -> None:
        p1 = {"steps": [{"op": "suspend"}]}
        assert plan_hash(p1) == plan_hash(dict(p1))
        assert plan_hash(p1) != plan_hash({"steps": []})

    def test_default_result_is_last_value(self) -> None:
        # no explicit return → plan result = last step's produced value
        plan = {"steps": [{"op": "let", "name": "x", "expr": "1"}]}
        r = run_plan(plan, {})
        assert r.status == "completed" and r.value == 1
        r = run_plan({"steps": [{"op": "suspend"}]}, {},
                     approve=lambda _i, _s: True)
        assert r.status == "completed" and r.value is None

    def test_no_save_call(self) -> None:
        plan = {"steps": [{"op": "call", "tool": "echo", "args": {"a": 1}},
                          {"op": "return", "value": "1"}]}
        assert run_plan(plan, _tools()).status == "completed"

    def test_return_in_fanout_yields_iteration(self) -> None:
        plan = {"steps": [
            {"op": "fanout", "over": "[1]", "as": "i", "max": 1,
             "do": [{"op": "return", "value": "42"}]},
            {"op": "return", "value": "0"},
        ]}
        assert run_plan(plan, _tools()).value == 0
        # if-branch return propagates to top level
        plan2 = {"steps": [
            {"op": "if", "cond": "true",
             "then": [{"op": "return", "value": "42"}]},
            {"op": "return", "value": "0"},
        ]}
        assert run_plan(plan2, _tools()).value == 42
