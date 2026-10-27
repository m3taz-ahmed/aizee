"""Uniform MCP tool response envelope + stable error codes.

Adopted from Agent-Reach: every MCP tool returns the same JSON shape so
agents can handle results and failures predictably:

    {
        "schema_version": "aizee.tool.v1",
        "ok": true,
        "tool": "aizee_doctor",
        "result": {...} | null,
        "error": {"code": "...", "message": "..."} | null,
        "meta": {"cost": {...}, "update": {...} | null}
    }

Stable error codes let callers branch on failure kind instead of parsing
free-text messages.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from runtime.schemas import AizeeError

F = TypeVar("F", bound=Callable[..., Any])

SCHEMA_VERSION = "aizee.tool.v1"


class ToolErrorCode(str, Enum):
    """Stable error codes for MCP tool responses."""

    NEED_SETUP = "NEED_SETUP"
    NEED_LOGIN = "NEED_LOGIN"
    UPSTREAM_BROKEN = "UPSTREAM_BROKEN"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_FOUND = "NOT_FOUND"
    BAD_INPUT = "BAD_INPUT"
    POLICY_DENIED = "POLICY_DENIED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"
    INTERNAL = "INTERNAL"


_ERROR_CODE_MAP: dict[str, ToolErrorCode] = {
    "PolicyDeniedError": ToolErrorCode.POLICY_DENIED,
    "BudgetExceededError": ToolErrorCode.BUDGET_EXCEEDED,
    "ValidationError": ToolErrorCode.VALIDATION_FAILED,
    "StorageError": ToolErrorCode.STORAGE_FAILED,
    "FileNotFoundError": ToolErrorCode.NOT_FOUND,
    "TimeoutError": ToolErrorCode.TIMEOUT,
    "PermissionError": ToolErrorCode.POLICY_DENIED,
    "ValueError": ToolErrorCode.BAD_INPUT,
    "KeyError": ToolErrorCode.BAD_INPUT,
}


def _error_code(exc: BaseException) -> ToolErrorCode:
    if isinstance(exc, AizeeError):
        return _ERROR_CODE_MAP.get(type(exc).__name__, ToolErrorCode.INTERNAL)
    return _ERROR_CODE_MAP.get(type(exc).__name__, ToolErrorCode.INTERNAL)


def wrap(tool_name: str) -> Callable[[F], F]:
    """Decorator: wrap a tool function so it always returns the envelope.

    The wrapped function may return any JSON-serializable value or a dict;
    it lands in ``result``. Errors are caught and encoded with a stable
    ``error.code``.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                result = func(*args, **kwargs)
                return _ok(tool_name, result)
            except Exception as exc:
                return _err(tool_name, exc)

        return wrapper  # type: ignore[return-value]
    return decorator


def _ok(tool_name: str, result: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "tool": tool_name,
        "result": result,
        "error": None,
        "meta": _meta(),
    }


def _err(tool_name: str, exc: BaseException) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "tool": tool_name,
        "result": None,
        "error": {
            "code": _error_code(exc).value,
            "message": str(exc),
            "severity": getattr(exc, "severity", "error"),
        },
        "meta": _meta(),
    }


def _meta() -> dict[str, Any]:
    """Build meta block: cost snapshot + pending update notification."""
    meta: dict[str, Any] = {}
    update = _pending_update()
    if update:
        meta["update"] = update
    return meta


def _pending_update() -> dict[str, Any] | None:
    """Return update notification if ``state/update_available.json`` exists.

    Written by ``aizee update --check``; read-only here — no network calls.
    """
    try:
        from config import discover_root

        state_file = discover_root() / "state" / "update_available.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return {
                "available": True,
                "version": data.get("version", "unknown"),
                "command": "aizee update",
            }
    except Exception:
        pass
    return None


def ok_response(tool_name: str, result: Any) -> dict[str, Any]:
    """Build an envelope success response directly (no decorator)."""
    return _ok(tool_name, result)


def err_response(tool_name: str, exc: BaseException) -> dict[str, Any]:
    """Build an envelope error response directly (no decorator)."""
    return _err(tool_name, exc)
