"""Coverage-completion tests for the star-repos adoption modules (batch 2).

Targets every uncovered line/branch in verification, doctor, tool_envelope,
find, output_filter, gateway_proxy, ingest_rules, config_ops, spec.changes,
memory.ingest rules pass, kernel._run_verification, aizee_server output
filter, and aizee_mcp doctor_tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest


class TestVerificationGaps:
    def test_resolve_passthrough_enum(self) -> None:
        from runtime.verification import VerificationLevel, resolve_verify

        assert resolve_verify(VerificationLevel.STRICT) is VerificationLevel.STRICT

    def test_checkpoints_blocks_forbidden_path_diff(self, tmp_path: Path) -> None:
        from runtime.verification import VerificationLevel, run_verification

        data = {"diff": "--- a/x\n+++ b/.env\n+SECRET=1\n"}
        result = run_verification(VerificationLevel.CHECKPOINTS, "Edit", data, tmp_path)
        assert result is not None
        assert result["violation"] == "plan_diff"
        assert result["verify"] == "checkpoints"

    def test_checkpoints_passes_clean_diff(self, tmp_path: Path) -> None:
        from runtime.verification import VerificationLevel, run_verification

        data = {"diff": "--- a/foo.py\n+++ b/foo.py\n+x = 1\n"}
        result = run_verification(VerificationLevel.CHECKPOINTS, "Edit", data, tmp_path)
        assert result is None

    def test_strict_supply_chain_flags_undeclared(self, tmp_path: Path) -> None:
        from runtime.verification import VerificationLevel, run_verification

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname="x"\ndependencies=[]\n', encoding="utf-8"
        )
        data = {"diff": "--- a/m.py\n+++ b/m.py\n+import undeclared_pkg_xyz_qqq\n"}
        result = run_verification(VerificationLevel.STRICT, "Edit", data, tmp_path)
        assert result is not None
        assert result["violation"] in ("supply_chain", "plan_diff")

    def test_strict_no_added_code(self, tmp_path: Path) -> None:
        from runtime.verification import _check_supply_chain

        assert _check_supply_chain("+++ b/f.py\n--- a/f.py\n", tmp_path) == []

    def test_supply_chain_exception_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import runtime.verification as v

        class Boom:
            def __init__(self, root: Path) -> None:
                raise RuntimeError("no manifest")

        monkeypatch.setattr("runtime.supply_chain_guard.SupplyChainGuard", Boom)
        assert v._check_supply_chain("+import os\n", tmp_path) == []

    def test_extract_diff_non_str(self) -> None:
        from runtime.verification import _extract_diff

        assert _extract_diff({"diff": 123}) == ""
        assert _extract_diff({"patch": "+x"}) == "+x"


class TestKernelVerifyGate:
    def test_act_verify_checkpoints_denies_forbidden(self, tmp_path: Path) -> None:
        from runtime.kernel import Kernel

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        # Read-type actions pass the policy ASK gate so the verify layer runs.
        result = k.act("Read", verify="checkpoints",
                       diff="--- a/x\n+++ b/.env\n+S=1\n")
        assert result.get("ok") is False
        assert result.get("violation") == "plan_diff"

    def test_act_verify_off_skips(self, tmp_path: Path) -> None:
        from runtime.kernel import Kernel

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        result = k.act("Read", verify="off",
                       diff="--- a/x\n+++ b/.env\n+S=1\n", dry_run=True)
        # verify=off adds nothing; the outcome (if any) must come from the
        # mandatory gates, not the verify gate.
        assert result.get("violation") is None

    def test_act_verify_bad_value_raises(self, tmp_path: Path) -> None:
        from runtime.kernel import Kernel
        from runtime.schemas import ValidationError

        k = Kernel(tmp_path / "os", tmp_path / "proj")
        with pytest.raises(ValidationError):
            k.act("Read", verify="paranoid")


class TestDoctorGaps:
    def test_fix_dict_shaped(self, tmp_path: Path) -> None:
        from runtime.doctor import run_doctor

        report = run_doctor(tmp_path / "os", tmp_path / "proj")
        for c in report.checks:
            if not c.ok and (c.fix_run or c.fix_guidance):
                d = c.to_dict()
                assert "fix" in d
                assert "run" in d["fix"] or "guidance" in d["fix"]

    def test_version_file_present(self, tmp_path: Path) -> None:
        from runtime.doctor import _version_check

        (tmp_path / ".aizee-version").write_text("9.9.9", encoding="utf-8")
        c = _version_check(tmp_path)
        assert c.ok and "9.9.9" in c.name

    def test_encryption_key_set_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.doctor import _encryption_check

        monkeypatch.setenv("AIOS_ENCRYPTION_KEY", "x")
        c = _encryption_check()
        assert c.name.startswith("encryption")

    def test_mcp_config_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os as _os

        from runtime.doctor import _mcp_config_check

        if _os.name == "nt":
            cfg_dir = tmp_path / "devin"
            monkeypatch.setenv("APPDATA", str(tmp_path))
        else:
            cfg_dir = tmp_path / ".config" / "devin"
            monkeypatch.setenv("HOME", str(tmp_path))
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "mcp_config.json").write_text(
            json.dumps({"mcpServers": {"aizee": {}}}), encoding="utf-8"
        )
        checks = _mcp_config_check()
        assert checks and checks[0].ok

    def test_mcp_config_empty_servers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os as _os

        from runtime.doctor import _mcp_config_check

        if _os.name == "nt":
            cfg_dir = tmp_path / "devin"
            monkeypatch.setenv("APPDATA", str(tmp_path))
        else:
            cfg_dir = tmp_path / ".config" / "devin"
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "mcp_config.json").write_text(
            json.dumps({"mcpServers": {}}), encoding="utf-8"
        )
        checks = _mcp_config_check()
        assert checks and not checks[0].ok

    def test_policy_checks_load_error(self, tmp_path: Path) -> None:
        from runtime.doctor import _policy_checks

        pol = tmp_path / "runtime" / "policies"
        pol.mkdir(parents=True)
        (pol / "guardian.yaml").write_text("not: [valid: yaml: {", encoding="utf-8")
        (pol / "probity.yaml").write_text("rules: {}\n", encoding="utf-8")
        checks = _policy_checks(tmp_path)
        names = [c.name for c in checks]
        assert any("guardian" in n for n in names)
        assert any("probity" in n for n in names)

    def test_capability_check(self) -> None:
        from runtime.doctor import _capability_check

        checks = _capability_check()
        assert checks and checks[0].name.startswith("capabilit")

    def test_tech_stack_check_fresh_root(self, tmp_path: Path) -> None:
        from runtime.doctor import _tech_stack_check

        checks = _tech_stack_check(tmp_path / "os", tmp_path / "proj")
        assert checks  # either detected or optional-fail

    def test_vector_check_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from runtime.doctor import _vector_check

        class BoomVec:
            def __init__(self, root: Path) -> None:
                raise RuntimeError("no vector backend")

        fake_mod = MagicMock()
        fake_mod.VectorMemory = BoomVec
        monkeypatch.setitem(sys.modules, "memory.vector", fake_mod)
        checks = _vector_check(tmp_path)
        assert checks and not checks[0].ok

    def test_deps_missing_pkg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        from runtime.doctor import _dep_checks

        real_import = builtins.__import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "yaml":
                raise ImportError("nope")
            return real_import(name, *a, **k)

        checks: list[Any] = []
        monkeypatch.setattr(builtins, "__import__", fake_import)
        _dep_checks(checks)
        assert any(c.name == "pip: yaml" and not c.ok for c in checks)
        assert any(c.fix_run == "pip install -e ." for c in checks if not c.ok)


class TestEnvelopeGaps:
    def test_pending_update_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import config
        from runtime.tool_envelope import ok_response

        state = tmp_path / "state"
        state.mkdir()
        (state / "update_available.json").write_text(
            json.dumps({"version": "9.9.9"}), encoding="utf-8"
        )
        monkeypatch.setattr(config, "discover_root", lambda: tmp_path)
        r = ok_response("t", 1)
        assert r["meta"]["update"]["version"] == "9.9.9"
        assert r["meta"]["update"]["available"] is True

    def test_pending_update_bad_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import config
        from runtime.tool_envelope import _pending_update

        state = tmp_path / "state"
        state.mkdir()
        (state / "update_available.json").write_text("{bad json", encoding="utf-8")
        monkeypatch.setattr(config, "discover_root", lambda: tmp_path)
        assert _pending_update() is None

    def test_err_response_severity(self) -> None:
        from runtime.schemas import BudgetExceededError
        from runtime.tool_envelope import err_response

        r = err_response("t", BudgetExceededError("over"))
        assert r["error"]["code"] == "BUDGET_EXCEEDED"

    def test_unknown_exception_internal(self) -> None:
        from runtime.tool_envelope import err_response

        r = err_response("t", RuntimeError("x"))
        assert r["error"]["code"] == "INTERNAL"


class TestFindGaps:
    def _root(self, tmp_path: Path) -> Path:
        (tmp_path / "skills" / "react-wizard").mkdir(parents=True, exist_ok=True)
        (tmp_path / "skills" / "react-wizard" / "SKILL.md").write_text("x", encoding="utf-8")
        (tmp_path / "skills" / "flat-skill.md").write_text("y", encoding="utf-8")
        (tmp_path / "workflows").mkdir(exist_ok=True)
        (tmp_path / "workflows" / "01-build.md").write_text(
            "## Steps\n1. one\n2. two\n## Done\n", encoding="utf-8"
        )
        (tmp_path / "tech-stack").mkdir(exist_ok=True)
        (tmp_path / "tech-stack" / "react-19.md").write_text("z", encoding="utf-8")
        return tmp_path

    def test_to_dicts(self, tmp_path: Path) -> None:
        from runtime.find import find, goal

        r = find("react", self._root(tmp_path))
        assert r and r[0].to_dict()["kind"] in ("skill", "tech-stack")
        g = goal("build", self._root(tmp_path), tmp_path)
        assert g.to_dict()["objective"] == "build"

    def test_find_exact_name_boost(self, tmp_path: Path) -> None:
        from runtime.find import find

        results = find("flat-skill", self._root(tmp_path))
        assert results[0].name == "flat-skill"

    def test_steps_missing_file(self) -> None:
        from runtime.find import _extract_workflow_steps

        assert _extract_workflow_steps(Path("/nonexistent/wf.md")) == []

    def test_steps_cap_and_headers(self, tmp_path: Path) -> None:
        from runtime.find import _extract_workflow_steps

        body = "## Steps\n" + "".join(f"{i}. step {i}\n" for i in range(30))
        wf = tmp_path / "wf.md"
        wf.write_text(body, encoding="utf-8")
        steps = _extract_workflow_steps(wf)
        assert len(steps) == 20

    def test_score_persona_hit(self, tmp_path: Path) -> None:
        from runtime.find import _score
        from runtime.service_catalog import ServiceDescriptor

        desc = ServiceDescriptor(
            name="x", kind="skill", triggers=frozenset(),
            personas=frozenset({"mobile"}),
        )
        score, matched = _score(desc, ["mobile"])
        assert score > 0 and "mobile" in matched


class TestOutputFilterGaps:
    def test_empty_input(self) -> None:
        from runtime.output_filter import filter_output

        _filtered, stats = filter_output("")
        assert stats.compression_ratio == 0.0
        assert stats.saved_chars == 0

    def test_consecutive_blanks(self) -> None:
        from runtime.output_filter import filter_output

        text = "a\n\n\n\n\nb\n"
        filtered, stats = filter_output(text)
        assert filtered.count("\n\n") <= 1
        assert stats.collapsed_groups > 0

    def test_separator_lines_collapsed(self) -> None:
        from runtime.output_filter import filter_output

        text = "x\n=====\n" + "~~~~~\n" * 5 + "y\n"
        filtered, stats = filter_output(text)
        assert "x" in filtered and "y" in filtered
        assert stats.filtered_lines < stats.original_lines


class TestGatewayGaps:
    def test_forward_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        import runtime.gateway_proxy as gp

        class Resp:
            status = 200
            headers: ClassVar[dict[str, str]] = {"Content-Type": "application/json"}

            def read(self) -> bytes:
                return b"{}"

            def __enter__(self) -> Any:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

        captured: dict[str, Any] = {}

        def fake_urlopen(req: Any, timeout: float = 0) -> Any:
            captured["headers"] = dict(req.headers)
            return Resp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setenv("TEST_KEY", "k123")
        p = gp.Provider(name="a", base_url="http://x", kind="anthropic", api_key_env="TEST_KEY")
        status, _body, _ = gp.forward(p, "/v1/messages", b"{}", {})
        assert status == 200
        # urllib normalizes header case — compare case-insensitively.
        assert any(k.lower() == "x-api-key" and v == "k123"
                   for k, v in captured["headers"].items())

    def test_forward_openai_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        import runtime.gateway_proxy as gp

        captured: dict[str, Any] = {}

        class Resp:
            status = 200
            headers: ClassVar[dict[str, str]] = {}

            def read(self) -> bytes:
                return b""

            def __enter__(self) -> Any:
                return self

            def __exit__(self, *a: Any) -> None:
                return None

        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda req, timeout=0: (captured.update(dict(req.headers)), Resp())[1])
        monkeypatch.setenv("K2", "tok")
        p = gp.Provider(name="b", base_url="http://y", kind="openai", api_key_env="K2")
        gp.forward(p, "/v1/chat/completions", b"{}", {})
        assert captured.get("Authorization") == "Bearer tok"

    def test_forward_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error
        import urllib.request

        import runtime.gateway_proxy as gp

        def fake_urlopen(req: Any, timeout: float = 0) -> Any:
            raise urllib.error.HTTPError("u", 500, "err", {}, None)  # type: ignore[arg-type]

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        p = gp.Provider(name="a", base_url="http://x")
        status, _, _ = gp.forward(p, "/v1/messages", b"{}", {})
        assert status == 500

    def test_forward_url_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error
        import urllib.request

        import runtime.gateway_proxy as gp

        def fake_urlopen(req: Any, timeout: float = 0) -> Any:
            raise urllib.error.URLError("down")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        p = gp.Provider(name="a", base_url="http://x")
        status, body, _ = gp.forward(p, "/v1/messages", b"{}", {})
        assert status == 0 and body == b""

    def test_estimate_tokens_prompt_field(self) -> None:
        from runtime.gateway_proxy import estimate_tokens

        assert estimate_tokens({"prompt": "x" * 80}) == 20
        assert estimate_tokens({}) == 1

    def test_extract_prompt_plain(self) -> None:
        from runtime.gateway_proxy import extract_prompt_text

        assert extract_prompt_text({"prompt": "hello"}) == "hello"
        assert extract_prompt_text({}) == ""

    def _server(self, monkeypatch: pytest.MonkeyPatch, kernel: Any = None,
                forward_ret: tuple = (200, b'{"r":1}', {})) -> tuple[int, Any]:
        import threading
        from http.server import ThreadingHTTPServer

        import runtime.gateway_proxy as gp

        cfg = gp.GatewayConfig(providers=(gp.Provider(name="a", base_url="http://x"),))
        monkeypatch.setattr(gp, "forward",
                            lambda *a, **k: forward_ret)
        handler = gp.make_handler(cfg, kernel)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv.server_address[1], srv

    def _post(self, port: int, path: str, body: bytes) -> tuple[int, bytes]:
        import urllib.request

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_handler_unsupported_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        port, srv = self._server(monkeypatch)
        try:
            status, body = self._post(port, "/v1/other", b"{}")
            assert status == 404
            assert json.loads(body)["error"]["code"] == "NOT_FOUND"
        finally:
            srv.shutdown()

    def test_handler_bad_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        port, srv = self._server(monkeypatch)
        try:
            status, body = self._post(port, "/v1/messages", b"{bad")
            assert status == 400
            assert json.loads(body)["error"]["code"] == "BAD_INPUT"
        finally:
            srv.shutdown()

    def test_handler_oversized_body_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        import runtime.gateway_proxy as gp

        port, srv = self._server(monkeypatch)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
                s.sendall(
                    f"POST /v1/messages HTTP/1.1\r\nHost: x\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {gp._MAX_BODY_BYTES + 1}\r\n"
                    f"Connection: close\r\n\r\n".encode()
                )
                resp = s.recv(4096)
            assert b"400" in resp.split(b"\r\n", 1)[0]
        finally:
            srv.shutdown()

    def test_handler_ok_forward(self, monkeypatch: pytest.MonkeyPatch) -> None:
        port, srv = self._server(monkeypatch)
        try:
            status, body = self._post(
                port, "/v1/messages?x=1",
                json.dumps({"messages": [{"role": "u", "content": "hi"}]}).encode(),
            )
            assert status == 200
            assert json.loads(body) == {"r": 1}
        finally:
            srv.shutdown()

    def test_handler_gate_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kernel = MagicMock()
        kernel.act.return_value = {"ok": False, "reason": "denied"}
        port, srv = self._server(monkeypatch, kernel=kernel)
        try:
            status, body = self._post(
                port, "/v1/messages",
                json.dumps({"messages": [{"role": "u", "content": "hi"}]}).encode(),
            )
            assert status == 403
            assert json.loads(body)["error"]["code"] == "POLICY_DENIED"
        finally:
            srv.shutdown()

    def test_handler_all_providers_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        port, srv = self._server(monkeypatch, forward_ret=(0, b"", {}))
        try:
            status, body = self._post(port, "/v1/messages", b"{}")
            assert status == 502
            assert json.loads(body)["error"]["code"] == "UPSTREAM_BROKEN"
        finally:
            srv.shutdown()

    def test_handler_upstream_retryable_end(self, monkeypatch: pytest.MonkeyPatch) -> None:
        port, srv = self._server(monkeypatch, forward_ret=(503, b'{"e":1}', {}))
        try:
            status, _ = self._post(port, "/v1/messages", b"{}")
            assert status == 503
        finally:
            srv.shutdown()

    def test_serve_no_providers(self, tmp_path: Path) -> None:
        from runtime.gateway_proxy import serve

        cfg = tmp_path / "g.yaml"
        cfg.write_text("providers: []\n", encoding="utf-8")
        with pytest.raises(ValueError):
            serve(cfg, 0, None)

    def test_serve_keyboard_interrupt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import runtime.gateway_proxy as gp

        cfg = tmp_path / "g.yaml"
        cfg.write_text(
            "providers:\n  - name: a\n    base_url: http://x\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            gp.ThreadingHTTPServer, "serve_forever",
            lambda self: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        assert gp.serve(cfg, 0, None) == 0


class TestIngestRulesGaps:
    def test_load_skips_invalid_entries(self, tmp_path: Path) -> None:
        from runtime.ingest_rules import load_rules

        (tmp_path / "rules").mkdir()
        (tmp_path / "rules" / "ingest.yaml").write_text(
            "rules:\n  - nope: x\n  - 'plain-string'\n  - match: 'a/*.md'\n",
            encoding="utf-8",
        )
        rules = load_rules(tmp_path)
        assert len(rules) == 1 and rules[0].match == "a/*.md"

    def test_load_explicit_path(self, tmp_path: Path) -> None:
        from runtime.ingest_rules import load_rules

        p = tmp_path / "custom.yaml"
        p.write_text("rules: []\n", encoding="utf-8")
        assert load_rules(tmp_path / "other", rules_path=p) == []

    def test_scan_folder_valueerror_fallback(self, tmp_path: Path) -> None:
        from runtime.ingest_rules import scan_folder

        outside = tmp_path / "out"
        outside.mkdir()
        (outside / "x.md").write_text("c", encoding="utf-8")
        unrelated_base = tmp_path / "base"
        unrelated_base.mkdir()
        hits = scan_folder(outside, [], base=unrelated_base)
        assert hits and hits[0][1].rule is None

    def test_scan_folder_not_dir(self, tmp_path: Path) -> None:
        from runtime.ingest_rules import scan_folder

        assert scan_folder(tmp_path / "ghost", []) == []


class TestIngestorRulesPass:
    def test_rules_route_into_bank(self, tmp_path: Path) -> None:
        from memory.ingest import Ingestor
        from memory.store import MemoryStore

        root = tmp_path / "os"
        (root / "rules").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (root / "rules" / "ingest.yaml").write_text(
            "rules:\n  - match: 'docs/*.md'\n    bank: kb\n    kind: reference\n    tags: [doc]\n",
            encoding="utf-8",
        )
        store = MemoryStore(tmp_path / "brain")
        ids = Ingestor(store, root).ingest_all()
        assert ids
        hits = store.search("Guide")
        assert hits and hits[0].bank == "kb"

    def test_no_rules_file(self, tmp_path: Path) -> None:
        from memory.ingest import Ingestor
        from memory.store import MemoryStore

        root = tmp_path / "os"
        root.mkdir(parents=True)
        store = MemoryStore(tmp_path / "brain")
        assert Ingestor(store, root).ingest_all() == []


class TestConfigOpsGaps:
    def _mgr(self, tmp_path: Path) -> Any:
        from runtime.settings import get_settings_manager

        return get_settings_manager(tmp_path)

    def test_apply_yaml_file(self, tmp_path: Path) -> None:
        from runtime.config_ops import apply_config

        mgr = self._mgr(tmp_path)
        cfg = tmp_path / "c.yaml"
        cfg.write_text("budget:\n  global:\n    max_tokens: 42\n", encoding="utf-8")
        result = apply_config(mgr, cfg, check=True)
        assert result["ok"]
        assert result["changes"]["budget"]["global"]["max_tokens"]["to"] == 42

    def test_apply_non_mapping_file(self, tmp_path: Path) -> None:
        from runtime.config_ops import apply_config
        from runtime.schemas import ValidationError

        cfg = tmp_path / "c.json"
        cfg.write_text("[1,2,3]", encoding="utf-8")
        with pytest.raises(ValidationError):
            apply_config(self._mgr(tmp_path), cfg, check=True)

    def test_apply_section_non_object(self, tmp_path: Path) -> None:
        from runtime.config_ops import apply_config

        cfg = tmp_path / "c.json"
        cfg.write_text(json.dumps({"budget": 42}), encoding="utf-8")
        result = apply_config(self._mgr(tmp_path), cfg, check=True)
        assert not result["ok"]
        assert "must be an object" in result["errors"][0]

    def test_apply_invalid_value(self, tmp_path: Path) -> None:
        from runtime.config_ops import apply_config

        cfg = tmp_path / "c.json"
        cfg.write_text(json.dumps({"budget": {"global": {"max_tokens": -1}}}), encoding="utf-8")
        result = apply_config(self._mgr(tmp_path), cfg, check=True)
        assert not result["ok"]

    def test_diff_removed_keys(self, tmp_path: Path) -> None:
        from runtime.config_ops import _diff

        out = _diff({"a": 1, "b": 2}, {"a": 1})
        assert out["b"] == {"removed": True}

    def test_redact_list(self) -> None:
        from runtime.config_ops import _redact

        out = _redact({"items": [{"token": "t1"}, "plain"]})
        assert out["items"][0]["token"] == "********"
        assert out["items"][1] == "plain"


class TestChangesGaps:
    def _engine(self, tmp_path: Path) -> Any:
        from runtime.spec_engine import SpecEngine

        return SpecEngine(tmp_path / "specs")

    def test_propose_default_title(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        d = engine.propose("my-thing")
        assert "My Thing" in (d / "proposal.md").read_text(encoding="utf-8")

    def test_scan_no_changes_dir(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        assert engine.list_changes() == []

    def test_archive_name_collision(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        engine.propose("c1")
        first = engine.archive("c1")
        engine.propose("c1")
        second = engine.archive("c1")
        assert first != second and second.exists()

    def test_status_and_task_counts(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        d = engine.propose("s")
        (d / "tasks.md").write_text("- [x] done\n- [ ] todo\n", encoding="utf-8")
        info = engine.change_status("s")
        assert info is not None and info.tasks_done == 1 and info.tasks_total == 2
        assert engine.change_status("ghost") is None

    def test_scan_skips_archive_subdir(self, tmp_path: Path) -> None:
        engine = self._engine(tmp_path)
        engine.propose("x")
        engine.archive("x")
        active = engine.list_changes()
        assert active == []
        archived = engine.list_archived()
        assert len(archived) == 1 and archived[0].archived


class TestServerOutputFilter:
    def test_gateway_post_check_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.aizee_server as srv

        kernel = MagicMock()
        kernel.check_tool_result.return_value = (True, "x\n" + ("====\n" * 50) + "y\n" * 8000)
        monkeypatch.setattr(srv, "kernel", lambda: kernel)
        monkeypatch.setenv("AIZEE_OUTPUT_FILTER", "1")
        out = srv._gateway_post_check("tool_x", kernel.check_tool_result.return_value[1])
        assert isinstance(out, str)
        kernel.audit.log.assert_called()

    def test_gateway_post_check_small_result_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.aizee_server as srv

        kernel = MagicMock()
        kernel.check_tool_result.return_value = (True, "small")
        monkeypatch.setattr(srv, "kernel", lambda: kernel)
        monkeypatch.setenv("AIZEE_OUTPUT_FILTER", "1")
        assert srv._gateway_post_check("t", "small") == "small"


class TestDoctorTools:
    class _FakeMCP:
        def __init__(self) -> None:
            self.tools: dict[str, Any] = {}

        def tool(self) -> Any:
            def deco(fn: Any) -> Any:
                self.tools[fn.__name__] = fn
                return fn
            return deco

    def _register(self) -> dict[str, Any]:
        from aizee_mcp.tools.doctor_tools import register_doctor_tools

        m = self._FakeMCP()
        register_doctor_tools(m)
        return m.tools

    def test_registers_three_tools(self) -> None:
        tools = self._register()
        assert {"aizee_doctor", "aizee_find", "aizee_goal"} <= set(tools)

    def test_doctor_tool_envelope(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        tools = self._register()
        monkeypatch.setattr(dt, "root", lambda: tmp_path / "os")
        k = MagicMock()
        k.project_root = tmp_path / "proj"
        monkeypatch.setattr(dt, "kernel", lambda: k)
        out = json.loads(tools["aizee_doctor"]())
        assert out["schema_version"] == "aizee.tool.v1"
        assert out["ok"] is True
        assert out["result"]["verdict"] in ("ready", "degraded", "blocked")

    def test_doctor_tool_error_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        tools = self._register()
        monkeypatch.setattr(dt, "run_doctor",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(dt, "root", lambda: Path("/x"))
        out = json.loads(tools["aizee_doctor"]())
        assert out["ok"] is False and out["error"]["code"] == "INTERNAL"

    def test_find_tool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "sk.md").write_text("x", encoding="utf-8")
        tools = self._register()
        monkeypatch.setattr(dt, "root", lambda: tmp_path)
        out = json.loads(tools["aizee_find"]("sk"))
        assert out["ok"] is True and out["result"]["items"]

    def test_goal_tool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        (tmp_path / "workflows").mkdir(parents=True)
        (tmp_path / "workflows" / "01-w.md").write_text("## Steps\n1. s\n", encoding="utf-8")
        tools = self._register()
        monkeypatch.setattr(dt, "root", lambda: tmp_path)
        k = MagicMock()
        k.project_root = tmp_path
        monkeypatch.setattr(dt, "kernel", lambda: k)
        out = json.loads(tools["aizee_goal"]("w"))
        assert out["ok"] is True

    def test_find_tool_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import aizee_mcp.tools.doctor_tools as dt

        tools = self._register()
        monkeypatch.setattr(dt, "nl_find",
                            lambda *a, **k: (_ for _ in ()).throw(ValueError("bad q")))
        out = json.loads(tools["aizee_find"]("x"))
        assert out["ok"] is False and out["error"]["code"] == "BAD_INPUT"
