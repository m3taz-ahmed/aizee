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
