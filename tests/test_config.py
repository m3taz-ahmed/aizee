"""Tests for config.py - root discovery and version parsing."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

import config as config_mod


class TestDiscoverRoot:
    """Tests for config.discover_root()."""

    def test_uses_agent_os_root_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AIZEE_ROOT", str(tmp_path))
        assert config_mod.discover_root() == tmp_path.resolve()

    def test_falls_back_to_config_parent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: tmp_path / "no-root.txt")
        result = config_mod.discover_root()
        assert result == Path(config_mod.__file__).resolve().parent

    def test_raises_on_nonexistent_env_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AIZEE_ROOT", "/nonexistent/path/that/should/not/exist")
        with pytest.raises(ValueError, match="AIZEE_ROOT"):
            config_mod.discover_root()

    def test_resolves_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AIZEE_ROOT", ".")
        result = config_mod.discover_root()
        assert result == tmp_path.resolve()


class TestDiscoverProjectRoot:
    """Tests for config.discover_project_root()."""

    def test_uses_agent_project_root_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_PROJECT_ROOT", str(tmp_path))
        result = config_mod.discover_project_root()
        assert result == tmp_path.resolve()

    def test_falls_back_to_agent_os_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENT_PROJECT_ROOT", raising=False)
        monkeypatch.setenv("AIZEE_ROOT", str(tmp_path))
        result = config_mod.discover_project_root()
        assert result == tmp_path.resolve()

    def test_falls_back_to_cwd_with_active_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGENT_PROJECT_ROOT", raising=False)
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        (ai_dir / "active-context.md").write_text("test", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = config_mod.discover_project_root()
        assert result == tmp_path.resolve()

    def test_falls_back_to_discover_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENT_PROJECT_ROOT", raising=False)
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: tmp_path / "no-root.txt")
        monkeypatch.chdir(Path(config_mod.__file__).resolve().parent)
        result = config_mod.discover_project_root()
        assert result == Path(config_mod.__file__).resolve().parent

    def test_raises_on_nonexistent_project_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_PROJECT_ROOT", "/nonexistent/project/path")
        with pytest.raises(ValueError, match="AGENT_PROJECT_ROOT"):
            config_mod.discover_project_root()


class TestVersion:
    """Tests for config._version() and VERSION constant."""

    def test_version_is_string(self) -> None:
        assert isinstance(config_mod.VERSION, str)
        assert len(config_mod.VERSION) > 0

    def test_version_format(self) -> None:
        # Should match semver-like pattern (e.g. "4.22.0")
        parts = config_mod.VERSION.split(".")
        assert len(parts) >= 2
        for part in parts:
            assert part.isdigit() or any(c.isdigit() for c in part)

    def test_version_reads_from_pyproject(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Create a fake pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nversion = "9.9.9"\n', encoding="utf-8"
        )
        # Mock __file__ to point to tmp_path
        with mock.patch.object(config_mod, "__file__", str(tmp_path / "config.py")):
            assert config_mod._version() == "9.9.9"

    def test_version_defaults_when_no_pyproject(self, tmp_path: Path) -> None:
        with mock.patch.object(config_mod, "__file__", str(tmp_path / "config.py")):
            result = config_mod._version()
            assert result == config_mod.VERSION


class TestResolveEnvDir:
    """Tests for config._resolve_env_dir()."""

    def test_returns_env_path_when_dir_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", str(tmp_path))
        result = config_mod._resolve_env_dir("TEST_VAR", Path("/fallback"))
        assert result == tmp_path.resolve()

    def test_returns_fallback_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_VAR", raising=False)
        fallback = Path("/some/fallback")
        result = config_mod._resolve_env_dir("TEST_VAR", fallback)
        assert result == fallback

    def test_raises_when_env_dir_does_not_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "/nonexistent/xyz")
        with pytest.raises(ValueError, match="TEST_VAR"):
            config_mod._resolve_env_dir("TEST_VAR", Path("/fallback"))


class TestDiscoverProjectRootCwdFallback:
    """Test line 39: the cwd fallback in discover_project_root."""

    def test_cwd_without_active_context_falls_back_to_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Line 39: when cwd has no .ai/active-context.md, falls back to discover_root()."""
        monkeypatch.delenv("AGENT_PROJECT_ROOT", raising=False)
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: tmp_path / "no-root.txt")
        # Use a temp dir that has no .ai/active-context.md
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="aizee_cfg_test_"))
        monkeypatch.chdir(tmp)
        result = config_mod.discover_project_root()
        # Should fall back to discover_root() which is the config.py parent
        assert result == Path(config_mod.__file__).resolve().parent
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


class TestRootPointer:
    """Tests for the bootstrap-written root pointer file."""

    def _write_pointer(self, tmp_path: Path, content: str) -> Path:
        pointer = tmp_path / "cfg" / "root.txt"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(content, encoding="utf-8")
        return pointer

    def test_pointer_used_when_no_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        root = tmp_path / "os-root"
        root.mkdir()
        pointer = self._write_pointer(tmp_path, str(root) + "\n")
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        assert config_mod.discover_root() == root.resolve()

    def test_env_beats_pointer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_root = tmp_path / "env-root"
        env_root.mkdir()
        monkeypatch.setenv("AIZEE_ROOT", str(env_root))
        pointer = self._write_pointer(tmp_path, str(tmp_path / "other") + "\n")
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        assert config_mod.discover_root() == env_root.resolve()

    def test_stale_pointer_falls_back_to_install_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        pointer = self._write_pointer(tmp_path, str(tmp_path / "deleted-root") + "\n")
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        assert config_mod.discover_root() == Path(config_mod.__file__).resolve().parent

    def test_blank_pointer_falls_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        pointer = self._write_pointer(tmp_path, "\n  \n")
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        assert config_mod.discover_root() == Path(config_mod.__file__).resolve().parent

    def test_unreadable_pointer_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        pointer = tmp_path / "cfg" / "root.txt"
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(
            Path, "read_text", lambda self, **kw: (_ for _ in ()).throw(OSError("locked"))
        )
        assert config_mod.discover_root() == Path(config_mod.__file__).resolve().parent

    def test_root_pointer_file_platform_dir(self) -> None:
        p = config_mod.root_pointer_file()
        assert p.name == "root.txt" and p.parent.name == "aizee"
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
            assert p.parent.parent == base
        else:
            assert p.parent.parent == Path.home() / ".config"

    def test_write_root_pointer_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        pointer = tmp_path / "cfg" / "root.txt"
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        target = tmp_path / "new-root"
        target.mkdir()
        written = config_mod.write_root_pointer(target)
        assert written == pointer
        assert config_mod.discover_root() == target.resolve()


class TestDefaultOsRoot:
    """Tests for config.default_os_root() precedence."""

    def test_env_root_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AIZEE_ROOT", str(tmp_path))
        assert config_mod.default_os_root() == tmp_path.resolve()

    def test_pointer_beats_install_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        root = tmp_path / "os-root"
        root.mkdir()
        pointer = tmp_path / "cfg" / "root.txt"
        pointer.parent.mkdir(parents=True)
        pointer.write_text(str(root) + "\n", encoding="utf-8")
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: pointer)
        assert config_mod.default_os_root() == root.resolve()

    def test_source_checkout_returns_install_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: tmp_path / "no-root.txt")
        install = tmp_path / "repo"
        (install / "skills").mkdir(parents=True)
        (install / "workflows").mkdir()
        monkeypatch.setattr(config_mod, "__file__", str(install / "config.py"))
        assert config_mod.default_os_root() == install

    def test_site_packages_falls_back_to_user_data_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AIZEE_ROOT", raising=False)
        monkeypatch.setattr(config_mod, "root_pointer_file", lambda: tmp_path / "no-root.txt")
        install = tmp_path / "site-packages"
        install.mkdir()
        monkeypatch.setattr(config_mod, "__file__", str(install / "config.py"))
        expected_base = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            if os.name == "nt"
            else Path.home() / ".local" / "share"
        )
        assert config_mod.default_os_root() == expected_base / "aizee"
