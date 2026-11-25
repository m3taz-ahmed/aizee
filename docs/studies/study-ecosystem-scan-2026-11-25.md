# Ecosystem Scan — 2026-11-25

**Scope:** full-taxonomy scout for repos/patterns aiZee should adopt (deep-research-prompt v2.0)
**Run date:** 2026-11-25 · **Source window:** recency cutoff 2026-05-25 (6 months)
**Preset/controls:** standard preset narrowed by SESSION_BUDGET=harness-default; CLONE_GATE=auto-after-shortlist; VALIDATION=normal; HARDWARE_PROFILE=low-resource local; CLEANUP=purge-run-clones-after-report
**Run workspace:** `temp/repo-research-2026-11-25/`
**Counts:** 19 discovery queries logged · 83 candidate rows · 15 shortlisted · 15 cloned (~350 MB actual after sparse/blobless reduction) · 3 full deep-reads · 12 digest/structure-level · cleanup: done
**Propagation:** user-approved ("اسحب المفيد وانقله عندنا") — implemented items marked ✅ below

---

## 1. Executive summary

The strongest 2026 signal is **evidence-gated skill engineering**: microsoft/SkillOpt (NeurIPS 2026 Spotlight) trains natural-language skills with epochs/validation gates in text space, and converges with the already-agreed animate-study backlog (proven-skill badges). aiZee had no measurement scaffold for skill efficacy — **this gap is now closed** (✅ `runtime/skill_efficacy.py`). Second: the old animate backlog is **mostly already implemented** in v6.14 (measured_gate, money gate, skill index, derive-checklist, intake-glossary, red-flag writing skills all verified present) — the honest gaps were narrow. Third: OS-level sandboxing (agent-safehouse) is macOS-only and platform-mismatched; agent gateway/runner infrastructure dominates the new repos but is largely infra-heavy or duplicative of aiZee's existing policy kernel.

**Biggest caveat:** 12 of 15 shortlist repos were read at digest/structure level only (context budget), so their rows below are hypotheses, not verified mechanisms. Adoption decisions rest on the 3 deep-reads plus static aiZee-side gap probes.

## 2. Adopted and implemented ✅

### 2.1 `runtime/skill_efficacy.py` + `aizee skill efficacy` — IMPLEMENTED

- **Pattern:** before/after A/B verdicts as append-only receipts (skill, scenario, verdict-with/without, model, commit, rig fingerprint) → badges `proven/flat/harmful/unmeasured`.
- **Sources:** microsoft/SkillOpt (validation-gated skill training doctrine, MIT, `dc0b5e654caf`); nodegenie/usethisskill badges; animate-study backlog row 20.
- **aiZee fit verified:** gap probe found zero efficacy/badge mechanism in eval/ — confirmed gap.
- **Implementation:** `runtime/skill_efficacy.py` (record/store/report, append-only JSONL at `state/skill-efficacy.jsonl`), CLI `aizee skill efficacy record|report|badges`, 11 tests in `tests/test_skill_efficacy.py`.
- **Evidence:** tests pass 11/11; ruff clean.

### 2.2 `skills/inference-optimisation/` — VENDORED (MIT)

- **Source:** sybil-solutions/inference-optimisation-skill @ `fda968e7fc19`, LICENSE.upstream included.
- **Why:** hill-climbing local LLM serving with measured ceilings (device-to-device bandwidth, not spec sheets), one-change-at-a-time A/B against interleaved controls, failure logging, full-context stability gates, pinned-build qualification. Perfect doctrinal fit with aiZee's measured-evidence rules; fills the local-inference tuning gap (`aizee models` is metadata-only).
- **Adaptation:** aiZee frontmatter (personas DEVOPS/SRE/DEV) added; scripts/references vendored unmodified.

## 3. Verified already-covered (no work needed)

Gap probe evidence (2026-11-25): measured-completion gate → `runtime/measured_gate.py`; money gate → `runtime/budget.py` quote/approve; spec rows→checks → `runtime/spec/scaffold.py` derive-checklist; intake glossary → `workflows/67-intake-glossary.md`; correction-loop caps + determinism rules → `rules/anti-patterns.md` et al.; red-flag writing guidance → 11 skills; discovery index → `runtime/harness_exporter.py`; HITL approval gate → `call_plan` `suspend` op with resume tokens; durable event log → `runtime/event_bus.py`; sandbox-adjacent mediation → `runtime/agent_gateway.py`, `mcp_firewall.py`. The animate-study P1 backlog is therefore **closed as implemented** except items folded into §4.

## 4. Deferred adoption backlog (evidence-ranked)

| Pri | Item | Source repo (commit) | Why deferred |
|-----|------|----------------------|--------------|
| P1 | Skill-optimization loop: iterative skill-text mutation with validation gates (SkillOpt's epochs/batch doctrine) using skill_efficacy as the measurement substrate | microsoft/SkillOpt `dc0b5e654caf` | needs live-model evaluator design; scaffold now exists |
| P1 | Cross-harness tool-call policy proxy — aiZee kernel mediating third-party harness traffic, not just own actions | solongate/agent-security `263226fe9d2f` (Apache-2.0), TheLunarCompany/lunar `4d8aff0e0c99` (MIT) | digest-level only; architecture decision needed |
| P2 | Typed durable-execution event log for plan runs (append-only history, resumable runs beyond suspend tokens) | TanStack/workflow `30511ade64f4` (MIT) | overlaps event_bus/replay; needs consolidation design |
| P2 | Skill registry: versioned publish/governance/distribution workflow beyond lock+index | iflytek/skillhub `045a20377a21` (Apache-2.0) | distribution is not yet a bottleneck |
| P2 | Unified heterogeneous local index (code+docs+logs+JSONL, one binary) | xerj-org/xerj `7ba0069e4e48` (Apache-2.0) | overlaps memory/+graphify; digest-level only |
| P2 | Structural code intelligence freshness ergonomics | Muvon/octocode `a789880f4f62` (Apache-2.0) | graphify already covers; incremental |
| P3 | Editor/agent client protocol adapter | agentclientprotocol/agent-client-protocol `134241fd4858` (Apache-2.0) | wildcard; no editor integration demand yet |
| P3 | Generative-UI client protocol for production frontends | CopilotKit/CopilotKit `7f7ba6ff6d1e` (MIT) | ui_concepts exists; large surface, no project pulling it |
| P3 | Long-horizon harness envelopes + meta-harness orchestration | bytedance/deer-flow `aa9913c4cc2d`, omnigent-ai/omnigent `6bc4e348f7e0` | platform-scale; digest-level only |
| P3 | Distributed event-driven workflow control plane | conductor-oss/conductor `8006242289a9` | infra-heavy; violates Ponytail for local-first aiZee |
| P3 | Harness run capture/reliability scoring | FailproofAI/failproofai `7ffd6dbcc4bf` | license NOASSERTION — reference-only unless clarified |

## 5. Rejected finds (one line each)

- eugene1g/agent-safehouse — deep-read: macOS `sandbox-exec` only; platform mismatch (deny-first composable profiles doctrine already in aiZee policy kernel). **Rejected for adoption, doctrine noted.**
- adithyan-ak/AgentHound, pikpikcu/airecon — offensive-security orientation; out of scope for adoption scan.
- Business/SEO/blog skill packs (notfair-plugin, claude-blog, opc-skills) — saturated domain, low marginal value.
- spec-driven clones (spec_driven_develop, shotgun, cabloy) — aiZee spec_engine already deeper.
- dapr/quickstarts, synergycodes/workflowbuilder, durable-workflow/workflow — infra/framework mismatches.
- getsentry/MobileBuildMCP, jacob-bd/gemini-notebook-mcp-cli — narrow single-vendor tools.

## 6. Contrary-evidence pass

For the two adopted items: SkillOpt — no abandonment signals (NeurIPS 2026 Spotlight, active Nov 2026, 151 test files); license MIT verified in-repo. inference-optimisation — single-author and very young (created 2026-11-16, 32 KB); mitigation: vendored as-is with upstream license, zero runtime coupling, deletion cost ≈ 0. agent-safehouse rejection verified in-repo (`sandbox-exec`, macOS-only CI badges). No security red flags observed in vendored files (scripts are bench/queue helpers, no network exfiltration; static reading only — nothing executed).

## 7. Scan statistics and reproduction

- Queries: `temp/repo-research-2026-11-25/queries.md` (19 rows; one tooling false-start: gh api requires explicit `--method GET` for search — recorded in errors.md).
- Candidates: `candidate-ledger.md` (83 rows incl. 8+ duplicates against the dedupe registry).
- Shortlist: `01-shortlist.md` (15 rows, full scoring schema). Clone manifest: `clone-manifest.md` — all 15 cloned, no quarantines.
- Dedupe caveat: the skip-list is heuristic (1050 raw entries incl. false positives); duplicates were treated as hints and hand-checked.
- Dry domains: media pipelines (0 results — saturated), docs/onboarding (3 weak hits), business (rejected as saturated).
- Coverage honesty: harness/MCP/skills/evals/security/UI/devtools/inference/automation/distribution/protocols scanned; spec/media/business skimmed by design (deep prior coverage).
- Cleanup: run clones purged after this report; digests/ledgers/manifests retained in the workspace.
