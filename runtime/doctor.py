"""Structured diagnostics engine — verdict + ordered next steps.

Adopted from google/artemis `doctor` MCP tool semantics: every check produces
a machine-readable verdict (``ready``/``degraded``/``blocked``) plus ordered
``next_steps`` where automatable fixes carry a ``run`` command and manual
steps carry ``guidance`` text. Shared by ``aizee doctor --json`` (CLI) and the
``aizee_doctor`` MCP tool so agents get the same truth as operators.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Verdict(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    severity: str = "required"  # required | recommended | optional
    fix_run: str = ""
    fix_guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "ok": self.ok, "severity": self.severity}
        if not self.ok:
            if self.fix_run:
                d["fix"] = {"run": self.fix_run}
            elif self.fix_guidance:
                d["fix"] = {"guidance": self.fix_guidance}
        return d


@dataclass(frozen=True)
class DoctorReport:
    verdict: str
    checks: list[Check]
    next_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "checks": [c.to_dict() for c in self.checks],
            "next_steps": self.next_steps,
            "summary": {
                "total": len(self.checks),
                "ok": sum(1 for c in self.checks if c.ok),
                "failed": sum(1 for c in self.checks if not c.ok),
            },
        }


def run_doctor(os_root: Path, project_root: Path) -> DoctorReport:
    """Run all health checks and build the structured report."""
    checks = _collect_checks(os_root, project_root)
    verdict = _compute_verdict(checks)
    return DoctorReport(
        verdict=verdict.value,
        checks=checks,
        next_steps=_build_next_steps(checks),
    )


def _compute_verdict(checks: list[Check]) -> Verdict:
    required_failed = any(not c.ok and c.severity == "required" for c in checks)
    recommended_failed = any(not c.ok and c.severity == "recommended" for c in checks)
    if required_failed:
        return Verdict.BLOCKED
    if recommended_failed:
        return Verdict.DEGRADED
    return Verdict.READY


def _build_next_steps(checks: list[Check]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for c in checks:
        if c.ok:
            continue
        if c.fix_run:
            steps.append({"kind": "run", "command": c.fix_run, "reason": c.name})
        elif c.fix_guidance:
            steps.append({"kind": "guidance", "text": c.fix_guidance, "reason": c.name})
    return steps


def _collect_checks(os_root: Path, project_root: Path) -> list[Check]:
    checks: list[Check] = []
    _fs_checks(checks, os_root, project_root)
    _module_checks(checks, os_root)
    _dep_checks(checks)
    _runtime_checks(checks, os_root, project_root)
    return checks


def _fs_checks(checks: list[Check], os_root: Path, project_root: Path) -> None:
    fs = [
        ("os root", os_root.exists(), "required", "", "Set AIZEE_ROOT to the aiZee root directory"),
        ("project root", project_root.exists(), "required", "", "Create the project directory"),
        ("pyproject.toml", (os_root / "pyproject.toml").exists(), "required", "", "Install aiZee: pip install -e ."),
        ("os policies", (os_root / "runtime" / "policies" / "default.yaml").exists(), "required", "aizee bootstrap", ""),
        ("project policies", (project_root / "runtime" / "policies" / "default.yaml").exists(), "recommended", "aizee bootstrap", ""),
        ("rules directory", (os_root / "rules").exists(), "recommended", "", "Run aiZee installer to restore rules/"),
        ("workflows directory", (os_root / "workflows").exists(), "recommended", "", "Run aiZee installer to restore workflows/"),
        ("tech-stack directory", (os_root / "tech-stack").exists(), "recommended", "", "Run aiZee installer to restore tech-stack/"),
        ("state directory", (project_root / "state").exists(), "recommended", "aizee bootstrap", ""),
        ("brain directory", (project_root / "brain").exists(), "optional", "aizee bootstrap", ""),
        ("LICENSE", (os_root / "LICENSE").exists(), "optional", "", "Restore LICENSE from the repository"),
        ("CODEOWNERS", (os_root / ".github" / "CODEOWNERS").exists(), "optional", "", "Restore .github/CODEOWNERS"),
        ("API.md", (os_root / "aizee_mcp" / "API.md").exists(), "optional", "", "Restore aizee_mcp/API.md"),
        ("env example", (os_root / ".env.example").exists(), "optional", "", "Restore .env.example"),
        ("vibe scenarios", (os_root / "eval" / "scenarios").is_dir(), "optional", "", "Restore eval/scenarios/"),
    ]
    for name, ok, sev, run, guide in fs:
        checks.append(Check(name, ok, sev, run, guide))


def _module_checks(checks: list[Check], os_root: Path) -> None:
    modules = [
        ("managers module", os_root / "runtime" / "managers", True),
        ("mcp tools module", os_root / "aizee_mcp" / "tools", True),
        ("crypto module", os_root / "runtime" / "crypto.py", False),
        ("migrations module", os_root / "runtime" / "migrations.py", False),
        ("telemetry module", os_root / "runtime" / "telemetry.py", False),
        ("mcp firewall", os_root / "runtime" / "mcp_firewall.py", False),
        ("mcp firewall policy", os_root / "runtime" / "policies" / "mcp_firewall.yaml", False),
        ("loop detector", os_root / "runtime" / "loop_detector.py", False),
        ("prompt gate", os_root / "runtime" / "prompt_gate.py", False),
        ("approval service", os_root / "runtime" / "approval_service.py", False),
        ("agent discovery", os_root / "runtime" / "agent_discovery.py", False),
        ("guard invariants", os_root / "scripts" / "guard_invariants.py", False),
        ("doctor module", os_root / "runtime" / "doctor.py", False),
        ("verification module", os_root / "runtime" / "verification.py", False),
        ("output filter", os_root / "runtime" / "output_filter.py", False),
        ("gateway proxy", os_root / "runtime" / "gateway_proxy.py", False),
    ]
    for name, path, is_dir in modules:
        ok = path.is_dir() if is_dir else path.exists()
        checks.append(Check(name, ok, "required", "", f"Restore {name} from the aiZee repository"))


def _dep_checks(checks: list[Check]) -> None:
    for pkg in ("yaml", "mcp", "pydantic", "rich", "cryptography"):
        try:
            __import__(pkg)
            checks.append(Check(f"pip: {pkg}", True))
        except ImportError:
            checks.append(Check(
                f"pip: {pkg}", False, "required",
                "pip install -e .", "",
            ))
    try:
        from importlib.metadata import version

        installed = version("cryptography")
        checks.append(Check(f"cryptography=={installed}", True, "optional"))
    except Exception:
        checks.append(Check("cryptography version", False, "optional", "", "pip install cryptography>=42,<52"))


def _runtime_checks(checks: list[Check], os_root: Path, project_root: Path) -> None:
    checks.append(_version_check(os_root))
    checks.append(_encryption_check())
    checks.extend(_vector_check(project_root))
    checks.extend(_mcp_config_check())
    checks.extend(_policy_checks(os_root))
    checks.extend(_capability_check())
    checks.extend(_tech_stack_check(os_root, project_root))


def _version_check(os_root: Path) -> Check:
    vf = os_root / ".aizee-version"
    if vf.exists():
        ver = vf.read_text(encoding="utf-8").strip()
        return Check(f"installed version ({ver})", True)
    return Check("installed version", False, "recommended", "aizee bootstrap", "")


def _encryption_check() -> Check:
    if not os.environ.get("AIOS_ENCRYPTION_KEY"):
        return Check(
            "encryption key set", False, "recommended", "",
            "Set AIOS_ENCRYPTION_KEY env var for memory encryption",
        )
    try:
        from runtime.crypto import _get_fernet

        ok = _get_fernet() is not None
        return Check("encryption fernet valid", ok, "recommended", "",
                     "Verify AIOS_ENCRYPTION_KEY is a valid Fernet key")
    except Exception:
        return Check("encryption fernet valid", False, "recommended", "",
                     "Check cryptography installation and key format")


def _vector_check(project_root: Path) -> list[Check]:
    try:
        from memory.vector import VectorMemory

        vector = VectorMemory(project_root)
        return [Check("vector index", vector.is_available(), "optional",
                      "aizee memory index", "")]
    except Exception:
        return [Check("vector index", False, "optional", "aizee memory index", "")]


def _mcp_config_check() -> list[Check]:
    try:
        if os.name == "nt":
            g_dir = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "devin"
        else:
            g_dir = Path.home() / ".config" / "devin"
        g_cfg = g_dir / "mcp_config.json"
        if g_cfg.exists():
            import json

            g_data = json.loads(g_cfg.read_text(encoding="utf-8"))
            g_count = len(g_data.get("mcpServers", {}))
            return [Check(f"global mcp config ({g_count} servers)", g_count > 0, "recommended",
                          "aizee mcp install", "")]
        return [Check("global mcp config", False, "recommended", "aizee mcp install", "")]
    except Exception:
        return [Check("global mcp config", False, "recommended", "aizee mcp install", "")]


def _policy_checks(os_root: Path) -> list[Check]:
    results: list[Check] = []
    guardian_path = os_root / "runtime" / "policies" / "guardian.yaml"
    if guardian_path.exists():
        try:
            from runtime.guardian import Guardian

            g = Guardian.from_yaml(guardian_path)
            results.append(Check(f"guardian.yaml ({len(g.rules)} rules)", len(g.rules) > 0))
        except Exception:
            results.append(Check("guardian.yaml (load error)", False, "required", "",
                                 "Fix guardian.yaml syntax or restore from repository"))
    else:
        results.append(Check("guardian.yaml", False, "required", "aizee bootstrap", ""))
    probity_path = os_root / "runtime" / "policies" / "probity.yaml"
    if probity_path.exists():
        try:
            import yaml as _yaml

            from runtime.probity import Guardrails

            data = _yaml.safe_load(probity_path.read_text(encoding="utf-8")) or {}
            gr = Guardrails(data)
            results.append(Check(f"probity.yaml ({len(gr.rules)} rules)", len(gr.rules) > 0))
        except Exception:
            results.append(Check("probity.yaml (load error)", False, "required", "",
                                 "Fix probity.yaml syntax or restore from repository"))
    else:
        results.append(Check("probity.yaml", False, "required", "aizee bootstrap", ""))
    return results


def _capability_check() -> list[Check]:
    try:
        from runtime.sovereign import AgentCapabilities

        caps = AgentCapabilities()
        return [Check(f"capabilities ({len(caps.list())})", len(caps.list()) > 0)]
    except Exception:
        return [Check("capabilities", False, "recommended", "", "Check runtime/sovereign.py")]


def _tech_stack_check(os_root: Path, project_root: Path) -> list[Check]:
    try:
        from runtime.kernel import Kernel

        k = Kernel(os_root, project_root)
        ts = k.detect_tech_stack()
        return [Check(f"tech_stack detection ({len(ts)} entries)", len(ts) > 0,
                      "optional", "", "Check kernel.detect_tech_stack()")]
    except Exception:
        return [Check("tech_stack detection", False, "optional", "",
                      "Check kernel.detect_tech_stack()")]
