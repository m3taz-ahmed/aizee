# Study — Agent-Ecosystem Research Wave (Harnesses, Memory, Skills, Schedules, Generative UI)

**Date:** 2026-11-14
**Scope:** OSS ecosystem sweep across 17 domains for adoptable patterns; hardware filter RTX 4050 / 6 GB VRAM
**Clone dir:** `temp/repo-research-2026-11-14/<domain>/<repo>` (depth-1; sparse for goose/tldraw/openclaw/ast-grep)
**Source window:** last ~6 months emphasized; all candidates verified via GitHub API (stars/license/push date)
**Dedupe:** `useful-repos.md` (~300 entries) + 4 prior studies (agentic-video ~81 repos, creative-tools 10, knowledge-graph, production-readiness) — everything inventoried there skipped
**Candidates studied:** 35 cloned, 25 deep-read, 10 structure/README-level (marked *)

---

## Coverage statement (Phase 0 output)

| Domain | Status | Note |
|--------|--------|------|
| Harnesses/orchestration | thin | meta-harness wave uncovered → 5 repos |
| MCP ecosystem | deep | only edge novelty (ext-apps, mcp-proxy) → 2 |
| Context/memory | thin | 2026 agent-memory explosion uncovered → 7 |
| Skills/rules | thin | canonical upstream + adapter matrix → 3 |
| Spec-driven | deep | 2 modest adds |
| Evals/observability | thin | judge/trajectory evals → 4 |
| Security/governance | deep | edge only → 3 |
| Design (priority) | thin | generative-UI protocol wave → 6 |
| Frontend/UI | thin | AG-UI + assistant-ui → 2 |
| Media | deep | covered — nothing new |
| DevTools/DX | thin | structural rewrite + indexing → 3 |
| Local inference | thin | llama-swap + sqlite-vec → 2 |
| Automation/routines | thin | `routines.py` 1 day old → 2 |
| Docs/onboarding | moderate | incremental-cache docs → 2 |
| Distribution | deep | marketplace matrix idea only |
| Business | deep | nothing new worth taking |
| Wildcard | — | AgentFS spec, MemPalace |

## Domain inventories

### Harnesses & orchestration
| Repo | ★ | Lang | License | Push | What |
|------|---|------|---------|------|------|
| ruvnet/ruflo | 81.7k | TS | MIT | 11-14 | Meta-harness: ledger/executor split, swarm topologies, SafetyEnvelope, metaharness audit/drift |
| aaif-goose/goose | 56.6k | Rust | Apache-2.0 | 11-14 | Mature open agent: crates/goose core + goose-mcp extensions, recipes, scheduler; migrating to official MCP Registry |
| moazbuilds/CodeMachine-CLI | 2.5k | TS | Apache-2.0 | 02-25 | `.workflow.js` DSL driving agent CLIs; bounded loops, per-step engine/model |
| first-fluke/oh-my-agent | 1.5k | TS | MIT | 11-14 | One `.agents/` SSOT → 14 runtimes; manifest+drift check; `agent spawn --isolation worktree`; ralph judge loop |
| os-factory/har | 132 | TS | Apache-2.0 | 11-13 | `.har/` harness: slot-based worktree isolation, stages.json, verify quick/full, poka-yoke gates |

### Skills / rules
| Repo | ★ | License | Push | What |
|------|---|---------|------|------|
| anthropics/skills | 194k | none asserted | 11-14 | Canonical SKILL.md upstream: `spec/`, `template/`, `skills/` catalog |
| wshobson/agents | 42.5k | MIT | 11-09 | 94 plugins/202 agents SSOT under `plugins/` → 7 harnesses via `tools/adapters/` + `capabilities.py` frozen-dataclass matrix |
| VoltAgent/awesome-agent-skills | 37k | MIT | 11-05 | 1000+ skills index (catalog reference) |

### Spec / plan
| Repo | ★ | License | What |
|------|---|---------|------|
| buildermethods/agent-os | 5.6k | MIT | `commands/`: discover/index/inject-standards, plan-product, shape-spec — standards as extractable/injectable artifacts |
| MrLesk/Backlog.md | 7.4k | MIT | md-kanban dogfooded in-repo (`backlog/{tasks,drafts,decisions,milestones,completed,archive}` + config.yml) |

### Context & memory
| Repo | ★ | Lang | License | What |
|------|---|------|---------|------|
| mem0ai/mem0 | 68.9k | Py | Apache-2.0 | v3: single-pass ADD-only extraction, entity linking, multi-signal fused retrieval (semantic+BM25+entity), temporal reasoning |
| vectorize-io/hindsight | 61k | Py | MIT | retain/recall/**reflect** verbs, banks, observations, mental models, decision models; `hindsight-all/` embedded no-server build |
| MemPalace/mempalace | 60.5k | Py | MIT | Verbatim archive (no summarization), wings/rooms/drawers scoped retrieval, pluggable backends, zero-LLM option |
| getzep/graphiti | 32.8k | Py | Apache-2.0 | Bitemporal KG (edges invalidated not deleted); OTEL_TRACING.md; Neo4j backend |
| MemoriLabs/Memori | 17.5k | Py | none asserted | SQL-native memory via wrapped LLM client; `core/` + benchmarks |
| supermemoryai/supermemory | 31.6k | TS | MIT | `apps/mcp` server + `packages/agent-framework-python` — memory as MCP + framework hooks |
| tursodatabase/agentfs | 3.5k | — | none asserted (docs-only spec) | **SQLite agent-FS spec**: `tool_calls` insert-only audit (started_at/completed_at/duration_ms), COW fs, kv state |

### Evals & observability
| Repo | ★ | License | What |
|------|---|---------|------|
| confident-ai/deepeval | 19.5k | Apache-2.0 | pytest-style LLM-judge metrics, DAG judge, agent trajectory evals |
| comet-ml/opik | 23.4k | Apache-2.0 | Trace trees + evals + dashboards (`apps/` multi-module) |
| UKGovernmentBEIS/inspect_ai | 3.2k | MIT | Task/Solver/Scorer/Sandbox composition + tool approval modes |
| harbor-framework/harbor | 7k | Apache-2.0 | Agent eval framework; `adapters/` for agent harnesses (terminal-bench lineage) |

### Security & governance
| Repo | ★ | License | What |
|------|---|---------|------|
| microsoft/PyRIT | 4.8k | MIT | Red-team: orchestrators × converters × scorers |
| snyk/agent-scan | 3.2k | Apache-2.0 | Harness-aware agent scanner: `agents/` adapters enumerate claude/codex/opencode/vscode(cursor, windsurf, kiro, antigravity, ext-mcp) configs; `guard.py` runtime interception; `hooks/` |
| superradcompany/microsandbox | 9k | Apache-2.0 | Rust microVMs, secret injection, MCP integration, Windows support |

### Design (generative UI)
| Repo | ★ | License | What |
|------|---|---------|------|
| a2ui-project/a2ui | 17.3k | Apache-2.0 | Declarative streaming agent-UI protocol: messages + component catalogs → React/Angular/Lit/Flutter/SwiftUI/Compose renderers |
| modelcontextprotocol/ext-apps | 3k | none asserted | Official MCP Apps spec + SDK (`_meta.ui` resources in tool results) |
| MCP-UI-Org/mcp-ui | 5.2k | Apache-2.0 | Pioneer UI-over-MCP implementation (remoteDom/iframe resources) |
| tldraw/tldraw | 51.4k | custom (NOASSERTION) | Agent template: canvas→context assembly (screenshot+shapes+selection+viewport), typed action schemas validated before apply — **patterns only** |
| onlook-dev/onlook | 27.2k | Apache-2.0 | code↔DOM mapping, edit-in-preview→code writeback |
| GLips/Figma-Context-MCP | 16.2k | MIT | Figma layout→agent-readable context (MCP server) |

### Frontend/UI
| Repo | ★ | License | What |
|------|---|---------|------|
| ag-ui-protocol/ag-ui | 17.2k | MIT | ~16 typed lifecycle/stream events agent↔UI (RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_*…), JSON-schema SDKs, SSE/WS transports; Nx monorepo `sdks/` |
| assistant-ui/assistant-ui | 13.1k | MIT | React AI-chat component model + tool-UI slots |

### DevTools
| Repo | ★ | Lang | License | What |
|------|---|------|---------|------|
| ast-grep/ast-grep | 16.6k | Rust | MIT | Structural search/lint/rewrite via code-like patterns + YAML rules; `sg` CLI |
| sourcebot-dev/sourcebot | 4k | Py | MIT | Self-hosted code search w/ MCP surface |
| cocoindex-io/cocoindex | 11.9k | Rust | Apache-2.0 | Incremental transform/index flows (source→index freshness) |

### Docs / onboarding
| Repo | ★ | License | What |
|------|---|---------|------|
| AsyncFuncAI/deepwiki-open | 18.4k | MIT | repo→wiki pipeline (local providers supported) |
| bb-boy680/open-zread | 51 | MIT | 3-layer repo map, AST/symbol-hash incremental doc cache, parallel page agents |

### Local inference
| Repo | ★ | Lang | License | What |
|------|---|------|---------|------|
| mostlygeek/llama-swap | 6.2k | Go | MIT | Hot-swap llama.cpp/vLLM models behind one port; idle-unload — the 6 GB VRAM unlock |
| asg017/sqlite-vec | 8.3k | C | Apache-2.0 | SQLite `vec0` virtual table for KNN — SQL-native vectors, zero deps |

### Automation / routines
| Repo | ★ | License | What |
|------|---|---------|------|
| openclaw/openclaw | 394k | MIT | Persistent automations: `src/cron/` `{kind:"cron"|"every"|"at", expr, tz}` schedules, active-hours windows, manual-run, scoped authority, run history |
| chaitin/agent-compose | 280 | **AGPL-3.0** | Compose-file agent declaration + cron/event triggers — **patterns only** |

### MCP
| Repo | ★ | License | What |
|------|---|---------|------|
| joshrotenberg/mcp-proxy | 19 | Apache-2.0 | Config-driven MCP reverse proxy: per-backend middleware, bearer/JWT/OAuth, RBAC visibility, arg validation, no inbound-token forwarding |

---

## Cross-cutting → aiZee map

| Pattern | Source | aiZee today | Proposal |
|---------|--------|-------------|----------|
| Declarative routine schedules (manual/every/cron/at + due computation) | openclaw `src/cron/`, agent-compose, OMA `automations.md` | `runtime/routines.py` — `schedule:` field parsed but inert | **ADOPTED** — `parse_schedule`/`next_fire`/`due`/`due_routines` + `aizee routine due` |
| Narrow-only delegation envelope (children may only shrink tools/scope/spend) | ruflo AGENTS.md SafetyEnvelope invariants | `runtime/task_farm.py`, `runtime/call_plan.py` — no capability-narrowing contract | Proposed — add `envelope` field validated to only-narrow on fan-out |
| Bounded workflow loops (`loopSteps`, `loopMaxIterations`, `loopSkip`, `executeOnce`) | CodeMachine `workflow.ts` resolveModule/resolveStep | `runtime/call_plan.py` inert plans; `runtime/loop_detector.py` runtime guard | Proposed — bounded `loop:` block in plan schema (detector already guards) |
| Per-harness capability matrix (frozen dataclass: skills/agents/commands native, marketplace, tool-allowlist, caps) | wshobson `tools/adapters/capabilities.py` | `runtime/harness_exporter.py` — flat dir table only | **PARTIAL ADOPT** — `devin` project target added; full matrix proposed |
| Per-repo skills dir `.devin/skills` native target | this repo's `.devin/skills/global-os`, OMA 14-vendor map | `harness_exporter` lacked it | **ADOPTED** — `_PROJECT_DIRS` + `devin` |
| ONNX torch-free embedder fallback (fastembed) | sqlite-vec study + 6 GB constraint; hindsight embedded mode | `memory/vector.py` — sentence-transformers only (torch-heavy) | **ADOPTED** — `Embedder` auto-fallback + `AIZEE_EMBEDDER` + `vector-lite` extra |
| SQLite-native vectors (`vec0`) | asg017/sqlite-vec, AgentFS spec | `memory/vector.py` uses turbovec (core dep — always present) | Registered in deps (`sqlite-vec`); backend swap is a non-goal — turbovec already required |
| Insert-only `tool_calls` audit (started_at/completed_at/duration_ms) | tursodatabase/agentfs SPEC.md | `runtime/audit.py` event log (check schema for duration cols) | Proposed — add duration columns if absent |
| Harness-aware agent enumeration before scan | snyk/agent-scan `agents/` adapters | `runtime/mcp_auditor.py` + `skill_scan` scan aiZee surface only | Proposed — `aizee security scan --harness <vendor>` adapter |
| retain/recall/**reflect** verb triad + mental models | hindsight | `memory/reflect.py` exists; banks + observations exist | Already-covered — validates direction; note divergence (their reflect produces cited answers) |
| Single-pass ADD-only fact ops + entity linking + temporal ranking | mem0 v3 | `memory/hybrid.py` entities, `memory/temporal.py`, sectors/heat | Already-covered — no action |
| Verbatim archive + scoped wings/rooms/drawers | MemPalace | `memory/store.py` verbatim already; `memory/sectors.py` scoping | Already-covered |
| Bitemporal edges (invalidate not delete) | graphiti | `memory/temporal.py` + `memory/graph.py` | Verify aiZee temporal keeps history on update; else adopt invalidation |
| md-kanban task artifacts (tasks/drafts/decisions/milestones/completed/archive) | Backlog.md `backlog/` dogfooding | `runtime/task_contract/`, spec engine | Proposed — `aizee task` kanban writer using same dir layout |
| Generative-UI protocol (declarative component catalog, streamed messages) | a2ui, MCP ext-apps, mcp-ui | `runtime/dashboard` stdlib UI; `ui_concepts` skills | Proposed — `aizee ui emit` emitting A2UI/AG-UI-compatible message streams |
| Typed agent→UI event stream (~16 lifecycle/tool events) | ag-ui | `runtime/event_bus.py` (typed pub/sub) | Proposed — align event names with AG-UI vocabulary for interop |
| Model hot-swap behind one port | llama-swap | none found | deps entry added (`llama-swap`); skill guidance for 6 GB box |
| MicroVM sandbox for untrusted code | microsandbox | `runtime/supply_chain_guard.py` static only | deps entry added; proposal — farm worker sandbox option |
| Worktree-isolated slots + deterministic verify stages | har `.har/` slots+stages, OMA `--isolation worktree` | `runtime/verification.py`, `runtime/durable.py` — no git-worktree isolation | Proposed — `farm submit --worktree` mode |
| Standards discover/index/inject pipeline | agent-os `commands/` | `rules/`, `tech-stack/` declarative layers | Proposed — `aizee standards extract` skill |

## Ranked adoption candidates (Ponytail filter — surgical first)

1. **`routine due` schedule engine** — ADOPTED. ~150 lines, stdlib cron parser, reuses existing state. (openclaw/agent-compose/OMA)
2. **fastembed embedder fallback** — ADOPTED. ~40 lines; kills torch requirement on the 6 GB box; `vector-lite` extra. (hindsight/sqlite-vec lineage)
3. **`devin` harness target** — ADOPTED. 6 lines. (OMA/wshobson vendor map)
4. **deps.yaml: fastembed, sqlite-vec, ast-grep, llama-swap, microsandbox** — ADOPTED (optional severity, install/guidance wired).
5. **SafetyEnvelope narrow-only `envelope` on fan-out** — proposed; ~60 lines in call_plan/task_farm.
6. **Bounded `loop:` in plan schema** — proposed; loop_detector already enforces runtime safety.
7. **`tool_calls` duration columns in audit** — proposed; schema check first.
8. **Harness-aware security scan** — proposed; bigger lift, defer to next wave.
9. **AG-UI event vocabulary alignment** — proposed; interop play.

Rejected by Ponytail: full wshobson-style adapter framework (over-engineering for 4 targets), Neo4j-grade temporal KG (sqlite is enough), any Redis/Postgres-shaped memory infra.

## Licensing

- **Adapted with attribution (MIT/Apache):** openclaw (schedule semantics), agentfs spec (schema), wshobson capability matrix (pattern), CodeMachine loop DSL (pattern), ruflo SafetyEnvelope (pattern), sqlite-vec/fastembed/ast-grep/llama-swap/microsandbox (as external deps).
- **Patterns-only (copyleft/custom):** chaitin/agent-compose (AGPL-3.0) — compose declaration + triggers, clean-room; tldraw/tldraw (custom license) — agent context-assembly pattern only.
- **No asserted license (verify before vendoring):** anthropics/skills, modelcontextprotocol/ext-apps, MemoriLabs/Memori, tursodatabase/agentfs — used as reference/spec only.

## Proposed `tech-stack/useful-repos.md` additions

(applied alongside this study — new section "Agent-ecosystem wave 2026-11")

ruvnet/ruflo, aaif-goose/goose, moazbuilds/CodeMachine-CLI, first-fluke/oh-my-agent, os-factory/har, anthropics/skills, wshobson/agents, VoltAgent/awesome-agent-skills, buildermethods/agent-os, MrLesk/Backlog.md, mem0ai/mem0, vectorize-io/hindsight, MemPalace/mempalace, getzep/graphiti, supermemoryai/supermemory, tursodatabase/agentfs, confident-ai/deepeval, comet-ml/opik, UKGovernmentBEIS/inspect_ai, harbor-framework/harbor, microsoft/PyRIT, snyk/agent-scan, superradcompany/microsandbox, a2ui-project/a2ui, modelcontextprotocol/ext-apps, MCP-UI-Org/mcp-ui, tldraw/tldraw (patterns only), onlook-dev/onlook, GLips/Figma-Context-MCP, ag-ui-protocol/ag-ui, assistant-ui/assistant-ui, ast-grep/ast-grep, sourcebot-dev/sourcebot, cocoindex-io/cocoindex, AsyncFuncAI/deepwiki-open, bb-boy680/open-zread, mostlygeek/llama-swap, asg017/sqlite-vec, openclaw/openclaw, joshrotenberg/mcp-proxy

## Non-goals (found, deliberately rejected)

- **chaitin/agent-compose** — AGPL; pattern noted, no code.
- **basicmachines-co/basic-memory** — AGPL + overlap with adopted memory stack.
- **TencentCloud/TencentDB-Agent-Memory** — NOASSERTION + vendor notice.
- **R0Wi/mcp-gateway** — 2★, unproven; CIMD/OAuth-2025-11 noted as protocol watch-item.
- **microsoft/acon** — stale research direction.
- **sqlite-vec replacing turbovec** — turbovec is a core dep; sqlite-vec registered for future SQL-native stores only.
- **Media/business domains** — prior studies saturated; nothing new worth taking.
- **Full multi-harness adapter framework** — 4 export targets don't justify a matrix engine yet.
