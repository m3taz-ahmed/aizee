"""Tests for runtime/deps.py — external dependency manifest."""

from __future__ import annotations

import sys
from pathlib import Path

from runtime import deps
from runtime.deps import DepSpec, Kind, State


def _manifest(tmp_path: Path, entries: str) -> Path:
    (tmp_path / "deps.yaml").write_text(
        "version: 1\nmedia_dir_default: '{media_root}'\ndeps:\n".format(
            media_root=str(tmp_path / "media").replace("\\", "/")
        )
        + entries,
        encoding="utf-8",
    )
    return tmp_path


class TestLoadManifest:
    def test_missing_manifest_returns_empty(self, tmp_path: Path):
        specs, meta = deps.load_manifest(tmp_path)
        assert specs == []
        assert meta == {}

    def test_parses_entries(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: ffmpeg\n    kind: binary\n    bin: ffmpeg\n    severity: recommended\n"
            "    required_by: [video-produce]\n    tags: [video]\n",
        )
        specs, _meta = deps.load_manifest(root)
        assert len(specs) == 1
        assert specs[0].id == "ffmpeg"
        assert specs[0].kind is Kind.BINARY
        assert specs[0].required_by == ("video-produce",)


class TestCheckBinary:
    def _spec(self, **over) -> DepSpec:
        base = {
            "id": "tool", "name": "tool", "kind": Kind.BINARY, "severity": "required",
            "bin": "tool", "version_cmd": ("tool", "--version"), "version_regex": r"(\d+\.\d+)",
        }
        return DepSpec(**{**base, **over})

    def test_missing_binary(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: None)
        _, meta = deps.load_manifest(tmp_path)
        ctx = deps._Ctx(root=tmp_path, media=deps.media_dir(meta))
        status = deps.check_dep(self._spec(install={"all": "echo install"}), ctx)
        assert status.state is State.MISSING
        assert not status.ok
        assert status.fix_cmd == "aizee deps install tool"

    def test_present_binary(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/tool")

        class _Proc:
            returncode = 0
            stdout = "tool 7.2"
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _Proc())
        _, meta = deps.load_manifest(tmp_path)
        ctx = deps._Ctx(root=tmp_path, media=deps.media_dir(meta))
        status = deps.check_dep(self._spec(min_version="6.0"), ctx)
        assert status.ok
        assert status.version == "7.2"

    def test_outdated_binary(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/tool")

        class _Proc:
            returncode = 0
            stdout = "tool 5.0"
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _Proc())
        _, meta = deps.load_manifest(tmp_path)
        ctx = deps._Ctx(root=tmp_path, media=deps.media_dir(meta))
        status = deps.check_dep(self._spec(min_version="6.0"), ctx)
        assert status.state is State.OUTDATED
        assert not status.ok


class TestCheckKinds:
    def test_pip_present_and_missing(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: pip-self\n    kind: pip\n    package: pip\n"
            "  - id: ghost\n    kind: pip\n    package: def-not-a-real-pkg-xyz\n",
        )
        statuses = {s.spec.id: s for s in deps.check_all(root)}
        assert statuses["pip-self"].ok
        assert statuses["pip-self"].version
        assert statuses["ghost"].state is State.MISSING

    def test_git_repo(self, tmp_path: Path):
        kit = tmp_path / "media" / "kits" / "demo"
        kit.mkdir(parents=True)
        root = _manifest(
            tmp_path,
            "  - id: kit\n    kind: git-repo\n    path: '{media}/kits/demo'\n"
            "    repo: https://example.com/demo.git\n",
        )
        missing = deps.check_all(root)[0]
        assert missing.state is State.MISSING
        (kit / "file.txt").write_text("x", encoding="utf-8")
        present = deps.check_all(root)[0]
        assert present.ok

    def test_command_kind_match_and_miss(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: hit\n    kind: command\n    check_cmd:\n"
            "      all: [\"" + sys.executable.replace("\\", "/") + "\", \"-c\", \"print('nvenc ok')\"]\n"
            "    expect_regex: \"nvenc\"\n"
            "  - id: miss\n    kind: command\n    check_cmd:\n"
            "      all: [\"" + sys.executable.replace("\\", "/") + "\", \"-c\", \"print('cpu only')\"]\n"
            "    expect_regex: \"nvenc\"\n",
        )
        statuses = {s.spec.id: s for s in deps.check_all(root)}
        assert statuses["hit"].ok
        assert statuses["miss"].state is State.MISSING

    def test_env_any_of(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("DEP_TEST_A", raising=False)
        monkeypatch.delenv("DEP_TEST_B", raising=False)
        root = _manifest(
            tmp_path,
            "  - id: keys\n    kind: env\n    env_any_of: true\n"
            "    env_vars: [DEP_TEST_A, DEP_TEST_B]\n",
        )
        assert deps.check_all(root)[0].state is State.MISSING
        monkeypatch.setenv("DEP_TEST_B", "x")
        assert deps.check_all(root)[0].ok


class TestInstall:
    def test_git_repo_default_command(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: kit\n    kind: git-repo\n    path: '{media}/kits/demo'\n"
            "    repo: https://example.com/demo.git\n",
        )
        results = deps.install_statuses(root, deps.check_all(root), dry_run=True)
        assert len(results) == 1
        assert results[0].ok
        assert "git clone --depth 1" in results[0].command
        assert "https://example.com/demo.git" in results[0].command

    def test_placeholders_and_os_fallback(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: pkg\n    kind: pip\n    package: ghost-pkg-xyz\n"
            "    install:\n      all: '{python} -m pip install --user ghost-pkg-xyz'\n",
        )
        results = deps.install_statuses(root, deps.check_all(root), dry_run=True)
        assert results[0].ok
        assert results[0].command.startswith(sys.executable)

    def test_manual_dep_reports_no_command(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: keys\n    kind: env\n    env_vars: [DEP_MANUAL_X]\n"
            "    guidance: set the key\n",
        )
        results = deps.install_statuses(root, deps.check_all(root), dry_run=True)
        assert not results[0].ok
        assert "manual" in results[0].detail

    def test_runner_invoked_and_rechecked(self, tmp_path: Path):
        kit_dir = tmp_path / "media" / "kits" / "demo"
        root = _manifest(
            tmp_path,
            "  - id: kit\n    kind: git-repo\n    path: '{media}/kits/demo'\n"
            "    repo: https://example.com/demo.git\n",
        )
        calls: list[str] = []

        def fake_runner(cmd: str):
            calls.append(cmd)
            (kit_dir / "f").parent.mkdir(parents=True, exist_ok=True)
            (kit_dir / "f").write_text("x", encoding="utf-8")
            return 0, "cloned"

        results = deps.install_statuses(root, deps.check_all(root), runner=fake_runner)
        assert results[0].ok
        assert calls and "git clone" in calls[0]


class TestFilters:
    def test_tag_and_id_filters(self, tmp_path: Path):
        root = _manifest(
            tmp_path,
            "  - id: a\n    kind: pip\n    package: pip\n    tags: [video]\n"
            "  - id: b\n    kind: pip\n    package: pip\n    tags: [core]\n",
        )
        video = deps.check_all(root, tags={"video"})
        assert [s.spec.id for s in video] == ["a"]
        only_b = deps.check_all(root, ids={"b"})
        assert [s.spec.id for s in only_b] == ["b"]

class TestCoverageGaps:
    """Cover the remaining uncovered branches in deps.py."""

    def _ctx(self, tmp_path: Path) -> deps._Ctx:
        return deps._Ctx(root=tmp_path, media=tmp_path / "media")

    def _spec(self, **over) -> DepSpec:
        base = {"id": "d", "name": "d", "kind": Kind.BINARY, "severity": "optional"}
        return DepSpec(**{**base, **over})

    def test_os_key_darwin_and_linux(self, monkeypatch):
        monkeypatch.setattr(deps.sys, "platform", "darwin")
        assert deps.os_key() == "darwin"
        monkeypatch.setattr(deps.sys, "platform", "linux")
        assert deps.os_key() == "linux"

    def test_check_cmd_map_flat_list_and_invalid(self):
        assert deps._check_cmd_map(["a", "b"]) == {"all": ("a", "b")}
        assert deps._check_cmd_map("nope") == {}

    def test_pip_outdated(self, tmp_path: Path, monkeypatch):
        import importlib.metadata as im

        monkeypatch.setattr(im, "version", lambda _p: "1.0")
        spec = self._spec(kind=Kind.PIP, package="x", min_version="2.0")
        state, ver, _ = deps._check_pip(spec, self._ctx(tmp_path))
        assert state is State.OUTDATED
        assert ver == "1.0"

    def test_docker_daemon_no_binary(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: None)
        state, _, detail = deps._check_docker_daemon(self._spec(), self._ctx(tmp_path))
        assert state is State.MISSING
        assert "PATH" in detail

    def test_docker_daemon_info_oserror(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        def _raise(*a, **k):
            raise OSError("boom")

        monkeypatch.setattr(deps.subprocess, "run", _raise)
        state, _, _ = deps._check_docker_daemon(self._spec(), self._ctx(tmp_path))
        assert state is State.MISSING

    def test_docker_daemon_not_running(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        class _P:
            returncode = 1
            stdout = ""
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        state, _, detail = deps._check_docker_daemon(self._spec(), self._ctx(tmp_path))
        assert state is State.MISSING
        assert "not running" in detail

    def test_docker_image_no_binary(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: None)
        state, _, _ = deps._check_docker_image(self._spec(image="img"), self._ctx(tmp_path))
        assert state is State.MISSING

    def test_docker_image_oserror_and_unreachable(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        def _raise(*a, **k):
            raise OSError("boom")

        monkeypatch.setattr(deps.subprocess, "run", _raise)
        state, _, _ = deps._check_docker_image(self._spec(image="i"), self._ctx(tmp_path))
        assert state is State.UNKNOWN

        class _P:
            returncode = 2
            stdout = ""
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        state, _, detail = deps._check_docker_image(self._spec(image="i"), self._ctx(tmp_path))
        assert state is State.UNKNOWN
        assert "unreachable" in detail

    def test_docker_image_not_built(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        class _P:
            returncode = 0
            stdout = "  "
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        state, _, detail = deps._check_docker_image(self._spec(image="img"), self._ctx(tmp_path))
        assert state is State.MISSING
        assert "not built" in detail

    def test_registry_env_posix_false(self, monkeypatch):
        monkeypatch.setattr(deps.os, "name", "posix")
        assert deps._registry_env_has("AIZEE_TEST_VAR") is False

    def test_registry_env_found_and_hive_oserror(self, monkeypatch):
        import types

        fake = types.ModuleType("winreg")
        fake.HKEY_CURRENT_USER = 1
        fake.HKEY_LOCAL_MACHINE = 2

        class _Key:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        calls = []

        def _open(hive, sub):
            calls.append(hive)
            if hive == 1:
                raise OSError("denied")
            return _Key()

        fake.OpenKey = _open
        fake.QueryValueEx = lambda k, n: ("v", 1)
        monkeypatch.setitem(sys.modules, "winreg", fake)
        assert deps._registry_env_has("AIZEE_TEST_VAR") is True
        assert calls == [1, 2]

    def test_any_path_first_missing_second_found(self, tmp_path: Path):
        found = tmp_path / "exists.txt"
        found.write_text("x", encoding="utf-8")
        spec = self._spec(kind=Kind.ANY_PATH, paths=(str(tmp_path / "nope"), str(found)))
        state, _, _ = deps._check_any_path(spec, self._ctx(tmp_path))
        assert state is State.OK

    def test_any_path_all_missing(self, tmp_path: Path):
        spec = self._spec(kind=Kind.ANY_PATH, paths=(str(tmp_path / "a"), str(tmp_path / "b")))
        state, _, detail = deps._check_any_path(spec, self._ctx(tmp_path))
        assert state is State.MISSING
        assert "none of the expected paths" in detail

    def test_command_no_os_entry(self, tmp_path: Path):
        spec = self._spec(kind=Kind.COMMAND, check_cmd={"other-os": ("echo", "hi")})
        state, _, detail = deps._check_command(spec, self._ctx(tmp_path))
        assert state is State.UNKNOWN
        assert "no check command" in detail

    def test_resolve_git_repo_update_pulls(self, tmp_path: Path):
        spec = self._spec(kind=Kind.GIT_REPO, path=str(tmp_path / "kit"), repo="https://x/y.git")
        cmd = deps._resolve({}, spec, self._ctx(tmp_path), update=True)
        assert cmd is not None
        assert "git -C" in cmd
        assert "pull --ff-only" in cmd

    def test_install_command_outdated_uses_update(self, tmp_path: Path):
        spec = self._spec(kind=Kind.PIP, package="p", update={"all": "pip install -U p"})
        cmd = deps.install_command(spec, self._ctx(tmp_path), outdated=True)
        assert cmd == "pip install -U p"

    def test_default_runner_success_and_timeout(self, monkeypatch):
        class _P:
            returncode = 3
            stdout = "o"
            stderr = "e"

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        rc, out = deps._default_runner("anything")
        assert rc == 3
        assert out == "oe"

        def _raise(*a, **k):
            raise deps.subprocess.TimeoutExpired("cmd", 1)

        monkeypatch.setattr(deps.subprocess, "run", _raise)
        rc, out = deps._default_runner("anything")
        assert rc == 124
        assert out == "timed out"

    def test_install_statuses_skips_ok(self, tmp_path: Path):
        ok = deps.DepStatus(spec=self._spec(), ok=True, state=State.OK)
        assert deps.install_statuses(tmp_path, [ok], dry_run=True) == []

    def test_ensure_parent_noop_for_pip(self, tmp_path: Path):
        deps._ensure_parent(self._spec(kind=Kind.PIP), self._ctx(tmp_path))

    def test_recheck_exception_returns_false(self, tmp_path: Path, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(deps, "check_dep", _boom)
        assert deps._recheck(self._spec(), self._ctx(tmp_path)) is False

    def test_detect_version_no_cmd_or_regex(self):
        assert deps._detect_version(self._spec(version_cmd=(), version_regex="x")) == ""
        assert deps._detect_version(self._spec(version_cmd=("a",), version_regex="")) == ""

    def test_detect_version_run_fails(self, monkeypatch):
        def _raise(*a, **k):
            raise OSError("boom")

        monkeypatch.setattr(deps.subprocess, "run", _raise)
        spec = self._spec(version_cmd=("tool", "-v"), version_regex=r"(\d+)")
        assert deps._detect_version(spec) == ""

    def test_docker_daemon_up(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        class _P:
            returncode = 0
            stdout = "27.1.0\n"
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        state, ver, detail = deps._check_docker_daemon(self._spec(), self._ctx(tmp_path))
        assert state is State.OK
        assert ver == "27.1.0"
        assert "up" in detail

    def test_docker_image_found(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(deps.shutil, "which", lambda _: "/usr/bin/docker")

        class _P:
            returncode = 0
            stdout = "sha256:abc\n"
            stderr = ""

        monkeypatch.setattr(deps.subprocess, "run", lambda *a, **k: _P())
        state, _, _ = deps._check_docker_image(self._spec(image="img"), self._ctx(tmp_path))
        assert state is State.OK

    def test_registry_env_falsy_value_continues(self, monkeypatch):
        import types

        fake = types.ModuleType("winreg")
        fake.HKEY_CURRENT_USER = 1
        fake.HKEY_LOCAL_MACHINE = 2

        class _Key:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        fake.OpenKey = lambda hive, sub: _Key()
        fake.QueryValueEx = lambda k, n: ("", 1)
        monkeypatch.setitem(sys.modules, "winreg", fake)
        assert deps._registry_env_has("AIZEE_TEST_VAR") is False

    def test_command_check_oserror(self, tmp_path: Path, monkeypatch):
        def _raise(*a, **k):
            raise OSError("boom")

        monkeypatch.setattr(deps.subprocess, "run", _raise)
        spec = self._spec(kind=Kind.COMMAND, check_cmd={"all": ("tool", "-v")})
        state, _, detail = deps._check_command(spec, self._ctx(tmp_path))
        assert state is State.MISSING
        assert "failed to run" in detail
