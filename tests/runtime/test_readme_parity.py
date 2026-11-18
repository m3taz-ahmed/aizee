"""Tests for runtime/readme_parity.py — localized README structural gate."""

from __future__ import annotations

from pathlib import Path

from runtime.readme_parity import check_readme_parity, localized_readmes

_BASE = """# Project

![badge](https://img.shields.io/badge/tests-100-green)

## One

```python
x = 1
```

## Two

| a | b |
|---|---|
| 1 | 2 |

### Sub

text
"""


def _write(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


class TestParity:
    def test_identical_structure_passes(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        _write(tmp_path, "README-AR.md", _BASE.replace("One", "واحد").replace("Two", "اتنين"))
        report = check_readme_parity(tmp_path)
        assert report.ok and report.compared == 1

    def test_no_localized_files_passes(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        report = check_readme_parity(tmp_path)
        assert report.ok and report.compared == 0

    def test_missing_section_fails(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        _write(tmp_path, "README-AR.md", _BASE.replace("### Sub\n\ntext\n", ""))
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert any(i.check == "headings" for i in report.issues)

    def test_reordered_sections_fail(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        # Swap the ### before the second ## — same count, wrong level order.
        reordered = _BASE.replace("## Two", "### Two").replace("### Sub", "## Sub")
        _write(tmp_path, "README-AR.md", reordered)
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert any(i.check == "headings" for i in report.issues)

    def test_stale_badge_number_fails(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        _write(tmp_path, "README-AR.md", _BASE.replace("badge/tests-100", "badge/tests-90"))
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert any(i.check == "badge_numbers" for i in report.issues)

    def test_missing_table_row_fails(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        _write(tmp_path, "README-AR.md", _BASE.replace("| 1 | 2 |\n", ""))
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert any(i.check == "table_rows" for i in report.issues)

    def test_missing_base_fails(self, tmp_path: Path) -> None:
        _write(tmp_path, "README-AR.md", _BASE)
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert report.issues[0].check == "base"

    def test_localized_glob_shape(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", "x")
        _write(tmp_path, "README-AR.md", "x")
        _write(tmp_path, "README-FR.md", "x")
        _write(tmp_path, "READMENOT.md", "x")
        assert {p.name for p in localized_readmes(tmp_path)} == {
            "README-AR.md", "README-FR.md"}


class TestRepoReadmes:
    def test_current_repo_readmes_are_in_parity(self) -> None:
        root = Path(__file__).resolve().parents[2]
        report = check_readme_parity(root)
        assert report.compared >= 1
        assert report.ok, [i.to_dict() for i in report.issues]


class TestEdgeCases:
    def test_directory_named_readme_ignored(self, tmp_path: Path) -> None:
        _write(tmp_path, "README.md", _BASE)
        (tmp_path / "README-DIR.md").mkdir()
        assert localized_readmes(tmp_path) == []

    def test_unreadable_localized_reports_issue(self, tmp_path: Path, monkeypatch) -> None:
        _write(tmp_path, "README.md", _BASE)
        target = tmp_path / "README-AR.md"
        target.write_text("x", encoding="utf-8")
        original = Path.read_text
        monkeypatch.setattr(
            Path, "read_text",
            lambda self, *a, **k: (_ for _ in ()).throw(OSError("denied"))
            if self == target else original(self, *a, **k),
        )
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert any(i.check == "read" for i in report.issues)

    def test_unreadable_base_reports_issue(self, tmp_path: Path, monkeypatch) -> None:
        target = tmp_path / "README.md"
        target.write_text("x", encoding="utf-8")
        monkeypatch.setattr(
            Path, "read_text",
            lambda *_a, **_k: (_ for _ in ()).throw(OSError("denied")),
        )
        report = check_readme_parity(tmp_path)
        assert not report.ok
        assert report.issues[0].check == "base"


def test_report_and_issue_to_dict(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", _BASE)
    _write(tmp_path, "README-AR.md", _BASE.replace("### Sub\n\ntext\n", ""))
    report = check_readme_parity(tmp_path)
    payload = report.to_dict()
    assert payload["ok"] is False and payload["compared"] == 1
    assert payload["issues"][0]["file"] == "README-AR.md"
    assert payload["issues"][0]["check"] == "headings"
