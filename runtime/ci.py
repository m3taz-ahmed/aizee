"""CI pipeline runner for aiZee quality gates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DEFAULT_TIMEOUT = 300


def run_command(cmd: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str]:
    if not cwd.is_dir():
        return 1, f"Invalid cwd (not a directory): {cwd}"
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout}s: {cmd}"
    except FileNotFoundError as exc:
        return 1, f"Command not found: {exc}"
    except (OSError, PermissionError) as exc:
        return 1, f"Command failed: {exc}"


class CIPipeline:
    """Runs the standard aiZee quality gates."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.results: list[dict[str, object]] = []

    def run(self, skip_pytest: bool = False) -> int:
        self.results = []
        all_ok = True

        checks: list[tuple[str, list[str], int]] = [
            ("ruff", [sys.executable, "-m", "ruff", "check", "."], 300),
            (
                "mypy",
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "runtime",
                    "memory",
                    "aizee_mcp",
                    "aizee_cli.py",
                    "config.py",
                    "dashboard/server.py",
                    "eval/harness.py",
                    "eval/pipeline.py",
                    "eval/reliability.py",
                    "eval/redteam.py",
                    "scripts/guard_invariants.py",
                    "scripts/sync_docs.py",
                ],
                600,
            ),
        ]
        if not skip_pytest:
            # Fast tier via the canonical runner — same deselection + xdist
            # logic as `aizee test` so CI can never drift from local runs.
            checks.append(("pytest", [sys.executable, str(self.root / "aizee_cli.py"), "test"], 900))
        checks.append(("validate-globals", [sys.executable, "scripts/validate-globals.py"], 180))
        # P1.7: reliability release gate — skips cleanly when no rollout
        # evidence exists, fails on KILL/INSUFFICIENT ladder verdicts.
        checks.append(("release-gate", [sys.executable, "eval/release_gate.py", "--project", str(self.root)], 180))

        for name, cmd, timeout in checks:
            code, output = run_command(cmd, self.root, timeout)
            ok = code == 0
            self.results.append({"name": name, "ok": ok, "output": output})
            if not ok:
                all_ok = False

        return 0 if all_ok else 1

    def report(self) -> dict[str, object]:
        if not self.results:
            return {
                "ok": False,
                "reason": "no runs recorded",
                "results": self.results,
            }
        return {
            "ok": all(r["ok"] for r in self.results),
            "results": self.results,
        }
