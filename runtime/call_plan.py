"""Inert plan execution engine (vercel-labs/callscript adoption).

The model authors a *plan*, not code. A plan is JSON data describing tool
calls; the only thing that can execute is a mounted tool. Everything the
plan contains — steps, expressions, fan-outs — is inspectable, statically
validatable, bounded, serializable, and resumable.

Design ported from callscript's guarantees:

- **Inert by construction**: plans are parsed and validated as data. There
  is no ``eval``/``exec`` anywhere — expressions compile to a tiny AST and
  are evaluated against the step environment only.
- **All-issues validation**: ``validate_plan`` reports every problem at
  once (unknown tools, unbound vars, missing ``max`` on fan-outs) instead
  of failing at runtime one error at a time.
- **Bounded**: step count, total tool calls, and per-fan-out width are
  declared caps; a runaway plan is a validation error, not an incident.
- **Resumable**: the run state (vars + settled results + program counter)
  is plain JSON; a ``suspend`` step yields a resume token and later runs
  skip settled steps — an approval gate that doesn't re-run side effects.
- **Auditable**: ``plan_hash`` is content-addressed; what will run and
  what ran are the same artifact.

Plan shape::

    {
      "steps": [
        {"op": "let", "name": "x", "expr": "1 + 2"},
        {"op": "call", "tool": "dns.lookup", "args": {"name": "example.com"},
         "save": "ips"},
        {"op": "fanout", "over": "$ips", "as": "ip", "max": 10,
         "do": [{"op": "call", "tool": "whois", "args": {"ip": "$ip"}}],
         "save": "records"},
        {"op": "if", "cond": "len($records) > 0",
         "then": [{"op": "return", "value": "$records"}],
         "else": [{"op": "return", "value": "[]"}]},
        {"op": "suspend", "reason": "needs approval"},
        {"op": "return", "value": "$x"}
      ]
    }
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

MAX_STEPS = 500
MAX_FANOUT = 100
MAX_CALLS = 200
VALID_OPS = frozenset({"let", "call", "if", "fanout", "suspend", "return"})
_EXPR_FUNCS = frozenset(
    {"len", "int", "str", "float", "sum", "min", "max", "sorted", "keys", "values", "abs", "round"}
)


class PlanError(Exception):
    """Single plan validation/execution issue with step index context."""

    def __init__(self, code: str, message: str, step: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.step = step

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "step": self.step}


# ---------------------------------------------------------------------------
# Expression engine — a tiny safe DSL, never eval().
# Grammar: or -> and -> not -> cmp -> add -> mul -> unary -> postfix -> atom
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""\s*(
        \$\w+(?:\.[\w.]*|\[\w*\])*  # $var / $var.path / $var[0].x
      | \d+\.\d+|\d+             # numbers
      | "(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'  # strings
      | [A-Za-z_]\w*             # identifiers (funcs, true/false/null, and/or/not/in)
      | ==|!=|<=|>=|<|>|\+|-|\*|/|%|\(|\)|,|\[|\]|\{|\}|:
    )""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class _Tok:
    kind: str
    text: str


def _tokenize(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i = 0
    while i < len(src):
        m = _TOKEN_RE.match(src, i)
        if not m:
            raise PlanError("EXPR_SYNTAX", f"bad token at {src[i:i+12]!r}")
        i = m.end()
        t = m.group(1).strip()
        toks.append(_Tok("var" if t.startswith("$") else "num" if t[0].isdigit() else "str" if t[0] in "\"'" else "id" if t[0].isalpha() else "op", t))
    return toks


class _ExprParser:
    """Recursive-descent parser producing an evaluatable node tree."""

    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.i = 0

    def _peek(self) -> str:
        return self.toks[self.i].text if self.i < len(self.toks) else ""

    def _eat(self, expected: str | None = None) -> _Tok:
        if self.i >= len(self.toks):
            raise PlanError("EXPR_SYNTAX", "unexpected end of expression")
        tok = self.toks[self.i]
        if expected is not None and tok.text != expected:
            raise PlanError("EXPR_SYNTAX", f"expected {expected!r}, got {tok.text!r}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        node = self._or()
        if self.i != len(self.toks):
            raise PlanError("EXPR_SYNTAX", f"trailing token {self._peek()!r}")
        return node

    def _or(self) -> Any:
        node = self._and()
        while self._peek() == "or":
            self._eat()
            node = ("or", node, self._and())
        return node

    def _and(self) -> Any:
        node = self._not()
        while self._peek() == "and":
            self._eat()
            node = ("and", node, self._not())
        return node

    def _not(self) -> Any:
        if self._peek() == "not":
            self._eat()
            return ("not", self._not())
        return self._cmp()

    def _cmp(self) -> Any:
        node = self._add()
        while self._peek() in ("==", "!=", "<", "<=", ">", ">=", "in"):
            op = self._eat().text
            node = (op, node, self._add())
        return node

    def _add(self) -> Any:
        node = self._mul()
        while self._peek() in ("+", "-"):
            op = self._eat().text
            node = (op, node, self._mul())
        return node

    def _mul(self) -> Any:
        node = self._unary()
        while self._peek() in ("*", "/", "%"):
            op = self._eat().text
            node = (op, node, self._unary())
        return node

    def _unary(self) -> Any:
        if self._peek() == "-":
            self._eat()
            return ("neg", self._unary())
        return self._atom()

    def _atom(self) -> Any:
        tok = self._eat()
        if tok.text == "(":
            node = self._or()
            self._eat(")")
            return node
        if tok.text == "[":
            items: list[Any] = []
            while self._peek() != "]":
                items.append(self._or())
                if self._peek() == ",":
                    self._eat()
            self._eat("]")
            return ("list", items)
        if tok.text == "{":
            pairs: list[tuple[str, Any]] = []
            while self._peek() != "}":
                key_tok = self._eat()
                if key_tok.kind not in ("str", "id"):
                    raise PlanError("EXPR_SYNTAX", "dict keys must be strings or identifiers")
                key = (
                    bytes(key_tok.text[1:-1], "utf-8").decode("unicode_escape")
                    if key_tok.kind == "str"
                    else key_tok.text
                )
                self._eat(":")
                pairs.append((key, self._or()))
                if self._peek() == ",":
                    self._eat()
            self._eat("}")
            return ("dict", pairs)
        if tok.kind == "var":
            return ("var", _var_path(tok.text))
        if tok.kind == "num":
            return ("lit", float(tok.text) if "." in tok.text else int(tok.text))
        if tok.kind == "str":
            return ("lit", bytes(tok.text[1:-1], "utf-8").decode("unicode_escape"))
        if tok.text in ("true", "false", "null"):
            return ("lit", {"true": True, "false": False, "null": None}[tok.text])
        if tok.text in _EXPR_FUNCS and self._peek() == "(":
            self._eat("(")
            args: list[Any] = []
            while self._peek() != ")":
                args.append(self._or())
                if self._peek() == ",":
                    self._eat()
            self._eat(")")
            return ("call", tok.text, args)
        raise PlanError("EXPR_SYNTAX", f"unexpected token {tok.text!r}")


def _var_path(text: str) -> tuple[str, ...]:
    """`$a.b[0].c` -> ('a', 'b', 0, 'c')."""
    parts: list[str | int] = []
    buf = ""
    i = 1  # skip $
    while i < len(text):
        ch = text[i]
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
            i += 1
        elif ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = text.index("]", i)  # tokenizer guarantees ']'
            idx = text[i + 1 : j]
            parts.append(int(idx) if idx.lstrip("-").isdigit() else idx)
            i = j + 1
        else:
            buf += ch
            i += 1
    if buf:
        parts.append(buf)
    return tuple(str(p) if isinstance(p, int) else p for p in parts)


def _resolve_path(path: tuple[str, ...], env: dict[str, Any]) -> Any:
    cur: Any = env.get(path[0], _MISSING)
    if cur is _MISSING:
        raise PlanError("UNBOUND_VAR", f"unbound variable ${path[0]}")
    for part in path[1:]:
        try:
            cur = cur[int(part)] if isinstance(cur, (list, tuple)) and part.lstrip("-").isdigit() else cur[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlanError("PATH_MISS", f"path ${'.'.join(path)} missing at {part!r}") from exc
    return cur


_MISSING = object()


def _eval(node: Any, env: dict[str, Any]) -> Any:
    if not isinstance(node, tuple):
        return node
    tag = node[0]
    if tag == "lit":
        return node[1]
    if tag == "var":
        return _resolve_path(node[1], env)
    if tag == "list":
        return [_eval(n, env) for n in node[1]]
    if tag == "dict":
        return {k: _eval(n, env) for k, n in node[1]}
    if tag == "not":
        return not _eval(node[1], env)
    if tag == "neg":
        return -_eval(node[1], env)
    if tag == "and":
        return _eval(node[1], env) and _eval(node[2], env)
    if tag == "or":
        return _eval(node[1], env) or _eval(node[2], env)
    if tag in ("==", "!=", "<", "<=", ">", ">=", "in"):
        a, b = _eval(node[1], env), _eval(node[2], env)
        try:
            if tag == "==":
                return a == b
            if tag == "!=":
                return a != b
            if tag == "<":
                return a < b
            if tag == "<=":
                return a <= b
            if tag == ">":
                return a > b
            if tag == ">=":
                return a >= b
            return a in b
        except TypeError as exc:
            raise PlanError("EXPR_TYPE", f"cannot compare/scan {a!r} {tag} {b!r}") from exc
    if tag in ("+", "-", "*"):
        a, b = _eval(node[1], env), _eval(node[2], env)
        try:
            if tag == "+":
                return a + b
            if tag == "-":
                return a - b
            return a * b
        except TypeError as exc:
            raise PlanError("EXPR_TYPE", f"cannot {tag} {a!r} and {b!r}") from exc
    if tag == "/":
        den = _eval(node[2], env)
        if den == 0:
            raise PlanError("EXPR_DIV0", "division by zero")
        return _eval(node[1], env) / den
    if tag == "%":
        den = _eval(node[2], env)
        if den == 0:
            raise PlanError("EXPR_DIV0", "modulo by zero")
        return _eval(node[1], env) % den
    if tag == "call":
        fn = _FUNC_IMPL[node[1]]
        args = [_eval(n, env) for n in node[2]]
        try:
            return fn(*args)
        except (TypeError, ValueError) as exc:
            raise PlanError("EXPR_CALL", f"{node[1]}() failed: {exc}") from exc
    raise PlanError("EXPR_SYNTAX", f"bad node {tag!r}")


_FUNC_IMPL: dict[str, Callable[..., Any]] = {
    "len": len,
    "int": int,
    "str": str,
    "float": float,
    "abs": abs,
    "round": round,
    "sum": sum,
    "min": min,
    "max": max,
    "sorted": sorted,
    "keys": lambda d: list(d.keys()),
    "values": lambda d: list(d.values()),
}


def eval_expr(src: str, env: dict[str, Any]) -> Any:
    """Compile + evaluate an expression string against ``env``."""
    return _eval(_ExprParser(_tokenize(src)).parse(), env)


def _expr_refs(node: Any, out: set[str]) -> None:
    """Collect top-level variable names referenced by an expr AST."""
    if not isinstance(node, tuple):
        return
    if node[0] == "var":
        out.add(node[1][0])
        return
    if node[0] == "call":
        for a in node[2]:
            _expr_refs(a, out)
        return
    if node[0] == "dict":
        for _, v in node[1]:
            _expr_refs(v, out)
        return
    for n in node[1:]:
        if isinstance(n, list):
            for x in n:
                _expr_refs(x, out)
        else:
            _expr_refs(n, out)


def expr_vars(src: str) -> set[str]:
    """Top-level `$name` bindings an expression depends on."""
    out: set[str] = set()
    _expr_refs(_ExprParser(_tokenize(src)).parse(), out)
    return out


# ---------------------------------------------------------------------------
# Plan structures + validation
# ---------------------------------------------------------------------------

@dataclass
class PlanIssue:
    code: str
    message: str
    step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "step": self.step}


@dataclass
class PlanValidation:
    ok: bool
    issues: list[PlanIssue] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    plan_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
            "tools_used": self.tools_used,
            "plan_hash": self.plan_hash,
        }


def plan_hash(plan: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def _count_steps(plan: dict[str, Any]) -> int:
    """Total steps including nested then/else/do blocks."""
    def walk(steps: list[Any]) -> int:
        n = 0
        for s in steps:
            n += 1
            if isinstance(s, dict):
                for key in ("then", "else", "do"):
                    sub = s.get(key)
                    if isinstance(sub, list):
                        n += walk(sub)
        return n
    steps = plan.get("steps", [])
    return walk(steps) if isinstance(steps, list) else 0


def _validate_expr(src: object, step_i: int, bound: set[str], issues: list[PlanIssue]) -> None:
    if not isinstance(src, str):
        issues.append(PlanIssue("EXPR_TYPE", "expression must be a string", step_i))
        return
    try:
        refs = expr_vars(src)
    except PlanError as exc:
        issues.append(PlanIssue(exc.code, exc.message, step_i))
        return
    for name in sorted(refs):
        if name not in bound:
            issues.append(PlanIssue("UNBOUND_VAR", f"expression references unbound ${name}", step_i))


def validate_plan(
    plan: dict[str, Any],
    tools: dict[str, Callable[..., Any]] | None = None,
    *,
    max_steps: int = MAX_STEPS,
    max_fanout: int = MAX_FANOUT,
) -> PlanValidation:
    """Static validation — reports EVERY issue at once (callscript parity)."""
    issues: list[PlanIssue] = []
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        return PlanValidation(
            ok=False,
            issues=[PlanIssue("SHAPE", "plan must be an object with a 'steps' list")],
        )
    steps = plan["steps"]
    total = _count_steps(plan)
    if total > max_steps:
        issues.append(PlanIssue("BOUND_STEPS", f"plan has {total} steps > {max_steps}"))
    used: set[str] = set()
    _validate_block(steps, set(), issues, used, tools, max_fanout)
    return PlanValidation(
        ok=not issues,
        issues=issues,
        tools_used=sorted(used),
        plan_hash=plan_hash(plan),
    )


def _validate_block(
    steps: list[Any],
    bound: set[str],
    issues: list[PlanIssue],
    used: set[str],
    tools: dict[str, Callable[..., Any]] | None,
    max_fanout: int,
) -> None:
    """Validate a step list in document order with scoped bindings.

    Names bound by ``let``/``save``/``as`` are visible from their step onward
    at the same block level; names bound inside then/else/do subtrees do not
    leak upward (matching the runtime's per-block semantics).
    """
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            issues.append(PlanIssue("SHAPE", "step must be an object", i))
            continue
        op = step.get("op")
        if op not in VALID_OPS:
            issues.append(PlanIssue("BAD_OP", f"unknown op {op!r}", i))
            continue
        if op == "let":
            _validate_expr(step.get("expr"), i, bound, issues)
            if not isinstance(step.get("name"), str) or not step["name"]:
                issues.append(PlanIssue("SHAPE", "let needs a string 'name'", i))
            else:
                bound.add(step["name"])
        elif op == "call":
            tool = step.get("tool")
            if not isinstance(tool, str) or not tool:
                issues.append(PlanIssue("SHAPE", "call needs a string 'tool'", i))
            else:
                used.add(tool)
                if tools is not None and tool not in tools:
                    issues.append(PlanIssue("UNKNOWN_TOOL", f"unknown tool {tool!r}", i))
            args = step.get("args", {})
            if not isinstance(args, dict):
                issues.append(PlanIssue("SHAPE", "call 'args' must be an object", i))
            else:
                for v in args.values():
                    if isinstance(v, str) and v.startswith("$"):
                        try:
                            for name in expr_vars(v):
                                if name not in bound:
                                    issues.append(
                                        PlanIssue("UNBOUND_VAR", f"arg references unbound ${name}", i)
                                    )
                        except PlanError as exc:
                            issues.append(PlanIssue(exc.code, exc.message, i))
            if "save" in step:
                if not isinstance(step["save"], str) or not step["save"]:
                    issues.append(PlanIssue("SHAPE", "'save' must be a non-empty string", i))
                else:
                    bound.add(step["save"])
        elif op == "fanout":
            if "max" not in step:
                issues.append(PlanIssue("UNBOUNDED", "fanout requires 'max'", i))
            elif not isinstance(step["max"], int) or step["max"] < 1 or step["max"] > max_fanout:
                issues.append(PlanIssue("BOUND_FANOUT", f"fanout max must be 1..{max_fanout}", i))
            _validate_expr(step.get("over"), i, bound, issues)
            as_name = step.get("as")
            if not isinstance(as_name, str) or not as_name:
                issues.append(PlanIssue("SHAPE", "fanout needs a string 'as'", i))
            body = step.get("do")
            if not isinstance(body, list) or not body:
                issues.append(PlanIssue("SHAPE", "fanout needs a non-empty 'do' list", i))
            else:
                inner = set(bound)
                if isinstance(as_name, str) and as_name:
                    inner.add(as_name)
                _validate_block(body, inner, issues, used, tools, max_fanout)
            if "save" in step and isinstance(step["save"], str) and step["save"]:
                bound.add(step["save"])
        elif op == "if":
            _validate_expr(step.get("cond"), i, bound, issues)
            if not isinstance(step.get("then"), list) or not step["then"]:
                issues.append(PlanIssue("SHAPE", "if needs a non-empty 'then' list", i))
            else:
                _validate_block(step["then"], set(bound), issues, used, tools, max_fanout)
            if "else" in step:
                if not isinstance(step["else"], list):
                    issues.append(PlanIssue("SHAPE", "'else' must be a list", i))
                else:
                    _validate_block(step["else"], set(bound), issues, used, tools, max_fanout)
        elif op == "suspend":
            pass
        else:  # op == "return" (last valid op)
            _validate_expr(step.get("value", "null"), i, bound, issues)


# ---------------------------------------------------------------------------
# Execution — bounded, resumable, auditable
# ---------------------------------------------------------------------------

@dataclass
class PlanState:
    """Serializable run state — resume skips settled steps."""

    vars: dict[str, Any] = field(default_factory=dict)
    settled: dict[str, Any] = field(default_factory=dict)  # step-id -> result
    calls: int = 0
    suspended_at: int | None = None
    suspend_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vars": self.vars,
            "settled": self.settled,
            "calls": self.calls,
            "suspended_at": self.suspended_at,
            "suspend_reason": self.suspend_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanState:
        return cls(
            vars=dict(data.get("vars", {})),
            settled=dict(data.get("settled", {})),
            calls=int(data.get("calls", 0)),
            suspended_at=data.get("suspended_at"),
            suspend_reason=str(data.get("suspend_reason", "")),
        )


@dataclass
class PlanResult:
    status: str  # completed | suspended | failed | denied
    value: Any = None
    state: PlanState = field(default_factory=PlanState)
    error: PlanError | None = None
    calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "value": self.value,
            "calls": self.calls,
            "state": self.state.to_dict(),
            "error": self.error.to_dict() if self.error else None,
        }


class PlanRunner:
    """Executes a validated plan against a mounted tool registry.

    Tools are ``Callable(**kwargs) -> Any``. ``approve`` is invoked before a
    step marked ``options.suspend`` — return False to suspend the run.
    """

    def __init__(
        self,
        tools: dict[str, Callable[..., Any]],
        *,
        max_calls: int = MAX_CALLS,
        approve: Callable[[int, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.tools = tools
        self.max_calls = max_calls
        self.approve = approve or (lambda _i, _s: True)

    def run(
        self,
        plan: dict[str, Any],
        state: PlanState | None = None,
    ) -> PlanResult:
        state = state or PlanState()
        state.suspended_at = None  # resume: clear prior suspension, retry the gate
        state.suspend_reason = ""
        try:
            value = self._exec_block(plan["steps"], state)
        except PlanError as exc:
            return PlanResult(status="failed", state=state, error=exc, calls=state.calls)
        if state.suspended_at is not None:
            return PlanResult(status="suspended", value=value, state=state, calls=state.calls)
        return PlanResult(status="completed", value=value, state=state, calls=state.calls)

    # -- block/step execution ---------------------------------------------

    def _exec_block(
        self,
        steps: list[dict[str, Any]],
        state: PlanState,
        *,
        prefix: str = "",
    ) -> Any:
        last: Any = None
        for i, step in enumerate(steps):
            key = f"{prefix}s{i}"
            if key in state.settled:
                continue  # resume: settled steps never re-run
            if state.suspended_at is not None:
                return last
            out = self._exec_step(step, state, i, key)
            if isinstance(out, _Return):
                return out.value
            if out is not _NO_VAL:
                last = out
        return last

    def _exec_step(
        self,
        step: dict[str, Any],
        state: PlanState,
        i: int,
        key: str,
    ) -> Any:
        op = step.get("op")
        if op == "let":
            state.vars[step["name"]] = value = eval_expr(step["expr"], state.vars)
            state.settled[key] = True
            return value
        if op == "call":
            return self._exec_call(step, state, i, key)
        if op == "fanout":
            items = eval_expr(step["over"], state.vars)
            if not isinstance(items, (list, tuple)):
                raise PlanError("EXPR_TYPE", "fanout 'over' must evaluate to a list", i)
            results = []
            start = int(state.settled.get(f"{key}/#done", 0))  # resume point
            for idx, item in enumerate(list(items)[: step["max"]]):
                if idx < start:
                    continue
                state.vars[step["as"]] = item
                results.append(
                    self._exec_block(step["do"], state, prefix=f"{key}/i{idx}/")
                )
                if state.suspended_at is not None:
                    state.settled[f"{key}/#done"] = idx  # redo this iteration
                    return results  # suspended: fanout NOT settled, resume redoes it
                state.settled[f"{key}/#done"] = idx + 1
            if "save" in step:
                state.vars[step["save"]] = results
            state.settled[key] = results
            return results
        if op == "if":
            cond = eval_expr(step["cond"], state.vars)
            branch = step["then"] if cond else step.get("else", [])
            out = self._exec_block(branch, state, prefix=f"{key}/")
            state.settled[key] = True
            if out is not None:
                return _Return(out)
            return _NO_VAL
        if op == "suspend":
            if not self.approve(i, step):
                state.suspended_at = i
                state.suspend_reason = str(step.get("reason", "approval required"))
                return _NO_VAL
            state.settled[key] = True
            return _NO_VAL
        if op == "return":
            value = eval_expr(step.get("value", "null"), state.vars)
            state.settled[key] = value
            return _Return(value)
        raise PlanError("BAD_OP", f"unknown op {op!r}", i)

    def _exec_call(
        self,
        step: dict[str, Any],
        state: PlanState,
        i: int,
        key: str,
    ) -> Any:
        state.calls += 1
        if state.calls > self.max_calls:
            raise PlanError("BOUND_CALLS", f"call budget {self.max_calls} exceeded", i)
        tool = self.tools.get(step["tool"])
        if tool is None:
            raise PlanError("UNKNOWN_TOOL", f"unknown tool {step['tool']!r}", i)
        args = {
            k: eval_expr(v, state.vars) if isinstance(v, str) and v.startswith("$") else v
            for k, v in (step.get("args") or {}).items()
        }
        try:
            result = tool(**args)
        except PlanError:
            raise
        except Exception as exc:  # tool failures surface as plan errors
            raise PlanError("TOOL_FAIL", f"{step['tool']} failed: {exc}", i) from exc
        if "save" in step:
            state.vars[step["save"]] = result
        state.settled[key] = result
        return result


class _Return:
    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


_NO_VAL = object()


def run_plan(
    plan: dict[str, Any],
    tools: dict[str, Callable[..., Any]],
    *,
    state: PlanState | dict[str, Any] | None = None,
    max_calls: int = MAX_CALLS,
    approve: Callable[[int, dict[str, Any]], bool] | None = None,
) -> PlanResult:
    """Convenience one-shot: validate-shape-then-run.

    Callers wanting the full issue list use ``validate_plan`` first.
    """
    if isinstance(state, dict):
        state = PlanState.from_dict(state)
    return PlanRunner(tools, max_calls=max_calls, approve=approve).run(plan, state)
