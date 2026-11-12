"""Guided architecture tour — dependency-ordered walkthrough of the codebase.

Adopted concept from Understand-Anything's ``tour-builder`` agent (MIT,
clean-room Python): their LLM pipeline picks an ordering; ours is
deterministic — graphify communities ranked by how much of the rest of
the codebase depends on them (inbound cross-community edge weight),
foundations first, entry points last. No cycles can form because the
ranking is a sort, not a traversal.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from runtime.layers import layer_for
from runtime.schemas import AizeeError

_logger = logging.getLogger(__name__)

_DEFAULT_GRAPH = Path("graphify-out") / "graph.json"
_DEFAULT_STOPS = 12
_PER_STOP = 6


class TourError(AizeeError):
    """Tour generation failures (missing/invalid graph)."""


@dataclass
class TourStop:
    """One community on the tour."""

    community: int
    title: str
    layer: str
    size: int
    inbound_weight: float
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "community": self.community,
            "title": self.title,
            "layer": self.layer,
            "size": self.size,
            "inbound_weight": round(self.inbound_weight, 2),
            "highlights": self.highlights,
        }


@dataclass
class Tour:
    stops: list[TourStop] = field(default_factory=list)
    communities_total: int = 0
    nodes_total: int = 0
    stale_graph: bool = False
    graph_commit: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "stops": [s.to_dict() for s in self.stops],
            "communities_total": self.communities_total,
            "nodes_total": self.nodes_total,
            "stale_graph": self.stale_graph,
            "graph_commit": self.graph_commit,
        }


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def _community_title(files: list[str]) -> str:
    """Name a community after its dominant directory or shared stem."""
    dirs: Counter[str] = Counter()
    stems: Counter[str] = Counter()
    if not files:
        return "unlabeled"
    for f in files:
        norm = _norm(f)
        parts = norm.split("/")
        dirs["/".join(parts[:2]) if len(parts) > 1 else parts[0].rsplit(".", 1)[0]] += 1
        stem = parts[-1].rsplit(".", 1)[0]
        for token in stem.replace("-", "_").split("_"):
            if len(token) > 3:
                stems[token] += 1
    top_dir: str = dirs.most_common(1)[0][0]
    if stems:
        top_stem, freq = stems.most_common(1)[0]
        if freq >= max(2, len(files) // 3):
            return f"{top_dir} ({top_stem}*)"
    return top_dir


class TourBuilder:
    """Build a deterministic, foundations-first tour from graphify output."""

    def __init__(self, root: Path, graph_path: Path | None = None) -> None:
        self._root = root
        self._graph_path = graph_path or (root / _DEFAULT_GRAPH)

    def build(self, max_stops: int = _DEFAULT_STOPS, per_stop: int = _PER_STOP) -> Tour:
        if not self._graph_path.exists():
            raise TourError(
                "NO_GRAPH",
                f"graph not found: {self._graph_path} — run `graphify update .` first",
                context={"path": str(self._graph_path)},
            )
        try:
            graph = json.loads(self._graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TourError("BAD_GRAPH", f"cannot parse graph: {exc}", context={}) from exc

        graph_commit, stale = str(graph.get("built_at_commit") or ""), False
        try:
            import subprocess

            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            stale = bool(
                graph_commit and head.returncode == 0 and head.stdout.strip() != graph_commit
            )
        except (OSError, subprocess.TimeoutExpired):
            stale = False

        comm_nodes: dict[int, list[dict[str, object]]] = defaultdict(list)
        node_comm: dict[str, int] = {}
        for node in graph.get("nodes", []):
            nid, comm = node.get("id"), node.get("community")
            if isinstance(nid, str) and isinstance(comm, int):
                comm_nodes[comm].append(node)
                node_comm[nid] = comm

        inbound: defaultdict[int, float] = defaultdict(float)
        indeg: defaultdict[str, float] = defaultdict(float)
        for link in graph.get("links", []):
            src, tgt = link.get("source"), link.get("target")
            if not isinstance(src, str) or not isinstance(tgt, str):
                continue
            weight = float(link.get("weight") or 1.0)
            indeg[tgt] += weight
            s_comm, t_comm = node_comm.get(src), node_comm.get(tgt)
            if s_comm is not None and t_comm is not None and s_comm != t_comm:
                inbound[t_comm] += weight

        ordered = sorted(
            comm_nodes,
            key=lambda c: (-inbound.get(c, 0.0), -len(comm_nodes[c]), c),
        )[:max_stops]

        stops: list[TourStop] = []
        for comm in ordered:
            nodes = comm_nodes[comm]
            files = [
                str(n["source_file"])
                for n in nodes
                if isinstance(n.get("source_file"), str) and n.get("source_file")
            ]
            file_weight: defaultdict[str, float] = defaultdict(float)
            for n in nodes:
                sfile = n.get("source_file")
                nid = n.get("id")
                if isinstance(sfile, str) and sfile and isinstance(nid, str):
                    file_weight[sfile] += indeg.get(nid, 0.0)
            highlights = [
                f for f, _ in sorted(
                    file_weight.items(), key=lambda kv: (-kv[1], kv[0])
                )[:per_stop]
            ]
            layer_hist = Counter(layer_for(f) for f in files)
            layer = layer_hist.most_common(1)[0][0].value if layer_hist else "other"
            stops.append(
                TourStop(
                    community=comm,
                    title=_community_title(files),
                    layer=layer,
                    size=len(nodes),
                    inbound_weight=inbound.get(comm, 0.0),
                    highlights=highlights,
                )
            )
        return Tour(
            stops=stops,
            communities_total=len(comm_nodes),
            nodes_total=len(node_comm),
            stale_graph=stale,
            graph_commit=graph_commit,
        )


def render_tour(tour: Tour) -> str:
    """Render the tour as a markdown walkthrough."""
    lines = [
        "# Guided Architecture Tour",
        "",
        f"{tour.communities_total} communities, {tour.nodes_total} nodes — "
        "ordered foundations-first by inbound dependency weight.",
        "",
    ]
    if tour.stale_graph:
        lines.append(
            f"> warning: graph built at {tour.graph_commit[:8]} differs from HEAD — "
            "run `graphify update .` for exact results"
        )
        lines.append("")
    for i, stop in enumerate(tour.stops, 1):
        lines.append(
            f"## {i}. {stop.title}  `[{stop.layer}]` "
            f"({stop.size} nodes, inbound w={stop.inbound_weight:.0f})"
        )
        for h in stop.highlights:
            lines.append(f"- `{h}`")
        lines.append("")
    return "\n".join(lines)
