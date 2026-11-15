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
    monkeypatch.setattr(aizee_cli.config, "discover_root", lambda: elsewhere)
    assert aizee_cli._root(_ns(None)) == elsewhere
    assert capsys.readouterr().err == ""


def test_explicit_root_suppresses_warning(tmp_path: Path, monkeypatch, capsys) -> None:
    _make_source_like(tmp_path)
    monkeypatch.chdir(tmp_path)
    chosen = tmp_path.parent / "chosen-root"
    assert aizee_cli._root(_ns(chosen)) == chosen
    assert capsys.readouterr().err == ""
