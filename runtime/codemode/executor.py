#!/usr/bin/env python3
"""Sandboxed Code Mode executor.

Executes an agent-authored Python snippet in a restricted namespace inside a
dedicated subprocess (:mod:`runtime.codemode._child`). The only privileged
capability injected is ``call_tool(server, tool, args)``, which round-trips
to the parent over a JSON-lines pipe and routes every invocation through
:mod:`runtime.enforcement` (MCP firewall + AgentGateway) before dispatch —
code mode never bypasses governance.

Sandbox layers:

1. **AST scan** — reuses ``_is_plugin_source_safe`` (denylisted imports,
   dangerous calls, dunder/``__builtins__`` bypasses).
2. **Restricted builtins** — the child execs with a whitelist-only builtins
   dict; ``open``/``eval``/``__import__`` etc. are absent.
3. **Governed tool bridge** — ``call_tool`` goes through
   ``enforce_tool_call``/``enforce_tool_result`` in the *parent* process.
4. **Process isolation + timeout** — execution runs in a spawned child
   process; on timeout the parent ``kill()``s it, guaranteeing termination.
   The previous thread-based sandbox could only *abandon* a timed-out
   worker while it kept executing with ``call_tool`` in scope (C1).
5. **Bounded resources** — snippet output is capped (``max_output_bytes``)
   and tool calls are counted (``max_tool_calls``); the child cannot flood
   the parent with output or unbounded bridge round-trips.
6. **Governed workspace** — ``workspace_read/write/list`` are the only
   filesystem capabilities, confined to ``state/codemode/workspace/`` with
   traversal protection and size caps. Raw ``open`` stays absent.
7. **Strict result enforcement** — with ``strict_results=True`` (the MCP
   surface), enforcement crashes fail closed instead of passing unchecked
   tool output through.

This is a *cooperative* sandbox (no OS-level sandboxing/pledge): it raises
the bar against accidental misuse and injection-driven tool abuse, and it
now guarantees a timed-out snippet cannot keep issuing tool calls.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from runtime.plugin import _is_plugin_source_safe

_logger = logging.getLogger(__name__)

_CHILD_SCRIPT = Path(__file__).resolve().with_name("_child.py")
_STDERR_TAIL = 500

# Workspace bridge caps. The workspace is the ONLY filesystem surface a
# snippet can reach; it is meant for intermediate results, not bulk storage.
_WS_READ_CAP = 262_144  # bytes read per file
_WS_WRITE_CAP = 262_144  # chars written per call
_WS_LIST_CAP = 500  # entries per listing


@dataclass
class CodeModeToolCall:
    """Audit record of a tool call made from inside a sandboxed snippet."""

    server: str
    tool: str
    decision: str  # allow/deny/ask
    ok: bool
    detail: str = ""


@dataclass
class CodeModeResult:
    """Outcome of a sandboxed snippet execution."""

    ok: bool
    output: str = ""
    error: str = ""
    tool_calls: list[CodeModeToolCall] = field(default_factory=list)
    timed_out: bool = False
    # True when snippet output exceeded ``max_output_bytes`` and the tail was
    # dropped — callers must know the output they see is incomplete.
    output_truncated: bool = False
    # Ownership retained: child cleanup did not complete — the process may
    # still be alive. Callers must surface this, never treat it as clean.
    cleanup_pending: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "timed_out": self.timed_out,
            "output_truncated": self.output_truncated,
            "cleanup_pending": self.cleanup_pending,
            "tool_calls": [
                {"server": t.server, "tool": t.tool, "decision": t.decision, "ok": t.ok, "detail": t.detail}
                for t in self.tool_calls
            ],
        }


ToolCaller = Callable[[str, str, dict[str, Any]], dict[str, Any]]


class CodeModeExecutor:
    """Execute sandboxed snippets that call MCP tools, in a child process."""

    def __init__(
        self,
        os_root: Path,
        tool_caller: ToolCaller | None = None,
        timeout_s: float = 15.0,
        max_output_bytes: int = 65_536,
        max_tool_calls: int = 50,
        strict_results: bool | None = None,
    ) -> None:
        self.os_root = os_root
        self._tool_caller = tool_caller or self._default_caller
        self.timeout_s = timeout_s
        self.max_output_bytes = max(1024, int(max_output_bytes))
        self.max_tool_calls = max(1, int(max_tool_calls))
        # Strict mode turns result-enforcement ERRORS into blocks (SEC-13
        # fail-closed). Default preserves the historic degrade-open behavior
        # for the CLI; the MCP surface opts into strict explicitly.
        if strict_results is None:
            strict_results = os.environ.get("AIZEE_CODEMODE_RESULT_STRICT") == "1"
        self.strict_results = strict_results

    def _default_caller(self, server: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        from runtime.mcp_client import McpClient

        return McpClient(server, self.os_root).call_tool(tool, args)

    # -- Public entry point ------------------------------------------------

    def execute(self, source: str) -> CodeModeResult:
        safe, reason = _is_plugin_source_safe(source, "<codemode>")
        if not safe:
            return CodeModeResult(ok=False, error=f"sandbox scan: {reason}")
        calls: list[CodeModeToolCall] = []
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(_CHILD_SCRIPT)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            return CodeModeResult(ok=False, error=f"sandbox spawn failed: {exc}")
        try:
            result = self._pump(proc, source, calls)
        except BaseException:
            self._terminate(proc)
            raise
        result.cleanup_pending = not self._terminate(proc)
        return result

    # -- Subprocess protocol pump ------------------------------------------

    def _pump(self, proc: subprocess.Popen[str], source: str, calls: list[CodeModeToolCall]) -> CodeModeResult:
        out_parts: list[str] = []
        out_state: dict[str, Any] = {"bytes": 0, "truncated": False}
        err_parts: list[str] = []
        lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read_lines, args=(proc.stdout, lines), daemon=True).start()
        threading.Thread(target=self._drain, args=(proc.stderr, err_parts), daemon=True).start()

        def _finish(result: CodeModeResult) -> CodeModeResult:
            result.output_truncated = out_state["truncated"]
            return result

        if not self._write_msg(proc, {"source": source}):
            return _finish(self._crash_result(proc, calls, out_parts, err_parts, "sandbox request failed"))
        deadline = time.monotonic() + self.timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _finish(self._timeout_result(proc, calls, out_parts))
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty:
                return _finish(self._timeout_result(proc, calls, out_parts))
            if line is None:
                return _finish(self._crash_result(proc, calls, out_parts, err_parts, "sandbox exited without result"))
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                return _finish(self._crash_result(proc, calls, out_parts, err_parts, "sandbox protocol violation"))
            msg_type = msg.get("type")
            if msg_type == "out":
                self._append_output(out_parts, out_state, str(msg.get("data", "")))
            elif msg_type == "tool_call":
                self._answer_tool_call(proc, msg, calls)
            elif msg_type == "workspace":
                self._answer_workspace(proc, msg)
            elif msg_type == "done":
                return _finish(self._done_result(proc, msg, calls, out_parts))

    def _append_output(self, out_parts: list[str], out_state: dict[str, Any], data: str) -> None:
        """Append snippet output under the byte cap; drop the tail once full.

        The cap is measured in characters (a close proxy for bytes in this
        text pipe). Once truncated, further output is discarded entirely —
        memory stays bounded even if the snippet prints in a tight loop.
        """
        if out_state["truncated"]:
            return
        remaining = self.max_output_bytes - out_state["bytes"]
        if len(data) <= remaining:
            out_parts.append(data)
            out_state["bytes"] += len(data)
            return
        if remaining > 0:
            out_parts.append(data[:remaining])
            out_state["bytes"] += remaining
        out_state["truncated"] = True

    def _answer_tool_call(self, proc: subprocess.Popen[str], msg: dict[str, Any], calls: list[CodeModeToolCall]) -> None:
        args = msg.get("args")
        resp = self._dispatch_tool_call(
            str(msg.get("server", "")), str(msg.get("tool", "")),
            args if isinstance(args, dict) else {}, calls,
        )
        self._write_msg(proc, resp)

    def _answer_workspace(self, proc: subprocess.Popen[str], msg: dict[str, Any]) -> None:
        self._write_msg(proc, self._dispatch_workspace(msg))

    # -- Workspace bridge (governed persistence) ----------------------------

    def _workspace_root(self) -> Path:
        return self.os_root / "state" / "codemode" / "workspace"

    def _resolve_ws_path(self, raw: str) -> Path | None:
        """Resolve a snippet-supplied relative path inside the workspace root.

        Rejects absolute paths, drive letters, UNC prefixes, and any ``..``
        segment; symlinks that escape the workspace fail the final
        ``relative_to`` check after resolution.
        """
        text = raw.replace("\\", "/")
        if text.startswith("/"):
            return None
        parts = [p for p in text.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return None
        if any(len(p) == 2 and p[1] == ":" for p in parts):
            return None
        base = self._workspace_root()
        target = base.joinpath(*parts) if parts else base
        try:
            resolved = target.resolve(strict=False)
            resolved.relative_to(base.resolve(strict=False))
        except (OSError, ValueError, RuntimeError):
            return None
        return resolved

    def _dispatch_workspace(self, msg: dict[str, Any]) -> dict[str, Any]:
        op = str(msg.get("op") or "")
        raw_path = str(msg.get("path") or "")
        if op not in ("read", "write", "list"):
            return {"ok": False, "error": f"unknown workspace op {op!r}"}
        if op in ("read", "write") and not raw_path.strip():
            return {"ok": False, "error": "workspace path required"}
        target = self._resolve_ws_path(raw_path)
        if target is None:
            return {"ok": False, "error": "workspace path escapes workspace root"}
        if op == "read":
            return self._ws_read(target)
        if op == "write":
            data = msg.get("data")
            return self._ws_write(target, data if isinstance(data, str) else "")
        return self._ws_list(target)

    @staticmethod
    def _ws_read(target: Path) -> dict[str, Any]:
        if not target.is_file():
            return {"ok": False, "error": "workspace file not found"}
        try:
            if target.stat().st_size > _WS_READ_CAP:
                return {"ok": False, "error": f"workspace file exceeds {_WS_READ_CAP} bytes"}
            return {"ok": True, "result": target.read_text(encoding="utf-8", errors="replace")}
        except OSError as exc:
            return {"ok": False, "error": f"workspace read failed: {exc}"}

    @staticmethod
    def _ws_write(target: Path, data: str) -> dict[str, Any]:
        if len(data) > _WS_WRITE_CAP:
            return {"ok": False, "error": f"workspace write exceeds {_WS_WRITE_CAP} chars"}
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data, encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"workspace write failed: {exc}"}
        return {"ok": True, "result": len(data)}

    def _ws_list(self, target: Path) -> dict[str, Any]:
        if not target.is_dir():
            return {"ok": True, "result": []}
        base = self._workspace_root().resolve(strict=False)
        entries: list[str] = []
        try:
            for p in sorted(target.rglob("*")):
                if len(entries) >= _WS_LIST_CAP:
                    break
                if p.is_file():
                    entries.append(str(p.relative_to(base)).replace("\\", "/"))
        except OSError as exc:
            return {"ok": False, "error": f"workspace list failed: {exc}"}
        return {"ok": True, "result": entries}

    def _dispatch_tool_call(self, server: str, tool: str, args: dict[str, Any], calls: list[CodeModeToolCall]) -> dict[str, Any]:
        if len(calls) >= self.max_tool_calls:
            # No audit record appended here: repeated attempts must stay
            # memory-bounded. The first max_tool_calls are already recorded.
            return {"ok": False, "error": f"tool call limit ({self.max_tool_calls}) exceeded"}
        decision = self._enforce(server, tool, args)
        if decision is not None:
            verdict = decision.get("decision", "deny")
            calls.append(
                CodeModeToolCall(server, tool, verdict, False, str(decision.get("error") or decision.get("reason") or "denied"))
            )
            return {"ok": False, "error": f"Tool call blocked ({verdict}): {decision.get('reason', 'denied')}"}
        try:
            result = self._tool_caller(server, tool, args)
        except Exception as exc:
            # A crashing dispatcher must not kill the protocol pump: report
            # the failure to the child as a normal denial-style response so
            # the snippet sees a controlled exception instead of a dead pipe.
            calls.append(CodeModeToolCall(server, tool, "error", False, str(exc)[:200]))
            return {"ok": False, "error": f"Tool call failed: {exc}"}
        result_text = json.dumps(result, default=str)
        ok, checked_text = self._enforce_result(server, tool, result_text)
        if not ok:
            calls.append(CodeModeToolCall(server, tool, "deny", False, "response blocked"))
            return {"ok": False, "error": f"Tool result blocked: {checked_text}"}
        calls.append(CodeModeToolCall(server, tool, "allow", True))
        try:
            return {"ok": True, "result": json.loads(checked_text)}
        except json.JSONDecodeError:
            return {"ok": True, "result": checked_text}

    # -- Result builders ----------------------------------------------------

    def _done_result(self, proc: subprocess.Popen[str], msg: dict[str, Any], calls: list[CodeModeToolCall], out_parts: list[str]) -> CodeModeResult:
        output = "".join(out_parts)
        self._reap(proc)
        if msg.get("ok"):
            return CodeModeResult(ok=True, output=output, tool_calls=calls)
        exc_type = str(msg.get("exc_type") or "")
        detail = str(msg.get("error") or "")
        if exc_type in ("PermissionError", "ChildError", ""):
            error = detail
        else:
            error = f"{exc_type}: {detail}" if detail else exc_type
        return CodeModeResult(ok=False, output=output, error=error, tool_calls=calls)

    def _timeout_result(self, proc: subprocess.Popen[str], calls: list[CodeModeToolCall], out_parts: list[str]) -> CodeModeResult:
        return CodeModeResult(
            ok=False, output="".join(out_parts), error=f"timeout after {self.timeout_s}s",
            tool_calls=calls, timed_out=True,
        )

    def _crash_result(self, proc: subprocess.Popen[str], calls: list[CodeModeToolCall], out_parts: list[str], err_parts: list[str], reason: str) -> CodeModeResult:
        code = proc.poll()
        detail = f"{reason} (exit code {code})"
        tail = "".join(err_parts).strip()[-_STDERR_TAIL:]
        if tail:
            detail += f": {tail}"
        return CodeModeResult(ok=False, output="".join(out_parts), error=detail, tool_calls=calls)

    # -- Process plumbing ---------------------------------------------------

    @staticmethod
    def _write_msg(proc: subprocess.Popen[str], msg: dict[str, Any]) -> bool:
        try:
            assert proc.stdin is not None
            proc.stdin.write(json.dumps(msg, default=str) + "\n")
            proc.stdin.flush()
        except (OSError, ValueError):
            return False
        return True

    @staticmethod
    def _read_lines(stream: TextIO | None, sink: queue.Queue[str | None]) -> None:
        try:
            if stream is not None:
                for line in stream:
                    sink.put(line)
        except (OSError, ValueError) as exc:
            _logger.debug("pipe reader stopped abnormally: %s", exc)
        finally:
            sink.put(None)

    @staticmethod
    def _drain(stream: TextIO | None, sink: list[str]) -> None:
        try:
            if stream is not None:
                for line in stream:
                    sink.append(line)
        except (OSError, ValueError) as exc:
            _logger.debug("pipe drain stopped abnormally: %s", exc)

    @staticmethod
    def _reap(proc: subprocess.Popen[str]) -> None:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=2)

    @staticmethod
    def _terminate(proc: subprocess.Popen[str]) -> bool:
        """Kill + reap the child. Returns True only when fully reaped.

        Cleanup failure does NOT drop ownership: retry the kill once, then
        retain the handle and report pending cleanup (REA lifecycle
        invariant - a resource whose cleanup failed is still ours).
        """
        try:
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=5)
                return True
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                    return True
                except subprocess.TimeoutExpired:
                    _logger.error(
                        "codemode child %s still alive after kill retry - retaining ownership",
                        proc.pid,
                    )
                    return False
        except OSError as exc:
            _logger.error("codemode child cleanup failed: %s", exc)
            return False

    # -- Governance bridge --------------------------------------------------

    def _enforce(self, server: str, tool: str, args: dict[str, Any]) -> dict[str, Any] | None:
        try:
            from runtime.enforcement import enforce_tool_call_root

            return enforce_tool_call_root(self.os_root, server, tool, args)
        except Exception as exc:
            return {"decision": "deny", "reason": f"enforcement error: {exc}"}

    def _enforce_result(self, server: str, tool: str, result_text: str) -> tuple[bool, str]:
        try:
            from runtime.enforcement import enforce_tool_result_root

            return enforce_tool_result_root(self.os_root, server, tool, result_text)
        except Exception as exc:
            _logger.warning("codemode result enforcement error (degraded): %s", exc)
            if self.strict_results:
                # SEC-13 fail-closed: in strict mode an enforcement crash is a
                # block, never silent passthrough of unchecked tool output.
                return False, f"result enforcement error (strict): {exc}"
            return True, result_text
