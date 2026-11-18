"""Tests for the source/mirror root-divergence warning in ``aizee_cli._root``."""

from __future__ import annotations

import argparse
from pathlib import Path

import aizee_cli


def _ns(root: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(root=root)


def _make_source_like(path: Path) -> None:
    (path / "AGENTS.md").write_text("x", encoding="utf-8")
    (path / "runtime").mkdir()
    (path / "aizee_cli.py").write_text("x", encoding="utf-8")


def test_no_warning_when_root_matches_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert aizee_cli._root(_ns(tmp_path)) == tmp_path
    assert "warning" not in capsys.readouterr().err


def test_warns_when_env_root_diverges_from_source_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    _make_source_like(tmp_path)
    monkeypatch.chdir(tmp_path)
    mirror = tmp_path.parent / "mirror-root"
    monkeypatch.setattr(aizee_cli.config, "discover_root", lambda: mirror)
    assert aizee_cli._root(_ns(None)) == mirror
    err = capsys.readouterr().err
    assert "resolved root" in err and "--root" in err


def test_no_warning_when_cwd_is_not_source(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)  # plain dir — no source markers
    elsewhere = tmp_path.parent / "elsewhere"
    (elsewhere / "skills").mkdir(parents=True)  # full OS root — no bootstrap hint either
    monkeypatch.setattr(aizee_cli.config, "discover_root", lambda: elsewhere)
    assert aizee_cli._root(_ns(None)) == elsewhere
    assert capsys.readouterr().err == ""


def test_explicit_root_suppresses_warning(tmp_path: Path, monkeypatch, capsys) -> None:
    _make_source_like(tmp_path)
    monkeypatch.chdir(tmp_path)
    chosen = tmp_path.parent / "chosen-root"
    assert aizee_cli._root(_ns(chosen)) == chosen
    assert capsys.readouterr().err == ""


def _root_with_pyproject(path: Path, version: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n', encoding="utf-8")
    return path


def test_warn_install_drift_on_version_mismatch(tmp_path: Path, capsys) -> None:
    root = _root_with_pyproject(tmp_path / "root", "0.0.1")
    aizee_cli._warn_install_drift(root)
    err = capsys.readouterr().err
    assert "0.0.1" in err and "reinstall" in err


def test_warn_install_drift_silent_when_equal(tmp_path: Path, capsys) -> None:
    root = _root_with_pyproject(tmp_path / "root", aizee_cli.config.VERSION)
    aizee_cli._warn_install_drift(root)
    assert capsys.readouterr().err == ""


def test_warn_install_drift_silent_without_pyproject(tmp_path: Path, capsys) -> None:
    aizee_cli._warn_install_drift(tmp_path / "no-pyproject")
    assert capsys.readouterr().err == ""


def test_warn_install_drift_silent_on_read_error(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = _root_with_pyproject(tmp_path / "root", "1.2.3")
    monkeypatch.setattr(
        Path, "read_text", lambda self, **kw: (_ for _ in ()).throw(OSError("locked"))
    )
    aizee_cli._warn_install_drift(root)
    assert capsys.readouterr().err == ""


def test_warn_install_drift_silent_on_versionless_pyproject(tmp_path: Path, capsys) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    aizee_cli._warn_install_drift(root)
    assert capsys.readouterr().err == ""


def test_hint_missing_os_root(tmp_path: Path, capsys) -> None:
    aizee_cli._hint_missing_os_root(tmp_path / "empty-root")
    assert "bootstrap" in capsys.readouterr().err


def test_hint_missing_os_root_silent_with_skills(tmp_path: Path, capsys) -> None:
    root = tmp_path / "root"
    (root / "skills").mkdir(parents=True)
    aizee_cli._hint_missing_os_root(root)
    assert capsys.readouterr().err == ""


def test_root_integration_warns_on_drift(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    drifted = _root_with_pyproject(tmp_path / "drifted", "0.0.1")
    (drifted / "skills").mkdir()
    monkeypatch.setattr(aizee_cli.config, "discover_root", lambda: drifted)
    assert aizee_cli._root(_ns(None)) == drifted
    err = capsys.readouterr().err
    assert "0.0.1" in err and "reinstall" in err
