"""Diff impact analysis — blast radius of pending changes over the code graph.

Adopted concept from Understand-Anything's ``/understand-diff`` (MIT,
clean-room Python): map changed files onto the graphify dependency graph,
walk depends-on edges backwards, and report which files, tests,
communities and layers the change can ripple into.

Reads ``graphify-out/graph.json`` (networkx node-link format). Edges run
``source -(relation)-> target`` meaning "source depends on target"; a
change in ``target`` may therefore affect ``source``, so the analysis
expands the frontier along *incoming* edges (reverse BFS).
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from runtime.layers import Layer, layer_for, layer_for_test_of
from runtime.schemas import AizeeError

_logger = logging.getLogger(__name__)

DEPENDS_ON: frozenset[str] = frozenset(
    {
        "imports",
        "imports_from",
        "calls",
        "uses",
        "references",
        "inherits",
        "re_exports",
        "indirect_call",
    }
)

_DEFAULT_GRAPH = Path("graphify-out") / "graph.json"
_DEFAULT_MAX_DEPTH = 6
_MAX_VISITED = 50_000


class ImpactError(AizeeError):
    """Impact analysis failures (missing graph, git failures)."""


@dataclass
class ImpactReport:
    """Blast radius of a change set."""

    changed: list[str] = field(default_factory=list)
    impacted: list[str] = field(default_factory=list)
    impacted_tests: list[str] = field(default_factory=list)
    communities: list[int] = field(default_factory=list)
    layer_counts: dict[str, int] = field(default_factory=dict)
    depth_reached: int = 0
    truncated: bool = False
    stale_graph: bool = False
    graph_commit: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "changed": self.changed,
            "impacted": self.impacted,
            "impacted_tests": self.impacted_tests,
            "communities": self.communities,
            "layer_counts": self.layer_counts,
            "depth_reached": self.depth_reached,
            "truncated": self.truncated,
            "stale_graph": self.stale_graph,
            "graph_commit": self.graph_commit,
        }


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def changed_files(root: Path, base: str | None = None, staged: bool = False) -> list[str]:
    """Repo-relative paths changed vs the index, worktree, or a base ref."""
    if base:
        cmd = ["git", "diff", "--name-only", f"{base}...HEAD"]
    elif staged:
        cmd = ["git", "diff", "--name-only", "--cached"]
    else:
        cmd = ["git", "diff", "--name-only", "HEAD"]
    proc = subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=30, check=False
    )
    if proc.returncode != 0:
        raise ImpactError(
            "GIT", f"git diff failed: {proc.stderr.strip()[:200]}", context={"cmd": cmd}
        )
    files = [_norm(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
    if not base:  # untracked files only matter for worktree diffs
        proc2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc2.returncode == 0:
            files += [_norm(line.strip()) for line in proc2.stdout.splitlines() if line.strip()]
    return sorted(set(files))


class ImpactAnalyzer:
    """Reverse-BFS blast-radius computation over the dependency graph."""

    def __init__(self, root: Path, graph_path: Path | None = None) -> None:
        self._root = root
        self._graph_path = graph_path or (root / _DEFAULT_GRAPH)
        self._inbound: dict[str, list[str]] = defaultdict(list)
        self._node_file: dict[str, str] = {}
        self._node_community: dict[str, int] = {}
        self._file_nodes: dict[str, set[str]] = defaultdict(set)
        self._graph_commit = ""
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not self._graph_path.exists():
            raise ImpactError(
                "NO_GRAPH",
                f"graph not found: {self._graph_path} — run `graphify update .` first",
                context={"path": str(self._graph_path)},
            )
        try:
            graph = json.loads(self._graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ImpactError(
                "BAD_GRAPH", f"cannot parse graph: {exc}", context={}
            ) from exc
        self._graph_commit = str(graph.get("built_at_commit") or "")
        for node in graph.get("nodes", []):
            nid = node.get("id")
            sfile = node.get("source_file")
            if not isinstance(nid, str):
                continue
            if isinstance(sfile, str) and sfile:
                norm = _norm(sfile)
                self._node_file[nid] = norm
                self._file_nodes[norm].add(nid)
            comm = node.get("community")
            if isinstance(comm, int):
                self._node_community[nid] = comm
        for link in graph.get("links", []):
            if link.get("relation") not in DEPENDS_ON:
                continue
            src, tgt = link.get("source"), link.get("target")
            if isinstance(src, str) and isinstance(tgt, str):
                self._inbound[tgt].append(src)
        self._loaded = True

    def analyze(
        self, files: list[str], max_depth: int = _DEFAULT_MAX_DEPTH
    ) -> ImpactReport:
        """Reverse-BFS from changed files over depends-on edges."""
        self._load()
        report = ImpactReport(changed=sorted(files), graph_commit=self._graph_commit)
        try:
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            report.stale_graph = bool(
                self._graph_commit
                and head.returncode == 0
                and head.stdout.strip() != self._graph_commit
            )
        except (OSError, subprocess.TimeoutExpired):
            report.stale_graph = False

        frontier: set[str] = set()
        visited: set[str] = set()
        for f in files:
            for nid in self._file_nodes.get(_norm(f), ()):
                frontier.add(nid)
                visited.add(nid)
        if not frontier:
            _logger.info("impact: no graph nodes for changed files", extra={"files": files})
            return report

        impacted_files: set[str] = set()
        communities: Counter[int] = Counter()
        depth = 0
        while frontier and depth < max_depth and len(visited) < _MAX_VISITED:
            nxt: set[str] = set()
            for nid in frontier:
                for dep in self._inbound.get(nid, ()):
                    if dep in visited:
                        continue
                    visited.add(dep)
                    nxt.add(dep)
                    sfile = self._node_file.get(dep)
                    if sfile:
                        impacted_files.add(sfile)
                    comm = self._node_community.get(dep)
                    if comm is not None:
                        communities[comm] += 1
            if not nxt:
                break
            depth += 1
            frontier = nxt
        report.depth_reached = depth
        report.truncated = bool(frontier) and (
            depth >= max_depth or len(visited) >= _MAX_VISITED
        )

        changed_set = {_norm(f) for f in files}
        impacted_files -= changed_set
        tests = {f for f in impacted_files if layer_for(f) is Layer.TESTS}
        for f in sorted(impacted_files | changed_set):
            candidate = layer_for_test_of(f)
            if candidate and Path(self._root / candidate).exists():
                tests.add(_norm(candidate))
        report.impacted_tests = sorted(tests)
        report.impacted = sorted(impacted_files - tests)
        report.communities = [c for c, _ in communities.most_common(12)]
        layer_hist: Counter[str] = Counter()
        for f in impacted_files:
            layer_hist[layer_for(f).value] += 1
        report.layer_counts = dict(layer_hist.most_common())
        return report


def render_report(report: ImpactReport) -> str:
    """Human-readable blast-radius summary."""
    lines = ["=== Impact Analysis ===", ""]
    lines.append(f"changed files : {len(report.changed)}")
    for f in report.changed[:20]:
        lines.append(f"  * {f}")
    if len(report.changed) > 20:
        lines.append(f"  ... +{len(report.changed) - 20} more")
    lines.append("")
    lines.append(
        f"blast radius  : {len(report.impacted)} files, "
        f"{len(report.impacted_tests)} tests, "
        f"{len(report.communities)} communities (depth {report.depth_reached})"
    )
    if report.truncated:
        lines.append("  (truncated — depth/visited cap hit; widen --depth if needed)")
    if report.stale_graph:
        lines.append(
            f"  warning: graph built at {report.graph_commit[:8]} differs from HEAD — "
            "run `graphify update .` for exact results"
        )
    if report.layer_counts:
        layers = ", ".join(f"{k}:{v}" for k, v in report.layer_counts.items())
        lines.append(f"layers        : {layers}")
    if report.impacted:
        lines.append("")
        lines.append("impacted files:")
        for f in report.impacted[:30]:
            lines.append(f"  <- {f} [{layer_for(f).value}]")
        if len(report.impacted) > 30:
            lines.append(f"  ... +{len(report.impacted) - 30} more")
    if report.impacted_tests:
        lines.append("")
        lines.append("tests to re-run:")
        for f in report.impacted_tests[:30]:
            lines.append(f"  [t] {f}")
        if len(report.impacted_tests) > 30:
            lines.append(f"  ... +{len(report.impacted_tests) - 30} more")
    return "\n".join(lines)
