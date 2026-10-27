#!/usr/bin/env python3
"""Diagnostics + discovery MCP tools with the uniform response envelope.

Adopted from google/artemis (``mobile_diagnose``) + Panniantong/Agent-Reach
(stable envelope + error codes): ``aizee_doctor`` returns a structured
verdict and ordered ``next_steps`` with ``run``/``guidance`` entries so an
agent can self-repair. ``aizee_find``/``aizee_goal`` expose the NL catalog
discovery added in runtime/find.py.
"""

from __future__ import annotations

import json
import logging

from aizee_mcp._compat import FastMCP
from runtime.doctor import run_doctor
from runtime.find import find as nl_find
from runtime.find import goal as nl_goal
from runtime.tool_envelope import err_response, ok_response

from .common import kernel, root

_logger = logging.getLogger(__name__)

TOOL_DOCTOR = "aizee_doctor"
TOOL_FIND = "aizee_find"
TOOL_GOAL = "aizee_goal"


def register_doctor_tools(mcp: FastMCP) -> None:
    """Register diagnostics and discovery tools."""

    @mcp.tool()
    def aizee_doctor() -> str:
        """Check aiZee health: verdict (ready/degraded/blocked) + ordered fix steps."""
        try:
            report = run_doctor(root(), kernel().project_root)
            return json.dumps(ok_response(TOOL_DOCTOR, report.to_dict()), indent=2, default=str)
        except Exception as exc:
            _logger.warning("doctor failed: %s", exc)
            return json.dumps(err_response(TOOL_DOCTOR, exc), indent=2, default=str)

    @mcp.tool()
    def aizee_find(query: str, limit: int = 10) -> str:
        """Find skills, workflows, and tech-stack entries matching a natural-language need."""
        try:
            results = nl_find(query, root(), limit=limit)
            return json.dumps(
                ok_response(TOOL_FIND, {"query": query, "items": [r.to_dict() for r in results]}),
                indent=2, default=str,
            )
        except Exception as exc:
            _logger.warning("find failed: %s", exc)
            return json.dumps(err_response(TOOL_FIND, exc), indent=2, default=str)

    @mcp.tool()
    def aizee_goal(objective: str) -> str:
        """Map an objective to the best-matching workflow and its step list."""
        try:
            result = nl_goal(objective, root(), kernel().project_root)
            return json.dumps(ok_response(TOOL_GOAL, result.to_dict()), indent=2, default=str)
        except Exception as exc:
            _logger.warning("goal failed: %s", exc)
            return json.dumps(err_response(TOOL_GOAL, exc), indent=2, default=str)


# Alias for auto-discovery preference.
register = register_doctor_tools
