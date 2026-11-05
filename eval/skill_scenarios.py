#!/usr/bin/env python3
"""Skill behavioral scenario runner - EGM-style evals for skills/workflows.

Schema (adapted from google/elephant-goldfish-model's test_scenarios.yaml,
Apache-2.0):

    scenarios:
      - scenario_id: goldfish_plans_before_spawning
        description: workflow must plan before review
        eval_type: static | live
        system_prompt:
          skill_file: workflows/65-goldfish-review.md
        turns:
          - user_input: "Review my design doc"
            assertions:
              - type: required_pattern | forbidden_pattern
                pattern: "semantic split"
                message: "expected ..."

Modes:
  static — assertions checked against the skill file text (protocol lint,
           no LLM, deterministic, always runnable).
  live   — assertions checked against the agent's response via an
           OpenAI-compatible endpoint (AIZEE_EVAL_ENDPOINT / --endpoint).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_LIVE_ENV_ENDPOINT = "AIZEE_EVAL_ENDPOINT"
_LIVE_ENV_MODEL = "AIZEE_EVAL_MODEL"
_MAX_FILE_BYTES = 500_000
_MAX_ASSERTION_TEXT = 1_000_000


@dataclass
class Assertion:
    type: str  # required_pattern | forbidden_pattern
    pattern: str
    message: str = ""


@dataclass
class Turn:
    user_input: str
    assertions: list[Assertion] = field(default_factory=list)


@dataclass
class Scenario:
    scenario_id: str
    description: str
    eval_type: str  # static | live
    skill_file: str
    turns: list[Turn] = field(default_factory=list)


@dataclass
class CheckResult:
    scenario_id: str
    eval_type: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    skipped: bool = False
    reason: str = ""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = path.read_bytes()[:_MAX_FILE_BYTES]
    raw = yaml.safe_load(data.decode("utf-8", errors="replace"))
    if not isinstance(raw, dict) or "scenarios" not in raw:
        raise ValueError(f"not a scenarios file: {path}")
    return raw


def _parse_assertions(items: Any) -> list[Assertion]:
    out: list[Assertion] = []
    for a in items or []:
        if isinstance(a, dict) and a.get("pattern"):
            out.append(Assertion(type=str(a.get("type", "required_pattern")),
                                 pattern=str(a["pattern"]), message=str(a.get("message", ""))))
    return out


def load_scenarios(path: Path) -> list[Scenario]:
    raw = _load_yaml(path)
    scenarios: list[Scenario] = []
    for entry in raw["scenarios"]:
        if not isinstance(entry, dict):
            continue
        sys_prompt = entry.get("system_prompt") or {}
        turns = [Turn(user_input=str(t.get("user_input", "")),
                      assertions=_parse_assertions(t.get("assertions")))
                 for t in entry.get("turns") or [] if isinstance(t, dict)]
        scenarios.append(Scenario(
            scenario_id=str(entry.get("scenario_id", entry.get("name", "unnamed"))),
            description=str(entry.get("description", "")),
            eval_type=str(entry.get("eval_type", "static")),
            skill_file=str(sys_prompt.get("skill_file", "")),
            turns=turns,
        ))
    return scenarios


def _apply_assertions(text: str, assertions: list[Assertion]) -> list[str]:
    text = text[:_MAX_ASSERTION_TEXT]
    failures: list[str] = []
    for a in assertions:
        hit = re.search(a.pattern, text, re.IGNORECASE | re.DOTALL) is not None
        if a.type == "required_pattern" and not hit:
            failures.append(a.message or f"missing required pattern: {a.pattern!r}")
        elif a.type == "forbidden_pattern" and hit:
            failures.append(a.message or f"forbidden pattern present: {a.pattern!r}")
    return failures


def run_static(scenario: Scenario, root: Path) -> CheckResult:
    target = root / scenario.skill_file if scenario.skill_file else None
    if target is None or not target.exists():
        return CheckResult(scenario.scenario_id, "static", False,
                           skipped=True, reason=f"skill_file missing: {scenario.skill_file}")
    text = target.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    for turn in scenario.turns:
        failures.extend(_apply_assertions(text, turn.assertions))
    return CheckResult(scenario.scenario_id, "static", not failures, failures)


def _live_request(endpoint: str, model: str, skill_text: str, user_input: str, timeout: float = 60.0) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": skill_text},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    choices = body.get("choices") or []
    return str(choices[0].get("message", {}).get("content", "")) if choices else ""


def run_live(scenario: Scenario, root: Path, endpoint: str, model: str,
             timeout: float = 60.0) -> CheckResult:
    target = root / scenario.skill_file if scenario.skill_file else None
    if target is None or not target.exists():
        return CheckResult(scenario.scenario_id, "live", False,
                           skipped=True, reason=f"skill_file missing: {scenario.skill_file}")
    skill_text = target.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    for turn in scenario.turns:
        try:
            reply = _live_request(endpoint, model, skill_text, turn.user_input, timeout)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            return CheckResult(scenario.scenario_id, "live", False,
                               skipped=True, reason=f"endpoint unreachable: {exc}")
        failures.extend(_apply_assertions(reply, turn.assertions))
    return CheckResult(scenario.scenario_id, "live", not failures, failures)


def run_file(path: Path, root: Path, *, live: bool = False, endpoint: str = "",
             model: str = "", timeout: float = 60.0) -> list[CheckResult]:
    """Run every scenario in a file. `live` forces live mode for live-type scenarios."""
    ep = endpoint or os.environ.get(_LIVE_ENV_ENDPOINT, "")
    md = model or os.environ.get(_LIVE_ENV_MODEL, "")
    results: list[CheckResult] = []
    for sc in load_scenarios(path):
        if live or sc.eval_type == "live":
            if not ep or not md:
                results.append(CheckResult(sc.scenario_id, "live", False, skipped=True,
                                           reason="no endpoint/model (AIZEE_EVAL_ENDPOINT / AIZEE_EVAL_MODEL)"))
                continue
            results.append(run_live(sc, root, ep, md, timeout))
        else:
            results.append(run_static(sc, root))
    return results


def run_dir(dir_path: Path, root: Path, **kwargs: Any) -> list[CheckResult]:
    results: list[CheckResult] = []
    for p in sorted(dir_path.glob("*.yaml")) + sorted(dir_path.glob("*.yml")):
        try:
            results.extend(run_file(p, root, **kwargs))
        except ValueError:
            continue  # legacy-format files are not scenario-runner targets
    return results


def format_results(results: list[CheckResult]) -> dict[str, Any]:
    passed = sum(1 for r in results if r.passed)
    skipped = sum(1 for r in results if r.skipped)
    return {
        "total": len(results), "passed": passed, "failed": len(results) - passed - skipped,
        "skipped": skipped,
        "results": [{"id": r.scenario_id, "type": r.eval_type, "passed": r.passed,
                     "skipped": r.skipped, "failures": r.failures, "reason": r.reason}
                    for r in results],
    }


if __name__ == "__main__":  # `python eval/skill_scenarios.py <file|dir> [--live]`
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run skill behavioral scenarios")
    parser.add_argument("path", nargs="?", default="eval/scenarios")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=float, default=60.0)
    ns = parser.parse_args()
    root_dir = Path(__file__).resolve().parent.parent
    target = Path(ns.path)
    if not target.is_absolute():
        target = root_dir / target
    kw: dict[str, Any] = {"live": ns.live, "endpoint": ns.endpoint,
                          "model": ns.model, "timeout": ns.timeout}
    out = run_file(target, root_dir, **kw) if target.is_file() else run_dir(target, root_dir, **kw)
    rep = format_results(out)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    sys.exit(0 if rep["failed"] == 0 else 1)
