#!/usr/bin/env python3
"""Coverage-gap tests for adopted modules (batch 3).

Closes the last uncovered branches so the FULL tier's 100% gate holds.
Each test targets a specific line/branch reported by coverage.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest


def _full_os_root(tmp_path: Path) -> Path:
    """Build a fake OS root passing every *required* doctor check."""
    os_root = tmp_path / "os"
    for rel in (
        "pyproject.toml",
        "runtime/crypto.py",
        "runtime/migrations.py",
        "runtime/telemetry.py",
        "runtime/mcp_firewall.py",
        "runtime/loop_detector.py",
        "runtime/prompt_gate.py",
        "runtime/approval_service.py",
        "runtime/agent_discovery.py",
        "runtime/doctor.py",
        "runtime/verification.py",
        "runtime/output_filter.py",
        "runtime/gateway_proxy.py",
        "runtime/policies/default.yaml",
        "runtime/policies/mcp_firewall.yaml",
        "scripts/guard_invariants.py",
        "aizee_mcp/API.md",
    ):
        p = os_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    for d in ("runtime/managers", "aizee_mcp/tools"):
        (os_root / d).mkdir(parents=True, exist_ok=True)
    (os_root / "runtime" / "policies" / "guardian.yaml").write_text(
        "rules:\n  - name: deny-x\n    tool: Bash\n"
        "    any:\n      - {key: 'args.command', op: 'contains', value: 'zz'}\n",
        encoding="utf-8",
    )
    (os_root / "runtime" / "policies" / "probity.yaml").write_text(
        "rules:\n  - kind: forbidCommandPattern\n    name: block-x\n"
        "    pattern: 'zz'\n    message: 'no'\n",
        encoding="utf-8",
    )
    return os_root


class TestDoctorVerdictBranches:
    def test_ready_verdict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.doctor import Verdict, run_doctor

        os_root = _full_os_root(tmp_path)
        proj = tmp_path / "proj"
        proj.mkdir()
        (os_root / ".aizee-version").write_text("9.9.9", encoding="utf-8")
        for d in ("rules", "workflows", "tech-stack", "eval/scenarios"):
            (os_root / d).mkdir(parents=True, exist_ok=True)
        for f in ("LICENSE", ".github/CODEOWNERS", ".env.example"):
            (os_root / f).parent.mkdir(parents=True, exist_ok=True)
            (os_root / f).write_text("x", encoding="utf-8")
        (proj / "state").mkdir()
        (proj / "brain").mkdir()
        (proj / "runtime" / "policies").mkdir(parents=True)
        (proj / "runtime" / "policies" / "default.yaml").write_text("x", encoding="utf-8")
        monkeypatch.setenv("AIOS_ENCRYPTION_KEY", "k")
        import runtime.crypto as crypto

        monkeypatch.setattr(crypto, "_get_fernet", lambda: object())
        monkeypatch.setenv("APPDATA", str(tmp_path))
        (tmp_path / "devin").mkdir()
        (tmp_path / "devin" / "mcp_config.json").write_text(
            '{"mcpServers": {"aizee": {}}}', encoding="utf-8"
        )
        report = run_doctor(os_root, proj)
        required_failed = [
            c.name for c in report.checks if not c.ok and c.severity == "required"
        ]
        assert not required_failed, required_failed
        assert report.verdict in (Verdict.READY.value, Verdict.DEGRADED.value)

    def test_blocked_and_guidance_steps(self, tmp_path: Path) -> None:
        from runtime.doctor import run_doctor

        report = run_doctor(tmp_path / "os", tmp_path / "proj")
        assert report.verdict == "blocked"
        kinds = {s["kind"] for s in report.next_steps}
        assert "run" in kinds and "guidance" in kinds

    def test_verdict_and_step_builders_directly(self) -> None:
        from runtime.doctor import Check, Verdict, _build_next_steps, _compute_verdict

        assert _compute_verdict([Check("a", True)]) == Verdict.READY
        degraded = _compute_verdict([Check("a", False, "recommended")])
        assert degraded.value == "degraded"
        blocked = _compute_verdict([Check("a", False, "required")])
        assert blocked.value == "blocked"
        c = Check("x", False, fix_guidance="do it")
        assert c.to_dict()["fix"] == {"guidance": "do it"}
        assert "fix" not in Check("b", False).to_dict()
        assert "fix" not in Check("ok", True).to_dict()
        steps = _build_next_steps([
            Check("ok1", True),
            Check("g", False, fix_guidance="hint"),
            Check("r", False, fix_run="aizee fix"),
            Check("bare", False),
        ])
        assert [s["kind"] for s in steps] == ["guidance", "run"]

    def test_crypto_version_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib.metadata

        import runtime.doctor as d

        monkeypatch.setattr(
            importlib.metadata, "version",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no dist")),
        )
        lst: list[Any] = []
        d._dep_checks(lst)
        assert any(c.name == "cryptography version" and not c.ok for c in lst)

    def test_encryption_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import runtime.doctor as d

        monkeypatch.delenv("AIOS_ENCRYPTION_KEY", raising=False)
        c = d._encryption_check()
        assert not c.ok and c.name == "encryption key set"
        monkeypatch.setenv("AIOS_ENCRYPTION_KEY", "k")
        import runtime.crypto as crypto

        monkeypatch.setattr(crypto, "_get_fernet", lambda: object())
        assert d._encryption_check().ok
        monkeypatch.setattr(
            crypto, "_get_fernet",
            lambda: (_ for _ in ()).throw(RuntimeError("bad key")),
        )
        assert not d._encryption_check().ok

    def test_mcp_config_posix_and_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runtime.doctor as d

        monkeypatch.setattr(d.os, "name", "posix")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        out = d._mcp_config_check()
        assert out and not out[0].ok and out[0].fix_run == "aizee mcp install"

    def test_mcp_config_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import runtime.doctor as d

        monkeypatch.setattr(
            Path, "exists",
            lambda self: (_ for _ in ()).throw(RuntimeError("io")),
        )
        out = d._mcp_config_check()
        assert not out[0].ok

    def test_guardian_load_error_and_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runtime.doctor as d

        os_root = tmp_path / "os"
        pol = os_root / "runtime" / "policies"
        pol.mkdir(parents=True)
        (pol / "guardian.yaml").write_text("{invalid: [", encoding="utf-8")
        (pol / "probity.yaml").write_text("{invalid: [", encoding="utf-8")
        out = d._policy_checks(os_root)
        assert any("load error" in c.name for c in out)
        out2 = d._policy_checks(tmp_path / "empty")
        assert all(c.fix_run == "aizee bootstrap" for c in out2)

    def test_capability_and_techstack_exceptions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runtime.doctor as d
        import runtime.kernel as kmod
        import runtime.sovereign as sov

        monkeypatch.setattr(
            sov, "AgentCapabilities",
            lambda: (_ for _ in ()).throw(RuntimeError("caps")),
        )
        assert not d._capability_check()[0].ok
        monkeypatch.setattr(
            kmod, "Kernel",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kernel")),
        )
        assert not d._tech_stack_check(tmp_path, tmp_path)[0].ok


class TestFindGaps2:
    def test_trigger_scoring(self) -> None:
        from runtime.find import _score
        from runtime.service_catalog import ServiceDescriptor

        desc = ServiceDescriptor(
            name="other", kind="skill",
            triggers=frozenset({"react-component"}),
        )
        score, matched = _score(desc, ["react"])
        assert score > 0 and "react" in matched

    def test_non_step_lines_inside_section(self, tmp_path: Path) -> None:
        from runtime.find import _extract_workflow_steps

        wf = tmp_path / "w.md"
        wf.write_text(
            "intro line\n## Steps\nnot-a-step line\n1. real step\n\nmore text\n## Done\n",
            encoding="utf-8",
        )
        assert _extract_workflow_steps(wf) == ["real step"]


class TestOutputFilterGaps:
    def test_empty_input_ratio(self) -> None:
        from runtime.output_filter import filter_output

        _, stats = filter_output("")
        assert stats.compression_ratio == 0.0

    def test_consecutive_blanks_collapse(self) -> None:
        from runtime.output_filter import filter_output

        _, stats = filter_output("a\n\n\n\nb\n")
        assert stats.collapsed_groups >= 1
        text, stats2 = filter_output("x\n" + "y\n" * 500, max_lines=5)
        assert "more lines truncated" in text
        assert stats2.compression_ratio >= 0.0


class TestVerificationGap:
    def test_strict_clean_diff_returns_none(self, tmp_path: Path) -> None:
        from runtime.verification import VerificationLevel, run_verification

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname="x"\ndependencies=[]\n', encoding="utf-8"
        )
        data = {"diff": "--- a/m.py\n+++ b/m.py\n+print(1)\n"}
        assert run_verification(
            VerificationLevel.STRICT, "Edit", data, tmp_path
        ) is None


class TestChangesGaps:
    def _engine(self, tmp_path: Path) -> Any:
        from runtime.spec.engine import SpecEngine

        e = SpecEngine.__new__(SpecEngine)
        e.specs_dir = tmp_path / "specs"
        return e

    def test_change_info_to_dict_and_no_tasks(self, tmp_path: Path) -> None:
        e = self._engine(tmp_path)
        d = e.changes_dir / "my-change"
        d.mkdir(parents=True)
        (d / "proposal.md").write_text("# why", encoding="utf-8")
        infos = e.list_changes()
        assert infos[0].to_dict()["has_proposal"] is True
        assert infos[0].to_dict()["tasks"] == {"done": 0, "total": 0}


class TestKernelVerifyPass:
    def test_checkpoints_clean_diff_passes(self, tmp_path: Path) -> None:
        from runtime.kernel import Kernel

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        result = k.act(
            "Read", verify="checkpoints",
            diff="--- a/src/x.py\n+++ b/src/x.py\n+print(1)\n",
        )
        assert result.get("violation") is None

    def test_verify_none_and_final_skip(self, tmp_path: Path) -> None:
        from runtime.kernel import Kernel

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        out = k.act("Read", diff="--- a/x\n+++ b/.env\n+S=1\n")
        assert out.get("violation") is None
        out2 = k.act("Read", verify="final", diff="--- a/x\n+++ b/.env\n+S=1\n")
        assert out2.get("violation") is None

    def test_verify_survives_middleware_path(self, tmp_path: Path) -> None:
        """The verify dial must not be dropped when a middleware is registered."""
        from runtime.kernel import Kernel

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        k.use_middleware(lambda ctx, nxt: nxt())
        result = k.act("Read", verify="checkpoints", diff="--- a/x\n+++ b/.env\n+S=1\n")
        assert result.get("ok") is False
        assert result.get("violation") == "plan_diff"


class TestConfigOpsGap:
    def test_added_key_in_diff(self) -> None:
        from runtime.config_ops import _diff

        assert _diff({"a": 1}, {"a": 1, "b": 2}) == {"b": {"added": 2}}


class TestGatewayGaps2:
    def test_verify_true_maps_strict(self, tmp_path: Path) -> None:
        import runtime.gateway_proxy as gp

        cfg = tmp_path / "gateway.yaml"
        cfg.write_text("verify: on\nproviders: []\n", encoding="utf-8")
        assert gp.GatewayConfig.load(cfg).verify == "strict"

    def test_estimate_and_extract_edges(self) -> None:
        import runtime.gateway_proxy as gp

        payload = {
            "messages": [{"content": [{"text": "abcd"}, 5, {"text": "efgh"}]}],
            "prompt": 12345,
        }
        assert gp.estimate_tokens(payload) >= 1
        text = gp.extract_prompt_text(
            {"messages": [{"content": ["x"]}, {"content": [{"text": "y"}]}],
             "prompt": 9}
        )
        assert "y" in text
        # Non-str, non-list content is skipped by both helpers.
        odd = {"messages": [{"content": 123}], "prompt": "p"}
        assert gp.estimate_tokens(odd) >= 1
        assert gp.extract_prompt_text(odd) == "p"

    def test_forward_no_api_key_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        import runtime.gateway_proxy as gp

        class Resp:
            status = 200
            headers: ClassVar[dict[str, str]] = {}

            def read(self) -> bytes:
                return b"{}"

            def __enter__(self) -> Any:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
        monkeypatch.delenv("MISSING_KEY", raising=False)
        p = gp.Provider(
            name="a", base_url="http://x", kind="openai", api_key_env="MISSING_KEY"
        )
        status, _, _ = gp.forward(p, "/v1/chat", b"{}", {})
        assert status == 200

    def test_gate_allow_and_deny(self) -> None:
        from unittest.mock import MagicMock

        import runtime.gateway_proxy as gp

        kernel = MagicMock()
        kernel.act.return_value = {"ok": False, "reason": "nope"}
        cfg = gp.GatewayConfig(providers=(), verify="off")
        handler_cls = gp.make_handler(cfg, kernel)
        req = handler_cls.__new__(handler_cls)
        req.rfile = io.BytesIO(b"")  # type: ignore[attr-defined]
        decision = req._gate({"messages": [{"content": "hi"}]})
        assert decision is not None and decision["error"]["code"] == "POLICY_DENIED"
        kernel.act.return_value = {"ok": True}
        assert req._gate({"messages": [{"content": "hi"}]}) is None
        # kernel=None -> gate is a pass-through.
        handler_cls2 = gp.make_handler(cfg, None)
        req2 = handler_cls2.__new__(handler_cls2)
        assert req2._gate({}) is None


class TestDoctorToolsGap:
    def test_goal_error_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        tools: dict[str, Any] = {}

        class CaptureMCP:
            def tool(self) -> Any:
                def deco(fn: Any) -> Any:
                    tools[fn.__name__] = fn
                    return fn
                return deco

        dt.register_doctor_tools(CaptureMCP())
        monkeypatch.setattr(
            dt, "nl_goal",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("goal boom")),
        )
        monkeypatch.setattr(dt, "root", lambda: Path("/x"))
        monkeypatch.setattr(
            dt, "kernel",
            lambda: type("K", (), {"project_root": Path("/x")})(),
        )
        out = json.loads(tools["aizee_goal"]("x"))
        assert out["ok"] is False and out["error"]["code"] == "INTERNAL"


class TestServerFilterResidual:
    def test_uncompressible_large_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.aizee_server as srv

        kernel = MagicMock()
        # >8000 chars in <=200 unique non-repeat lines -> nothing compressible.
        text = "".join(f"u{i:03d}" + "x" * 290 + "\n" for i in range(30))
        kernel.check_tool_result.return_value = (True, text)
        monkeypatch.setattr(srv, "kernel", lambda: kernel)
        monkeypatch.setenv("AIZEE_OUTPUT_FILTER", "1")
        out = srv._gateway_post_check("t", text)
        assert out == text  # nothing saved -> original returned

    def test_non_str_result_filters_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.aizee_server as srv

        kernel = MagicMock()
        result = {"data": "====\n" * 3000}
        kernel.check_tool_result.return_value = (
            True, json.dumps(result),
        )
        monkeypatch.setattr(srv, "kernel", lambda: kernel)
        monkeypatch.setenv("AIZEE_OUTPUT_FILTER", "1")
        out = srv._gateway_post_check("t", result)
        assert out == result  # non-str results keep original object

    def test_filter_exception_degrades(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.aizee_server as srv
        import runtime.output_filter as of

        kernel = MagicMock()
        text = "x\n" + "====\n" * 3000
        kernel.check_tool_result.return_value = (True, text)
        monkeypatch.setattr(srv, "kernel", lambda: kernel)
        monkeypatch.setenv("AIZEE_OUTPUT_FILTER", "1")
        monkeypatch.setattr(
            of, "filter_output",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("f")),
        )
        assert srv._gateway_post_check("t", text) == text


class TestIngestRulesGaps:
    def _ingestor(self, tmp_path: Path, rules_yaml: str) -> Any:
        from unittest.mock import MagicMock

        from memory.ingest import Ingestor

        (tmp_path / "rules").mkdir(parents=True)
        (tmp_path / "rules" / "ingest.yaml").write_text(rules_yaml, encoding="utf-8")
        return Ingestor(MagicMock(), root=tmp_path)

    def test_rule_match_directory_skipped(self, tmp_path: Path) -> None:
        ing = self._ingestor(
            tmp_path, "rules:\n  - match: 'docs/*'\n    kind: note\n"
        )
        (tmp_path / "docs" / "subdir").mkdir(parents=True)
        (tmp_path / "docs" / "f.md").write_text("plain text", encoding="utf-8")
        added, _sigs, sources = ing._collect_rules({})
        assert len(added) == 1 and "docs/f.md" in sources

    def test_rule_validate_reject_skipped(self, tmp_path: Path) -> None:
        ing = self._ingestor(
            tmp_path, "rules:\n  - match: 'notes/*.md'\n    kind: note\n"
        )
        notes = tmp_path / "notes"
        notes.mkdir()
        # AI-tagged but malformed -> _validate() False -> skipped.
        (notes / "bad.md").write_text("[FILE] broken\nno sections\n", encoding="utf-8")
        with pytest.warns(UserWarning):
            added, _sigs, sources = ing._collect_rules({})
        assert not added and not sources

    def test_rule_manifest_hit_skipped(self, tmp_path: Path) -> None:
        ing = self._ingestor(
            tmp_path, "rules:\n  - match: 'notes/*.md'\n    kind: note\n"
        )
        notes = tmp_path / "notes"
        notes.mkdir()
        (notes / "same.md").write_text("plain", encoding="utf-8")
        sig = ing._sig("plain")
        added, _sigs, sources = ing._collect_rules({"notes/same.md": sig})
        assert not added and sources == {"notes/same.md"}
