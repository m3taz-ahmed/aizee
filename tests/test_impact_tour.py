"""Tests for runtime.impact, runtime.tour, runtime.layers (Understand-Anything adoption)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runtime.impact import (
    DEPENDS_ON,
    ImpactAnalyzer,
    ImpactError,
    ImpactReport,
    changed_files,
    render_report,
)
from runtime.layers import Layer, layer_for, layer_for_test_of
from runtime.tour import TourBuilder, TourError, render_tour


def _graph(nodes: list[dict], links: list[dict]) -> dict:
    return {"nodes": nodes, "links": links, "built_at_commit": "abc123"}


def _node(nid: str, sfile: str | None, comm: int = 1) -> dict:
    n: dict = {"id": nid, "label": nid, "community": comm}
    if sfile:
        n["source_file"] = sfile
    return n


def _write_graph(root: Path, graph: dict) -> Path:
    gdir = root / "graphify-out"
    gdir.mkdir(parents=True, exist_ok=True)
    gpath = gdir / "graph.json"
    gpath.write_text(json.dumps(graph), encoding="utf-8")
    return gpath


class TestLayers:
    def test_prefix_map(self) -> None:
        assert layer_for("runtime/kernel.py") is Layer.RUNTIME
        assert layer_for("tests/test_x.py") is Layer.TESTS
        assert layer_for("dashboard/server.py") is Layer.DASHBOARD
        assert layer_for("skills/web/SKILL.md") is Layer.SKILLS
        assert layer_for("workflows/01-x.md") is Layer.WORKFLOWS
        assert layer_for("./pkg/x.py") is Layer.OTHER  # "./" stripped before match
        assert layer_for("deploy.ps1") is Layer.SCRIPTS
        assert layer_for("memory/store.py") is Layer.MEMORY
        assert layer_for("scripts/sync_docs.py") is Layer.SCRIPTS

    def test_config_and_docs(self) -> None:
        assert layer_for("pyproject.toml") is Layer.CONFIG
        assert layer_for("manifest.json") is Layer.CONFIG
        assert layer_for("README.md") is Layer.DOCS
        assert layer_for("docs/guide.md") is Layer.DOCS

    def test_root_py_is_cli(self) -> None:
        assert layer_for("aizee_cli.py") is Layer.CLI
        assert layer_for("weird.xyz") is Layer.OTHER

    def test_windows_separators(self) -> None:
        assert layer_for("runtime\\kernel.py") is Layer.RUNTIME

    def test_dotfiles_not_mangled(self) -> None:
        # lstrip("./") used to strip leading dots — .gitignore → "gitignore"
        assert layer_for(".gitignore") is Layer.CONFIG
        assert layer_for(".env") is Layer.CONFIG

    def test_test_of(self) -> None:
        assert layer_for_test_of("runtime/kernel.py") == "tests/test_kernel.py"
        assert layer_for_test_of("tests/test_x.py") is None
        assert layer_for_test_of("readme.md") is None


class TestImpact:
    def test_reverse_bfs_blast_radius(self, tmp_path: Path) -> None:
        # app.py imports lib.py; handler.py calls app.py.fn -> change lib.py
        graph = _graph(
            [
                _node("app_py", "app.py", comm=1),
                _node("lib_py", "lib.py", comm=2),
                _node("handler_py", "handler.py", comm=3),
            ],
            [
                {"source": "app_py", "target": "lib_py", "relation": "imports"},
                {"source": "handler_py", "target": "app_py", "relation": "calls"},
                {"source": "handler_py", "target": "os", "relation": "imports"},
            ],
        )
        _write_graph(tmp_path, graph)
        report = ImpactAnalyzer(tmp_path).analyze(["lib.py"])
        assert report.impacted == ["app.py", "handler.py"]
        assert report.depth_reached == 2

    def test_changed_files_excluded(self, tmp_path: Path) -> None:
        graph = _graph(
            [_node("a", "a.py"), _node("b", "b.py")],
            [{"source": "b", "target": "a", "relation": "imports"}],
        )
        _write_graph(tmp_path, graph)
        report = ImpactAnalyzer(tmp_path).analyze(["a.py", "b.py"])
        assert report.impacted == []

    def test_non_dep_edges_ignored(self, tmp_path: Path) -> None:
        graph = _graph(
            [_node("a", "a.py"), _node("b", "b.py")],
            [{"source": "b", "target": "a", "relation": "contains"}],
        )
        _write_graph(tmp_path, graph)
        assert "contains" not in DEPENDS_ON
        report = ImpactAnalyzer(tmp_path).analyze(["a.py"])
        assert report.impacted == []

    def test_test_mapping(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_lib.py").write_text("x", encoding="utf-8")
        graph = _graph([_node("lib", "lib.py")], [])
        _write_graph(tmp_path, graph)
        report = ImpactAnalyzer(tmp_path).analyze(["lib.py"])
        assert report.impacted_tests == ["tests/test_lib.py"]

    def test_missing_graph(self, tmp_path: Path) -> None:
        with pytest.raises(Exception) as exc:
            ImpactAnalyzer(tmp_path).analyze(["x.py"])
        assert "graph" in str(exc.value).lower()

    def test_no_matching_nodes(self, tmp_path: Path) -> None:
        _write_graph(tmp_path, _graph([_node("a", "a.py")], []))
        report = ImpactAnalyzer(tmp_path).analyze(["nonexistent.py"])
        assert report.impacted == [] and report.depth_reached == 0

    def test_render(self, tmp_path: Path) -> None:
        graph = _graph(
            [_node("a", "a.py"), _node("b", "b.py")],
            [{"source": "b", "target": "a", "relation": "imports"}],
        )
        _write_graph(tmp_path, graph)
        text = render_report(ImpactAnalyzer(tmp_path).analyze(["a.py"]))
        assert "Impact Analysis" in text and "b.py" in text


class TestTour:
    def _sample(self, tmp_path: Path) -> None:
        # comm 1 = foundational (inbound from 2 and 3), comm 3 = leaf
        graph = _graph(
            [
                _node("k", "runtime/kernel.py", comm=1),
                _node("s", "runtime/schemas.py", comm=1),
                _node("c", "aizee_cli.py", comm=2),
                _node("d", "dashboard/server.py", comm=3),
            ],
            [
                {"source": "c", "target": "k", "relation": "imports", "weight": 1.0},
                {"source": "d", "target": "k", "relation": "imports", "weight": 1.0},
                {"source": "c", "target": "s", "relation": "imports", "weight": 1.0},
            ],
        )
        _write_graph(tmp_path, graph)

    def test_foundations_first(self, tmp_path: Path) -> None:
        self._sample(tmp_path)
        tour = TourBuilder(tmp_path).build()
        assert tour.stops[0].community == 1  # most-depended-on first
        assert tour.communities_total == 3
        assert tour.nodes_total == 4

    def test_stops_have_highlights(self, tmp_path: Path) -> None:
        self._sample(tmp_path)
        tour = TourBuilder(tmp_path).build()
        first = tour.stops[0]
        assert first.highlights and first.layer == "runtime"
        assert "kernel" in first.highlights[0] or "schemas" in first.highlights[0]

    def test_max_stops(self, tmp_path: Path) -> None:
        self._sample(tmp_path)
        tour = TourBuilder(tmp_path).build(max_stops=1)
        assert len(tour.stops) == 1

    def test_render_markdown(self, tmp_path: Path) -> None:
        self._sample(tmp_path)
        text = render_tour(TourBuilder(tmp_path).build())
        assert "Guided Architecture Tour" in text and "## 1." in text

    def test_missing_graph(self, tmp_path: Path) -> None:
        with pytest.raises(Exception) as exc:
            TourBuilder(tmp_path).build()
        assert "graph" in str(exc.value).lower()


class TestTourEdge:
    def test_nodes_without_source_file(self, tmp_path: Path) -> None:
        """REGRESSION: a community with no source_file must not crash the title."""
        _write_graph(tmp_path, _graph([_node("n1", None, comm=1)], []))
        tour = TourBuilder(tmp_path).build()
        assert tour.stops[0].title == "unlabeled"
        assert tour.graph_commit == "abc123"
        assert tour.stale_graph is False  # tmp_path is not a git repo

    def test_bad_graph_raises(self, tmp_path: Path) -> None:
        gpath = _write_graph(tmp_path, _graph([], []))
        gpath.write_text("{broken", encoding="utf-8")
        with pytest.raises(TourError) as exc:
            TourBuilder(tmp_path, graph_path=gpath).build()
        assert exc.value.error_code == "BAD_GRAPH"

    def test_stale_graph_warns_in_render(self, tmp_path: Path, monkeypatch) -> None:
        """Graph built at a different commit surfaces a stale warning."""
        nodes = [
            _node("a1", "pkg/aa.py", 1),
            _node("a2", "pkg/ab.py", 1),
            _node("a3", "pkg/ac.py", 1),          # short stems -> plain dir title
            _node("b1", "lib/cache_a.py", 2),
            _node("b2", "lib/cache_b.py", 2),
            _node("b3", "lib/cache_c.py", 2),     # 'cache' stem -> dir (stem*)
            {"id": "bad", "label": "x"},           # no community -> skipped
        ]
        links = [
            {"source": "b1", "target": "a1", "relation": "depends_on", "weight": 2.0},
            {"source": "a1", "target": "a2", "relation": "depends_on"},
            {"source": 1, "target": "a1", "relation": "depends_on"},
        ]
        gpath = _write_graph(
            tmp_path, {"nodes": nodes, "links": links, "built_at_commit": "oldsha"}
        )

        class _P:
            returncode = 0
            stdout = "newsha123\n"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _P())
        tour = TourBuilder(tmp_path, graph_path=gpath).build()
        assert tour.stale_graph is True
        titles = {s.title for s in tour.stops}
        assert "lib/cache_a.py (cache*)" in titles  # stem-qualified title
        assert "pkg/aa.py" in titles                # no >3-char stems -> dir only
        text = render_tour(tour)
        assert "differs from HEAD" in text
        assert tour.to_dict()["stale_graph"] is True

    def test_stale_check_git_failure_is_safe(self, tmp_path: Path, monkeypatch) -> None:
        gpath = _write_graph(tmp_path, _graph([_node("n1", "a.py", 1)], []))

        def _gone(*a: object, **k: object) -> None:
            raise OSError("no git")

        monkeypatch.setattr(subprocess, "run", _gone)
        tour = TourBuilder(tmp_path, graph_path=gpath).build()
        assert tour.stale_graph is False


class TestChangedFiles:
    def test_worktree_base_staged_and_error(self, tmp_path: Path, monkeypatch) -> None:
        calls: list[list[str]] = []

        class _P:
            def __init__(self, stdout: str = "", rc: int = 0) -> None:
                self.stdout, self.returncode, self.stderr = stdout, rc, ""

        def _run(cmd: list[str], **kw: object) -> _P:
            calls.append(cmd)
            if "ls-files" in cmd:
                return _P("untracked.py\n")
            return _P("a.py\nb.py\n")

        monkeypatch.setattr(subprocess, "run", _run)
        assert changed_files(tmp_path) == ["a.py", "b.py", "untracked.py"]
        calls.clear()
        assert changed_files(tmp_path, base="v1") == ["a.py", "b.py"]
        assert all("ls-files" not in c for c in calls)  # --base skips untracked
        # staged diffs still fold in untracked files
        assert changed_files(tmp_path, staged=True) == ["a.py", "b.py", "untracked.py"]

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _P(rc=1))
        with pytest.raises(ImpactError) as exc:
            changed_files(tmp_path)
        assert exc.value.error_code == "GIT"

    def test_ls_files_failure_is_tolerated(self, tmp_path: Path, monkeypatch) -> None:
        """A failing ls-files just means no untracked additions."""

        class _P:
            def __init__(self, stdout: str = "", rc: int = 0) -> None:
                self.stdout, self.returncode, self.stderr = stdout, rc, ""

        def _run(cmd: list[str], **kw: object) -> _P:
            return _P(rc=1) if "ls-files" in cmd else _P("a.py\n")

        monkeypatch.setattr(subprocess, "run", _run)
        assert changed_files(tmp_path) == ["a.py"]


class TestImpactEdges:
    def test_bad_graph_and_cached_load(self, tmp_path: Path) -> None:
        gpath = _write_graph(tmp_path, _graph([], []))
        gpath.write_text("{broken", encoding="utf-8")
        with pytest.raises(ImpactError) as exc:
            ImpactAnalyzer(tmp_path, graph_path=gpath).analyze(["x.py"])
        assert exc.value.error_code == "BAD_GRAPH"

    def test_node_link_filters_and_stale_exception(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        nodes = [
            _node("n1", "a.py", 1),
            _node("n2", None, None),                                # no file, no comm
            {"id": "n3", "source_file": "", "community": 2},        # empty sfile
            {"id": 7, "source_file": "x.py", "community": 1},       # non-str id
            _node("n4", "tests/test_a.py", 2),
        ]
        links = [
            {"source": "n2", "target": "n1", "relation": "imports"},
            {"source": "n4", "target": "n1", "relation": "imports"},
            {"source": "n1", "target": "n2", "relation": "depends_on"},  # filtered relation
            {"source": "n1", "target": 9, "relation": "imports"},  # non-str target
        ]
        gpath = _write_graph(
            tmp_path, {"nodes": nodes, "links": links, "built_at_commit": "abc"}
        )
        az = ImpactAnalyzer(tmp_path, graph_path=gpath)
        az._load()
        az._load()  # cached — early return
        report = az.analyze(["a.py"], max_depth=1)
        assert "tests/test_a.py" in report.impacted_tests
        assert report.truncated is True  # depth cap hit with frontier left
        assert report.to_dict()["changed"] == ["a.py"]

        def _gone(*a: object, **k: object) -> None:
            raise OSError("no git")

        monkeypatch.setattr(subprocess, "run", _gone)
        report2 = az.analyze(["a.py"])
        assert report2.stale_graph is False
        assert report2.depth_reached >= 1  # BFS exhausted naturally this time

    def test_render_full_and_sparse(self) -> None:
        report = ImpactReport(
            changed=[f"f{i}.py" for i in range(25)],
            impacted=[f"runtime/m{i}.py" for i in range(35)],
            impacted_tests=[f"tests/test_{i}.py" for i in range(35)],
            communities=[1, 2],
            layer_counts={"runtime": 35},
            depth_reached=3,
            truncated=True,
            stale_graph=True,
            graph_commit="deadbeef",
        )
        text = render_report(report)
        assert "+5 more" in text
        assert "truncated" in text
        assert "differs from HEAD" in text
        assert "layers" in text
        sparse = render_report(ImpactReport(changed=["a.py"]))
        assert "layers" not in sparse
        assert "impacted files:" not in sparse
        few_tests = render_report(
            ImpactReport(changed=["a.py"], impacted_tests=["tests/test_a.py"])
        )
        assert "tests to re-run:" in few_tests
        assert "+0 more" not in few_tests  # <=30 tests -> no truncation footer
