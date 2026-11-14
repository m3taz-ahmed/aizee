# Repo study — Egonex-AI/Understand-Anything (2026-11-12)

Source: https://github.com/Egonex-AI/Understand-Anything — MIT, TypeScript, Claude-Code/multi-harness plugin.
Pipeline: multi-agent scan -> `.ua/knowledge-graph.json` -> interactive dashboard + guided tours.

## Feature map vs aiZee

| Their feature | aiZee equivalent | Verdict |
|---|---|---|
| `/understand` graph build | `graphify update` (51k nodes, 12 relation types) | already have |
| `/understand-dashboard` | `aizee dashboard` + graphify HTML viz | already have |
| `/understand-chat`, `/understand-explain` | `graphify query` / `graphify explain` | already have |
| `/understand-domain` (domains/flows/steps) | `workflows/` = curated domain flows | already have |
| `/understand-onboard` | tour output covers it | folded into tour |
| `/understand-diff` blast radius | **none** | **ADOPTED -> `aizee impact`** |
| `tour-builder` guided walkthrough | **none** (communities unordered) | **ADOPTED -> `aizee tour`** |
| layer classification (API/Service/Data/UI) | **none** | **ADOPTED inside impact+tour** |
| incremental re-analysis | graphify incremental already | already have |
| `--language` localization | bilingual docs already; summary LLM-side | skip |
| multi-harness install.sh/ps1 | `aizee skill link --pack`, daemon install | already have |
| post-commit auto-update hook | manual `graphify update` per rules | deferred (hook slows commits) |
| large-repo benchmark methodology | eval harness | noted, skip |
| `/understand-figma` | — | out of scope |
| `/understand-knowledge` (wiki->graph) | memory ingest + graphify on docs dir | already covered |

## Adopted (clean-room, Python — no TS copied)

1. `runtime/impact.py` — `aizee impact [--base REF] [--staged] [--depth N]`: git-changed files -> graph nodes (by `source_file`) -> bounded reverse-BFS over DEPENDS_ON edges (imports, imports_from, calls, uses, references, inherits, re_exports, indirect_call) -> impacted files, tests (tests/ prefix + test_X<->X name mapping), communities, layer histogram. Stdlib/third-party nodes can't seed the frontier (no repo source_file) so blast radius stays repo-scoped.
2. `runtime/tour.py` — `aizee tour [--stops N] [--json]`: communities ranked by inbound cross-community edge weight (foundational-first, deterministic, cycle-free by construction), top nodes per community by in-degree, layer labels, markdown walkthrough.
3. `runtime/layers.py` — path/name heuristic layer classifier shared by both (cli/dashboard/runtime/memory/skills/workflows/tests/docs/vendor/config).

## Legal

MIT — ideas reimplemented in Python; attribution here + `tech-stack/useful-repos.md`. No code copied.
