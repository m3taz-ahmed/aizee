# Study — Animate + RammCodes Skill Ecosystem (Agent-Native Video, Skills as Programs)

**Date:** 2026-11-15
**Scope:** `cth9191/animate` deep study + FB profile 61554891783841 (RammCodes) featured content + adjacent skill ecosystem
**Clone dir:** `temp/*-study/` (depth-1): animate-study, motion-design-study, scroll-world-study, reanimate-study, open-edit-study, superpowers-study, mattpocock-skills-study, vercel-skills-study, wshobson-agents-study
**Status:** research only — no adoption implemented. Backlog below is AGREED, pending "نفّذ".

---

## 1. Profile: RammCodes (Ram Maheshwari)

FB 61554891783841 = curator/reposter of viral open-source agent skills (~500k followers across FB/IG/Threads/X/LinkedIn). Login-walled; content recovered via cross-posted search. Featured repos traced and cloned. Same niche: "Claude Code / Codex skills that make videos, animations, UIs".

## 2. Repos studied

| Repo | ★ | License | Core idea | Golden artifact |
|------|---|---------|-----------|-----------------|
| cth9191/animate | ~1.9k | MIT | Procedural animation skill: one canvas, deterministic seeded render, canvas→ffmpeg MP4, voice via faster-whisper, procedural score | `tools/review.mjs` measured gate + 3 cheap HITL checkpoints before expensive build |
| cth9191/motion-design | — | MIT | 10 immutable source-prompt presets → adapt → Higgsfield MCP video | `source-prompts/*.txt` hash-locked film specs (palette, seam-as-in-world-event, exact-copy list) |
| cth9191/scroll-world | — | MIT | Scroll-scrubbed fly-through landing pages | Actual-frame handoff doctrine + SSIM seam gate ≥0.90; blob-URL seekability; previz cheap tier |
| NiazMorshed2007/reanimate | — | MIT | Reverse-engineer any animation into user's codebase with proof | capture→spec.md(rows=checks)→build→verify loop; identical-viewport doctrine; fidelity levels; ≤5 rounds then report |
| veedstudio/open-edit | 1.8k | Apache-2.0 | Agent editing pipeline: HTML page = the edit, virtual-clock renderer | `transcript.json` single seam; MediaPipe faces.json text placement; `--from/--to` incremental re-render; Money gate (quote→`--approve`→spend report) |
| obra/superpowers | 70k+ | MIT | Methodology-as-skills: brainstorm→design→plan→subagent-driven TDD | `using-superpowers` bootstrap skill; eval-gated skill content (superpowers-evals/Quorum); AGENTS.md 94%-rejection PR discipline |
| mattpocock/skills | — | MIT | 20 eng + 17 misc/productivity skills, composable | grill-me/grill-with-docs (shared-language glossary+ADRs), to-spec→to-tickets→implement-spec, improve-codebase-architecture survey |
| vercel-labs/agent-skills | — | MIT | 9 official skills w/ rule-count checklists | web-design-guidelines 100+ rules, writing-guidelines 80+, react-best-practices 40+; per-skill immutable release + discovery index |
| wshobson/agents | 42.5k | MIT | 94 plugins/202 agents/185 SKILL.md | SSOT → 7 harnesses via `tools/adapters/` + capabilities matrix |
| anthropics/skills | 194k | — | Canonical upstream | `spec/agent-skills-spec.md` → agentskills.io/specification; `template/`; skills/ catalog |
| yihui-dev/awesome-opus5-5-videos | — | — | 703 video prompts + 418 live remakes | prompts/*.md + data/videos.json + skillry.dev remakes — "proven prompt" dataset pattern |

Also found (not cloned): VoltAgent/awesome-agent-skills (1k+), ComposioHQ/awesome-claude-skills (1k+), sickn33/agentic-awesome-skills (2957, `gh skill install`), nodegenie/awesome-agent-skills (2043, usethisskill.com A/B "proven" badges), skills.suedeai.ai directory (3868 graded 0-99), remotion-dev/skills (13 official), VoltAgent/awesome-design-md, nextlevelbuilder/ui-ux-pro-max-skill.

## 3. Adoption backlog — AGREED, pending implementation

Approved by user: "عايز اخد كل اللي نقدر ناخده والمهم لينا" + "موافق لاكتر من كده كمان". Execute on "نفّذ".

### P1 — Patterns (map to existing aiZee subsystems)

| # | Pattern | Source | Proposed aiZee target |
|---|---------|--------|----------------------|
| 1 | Measured-completion gate (numbers not prose: SSIM/LUFS/frame-diff/cut-grid) | animate review.mjs, scroll-world SSIM, reanimate compare | New `runtime/measured_gate.py` or extend eval — deliverable checks return metrics, agent cites them |
| 2 | HITL ordering cheap→expensive (anchor still→batch, storyboard→build, previz→final) | animate, scroll-world | Workflow pattern for costly fan-outs: `plan` step type `preview_gate` |
| 3 | Determinism discipline (seeded RNG, virtual clock, identical-capture doctrine for fair compares) | animate core.js, reanimate | Rule in rules/: any eval comparing outputs must fix viewport/seed/clock; eval harness flag |
| 4 | Single-artifact contract (one index.html / runs/<key>/ / .reanimate/<name>/ evidence dir) | all video skills | Convention for generated deliverables + evidence retention in eval/runs |
| 5 | Immutable source artifacts + hash verify | motion-design sha-checks | Extend `aizee skill lock-*` to arbitrary reference assets |
| 6 | Money gate: quote→single-use `--approve`→spend report on delivery | open-edit, scroll-world spend estimate | `aizee check` budget extension for paid-API calls; policy rule pending in runtime |
| 7 | Idempotent pipelines (re-run skips finished assets) | scroll-world pipeline.md | Plan-runner step dedupe by output-hash |
| 8 | IP/reference-media discipline (local only, gitignored, never committed) | animate new-style.md | rules/security: add reference-media rule |
| 9 | Skill-behavior evals gate wording changes (before/after evidence required) | superpowers-evals/Quorum | Extend `aizee eval` to skill-diff regression: changing skill text requires eval pass record |
| 10 | Bootstrap/meta skill (`using-superpowers` auto-loads at session start + post-compaction) | superpowers | Equivalent: global-roles already does this; add post-compaction re-inject note |
| 11 | Shared-language glossary + ADRs from intake ("materialization cascade" vs 20 words) | mattpocock grill-with-docs | workflow: intake produces CONTEXT.md glossary per project |
| 12 | User-invoked vs auto-triggered skill taxonomy | mattpocock Reference axis | skills/ frontmatter field `invoke: user\|auto` |
| 13 | Grill/intake as first-class skill (align before build) | grill-me, animate intake.md, scroll-world interview | Adopt intake protocol into workflows (already partially in spec_engine) |
| 14 | Per-skill immutable release + discovery index artifact | vercel scripts/build-discovery-index | `aizee skill link` emit discovery index + release hash |
| 15 | Rule-count audit checklists (100+ numbered rules, severity categories) | vercel web/writing guidelines | Validates compressed-rules approach; consider numbered `[R-nn]` IDs for audit skills |
| 16 | Multi-harness SSOT→adapters capabilities matrix | wshobson tools/adapters | Compare vs `aizee skill link --pack` coverage (claude/codex/cursor/opencode/windsurf/devin) |
| 17 | "Your human partner" voice + Red-Flags/rationalization tables = behavior code | superpowers writing-skills | writing-skills rule for aiZee skill authors |
| 18 | Verification-before-completion skill | superpowers | Already = quality gate; add "show the evidence" phrasing contract |
| 19 | dispatching-parallel-agents + subagent-driven-development (fresh agent per task + review each) | superpowers | Map to `aizee plan` fan-out + per-step review |
| 20 | Proven-skill badges (A/B runs w/ and w/o skill, recorded model+commit) | nodegenie/usethisskill | eval/harness: optional skill-efficacy scenario that records before/after |
| 21 | Bounded correction loop: 2–5 rounds then STOP and report with numbers (never lower threshold silently) | reanimate | rules: correction-loop cap + escalate-with-evidence |
| 22 | Spec rows = checks (spec.md row→verify item, "?" = unfinished reading) | reanimate analysis.md | spec_engine: checklist items derived from spec rows |

### P2 — Candidate direct adoptions (skill packs to port/install)

- `obra/superpowers` core loop (brainstorming→writing-plans→subagent-driven-development→tdd→verification) — overlaps spec_engine; mine for wording/red-flag tables.
- `mattpocock/skills`: grill-with-docs, to-spec→to-tickets→implement-spec chain, diagnosing-bugs, improve-codebase-architecture, wayfinder, handoff, writing-for-agents.
- `vercel-labs/agent-skills`: react-best-practices, web-design-guidelines, writing-guidelines — as tech-stack audit references.
- `animate` skill itself — full pipeline could run under Devin (uses .claude/skills layout + Node tools; port = point skill loader at plugins/animate/skills/animate).
- `reanimate` — Bun + Playwright capture/compare scripts are standalone-portable.
- `cth9191` animate/motion-design/scroll-world = one author's three-skill suite (procedural / AI-gen / hybrid) — worth tracking upstream.

### P3 — Watchlist (directories/influencers for future sweeps)

VoltAgent/awesome-agent-skills, ComposioHQ/awesome-claude-skills, sickn33/agentic-awesome-skills, nodegenie (usethisskill.com), skills.suedeai.ai, skills.sh/.lc/skillsf.com/qai.io, anthropics/skills releases, obra/superpowers-marketplace, @ramzcoder, @moritzkremb, Ben Pierron, RammCodes (FB/IG/Threads/X/LinkedIn), skillry.dev remakes.

## 4. Notes

- FB access blocked by login wall — all findings via indexed cross-posts; no auth bypass attempted.
- reanimate IP note: skill clones copyrighted sites' motion — fine for motion-faithful internal use; pixel-faithful of others' assets needs care (rule 8 covers media).
- wshobson/agents already registered in useful-repos (Skill Upstreams); new: adapter matrix detail + local clone path.
- Temp clones kept at `temp/*-study/` for the implementation phase; clean after adoption decisions land.
