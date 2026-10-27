# aiZee — Active Context / Handoff

**Repo:** `aizee` (branch `main`) — version 6.5.0
**Last checkpoint:** 2026-10-15 — Second maintenance cycle DONE + external-research integration pass (ECC/agent-reach/auth-for-laravel).
**Next:** commit (pending user approval), then `update_aizee.bat` sync to deployment mirror.
**Gates (maintenance cycle):** all green — ruff ✓, mypy 599 files ✓, `aizee test --full` 7060 passed / 3 env-skips / 100% cov ✓, `eval/harness.py` all_pass=true ✓, `validate-globals` 0 errors ✓.
**Gates (research pass):** ruff ✓, mypy (touched files) ✓, focused pytest ✓ — FULL suite + harness pending.

## External-research integration (this session)

Selective adoption from `affaan-m/ecc`, `Panniantong/agent-reach`,
`roundly-consulting/auth-for-laravel` — ideas only, no vendored code:

- **`security mcp` deepened** — secrets in `args`, more token prefixes
  (`github_pat_`, `xox*`, `AIza`, `pk_live`…), unpinned pkg + writable-path
  detectors, no duplicate flag/value findings.
- **Prompt-defense baseline** — every emitted harness rules file now
  carries a fixed anti-injection section (identity lock, secrets,
  untrusted external content, unicode tricks). Not counted in
  `rules_emitted`.
- **`fact_force` guardrail** — recoverable destructive ops (force-push…)
  require explicit facts {target, rollback}; catastrophic commands still
  hard-blocked.
- **Memory handoffs `aizee.handoff.v1`** — `memory handoff/handoffs`;
  scoped vaults (project=`brain/` fail-closed gitignored, user=`~/.aizee`).
- **Instincts `aizee.instinct.v1`** — `instinct-add/-reinforce/instincts`;
  confidence 0.3→0.9, auto-promote project→user at ≥2 projects; via
  `MemoryStore.update_meta` (re-signs row).
- **Docs** — `tech-stack/auth-for-laravel.md`, `docs/INSTALL_CONTRACT.md`
  (agent-readable `aizee.install.v1` boundaries).
- **Rejected** (Ponytail): Plan Canvas/Control Pane UI, GitHub App layer,
  311-skill bulk import, npm dependency.

⚠️ Gotcha found this pass: `--project`/`--root` must point at the working
repo for dev writes — a default `AIZEE_ROOT` aimed at the deployment
mirror routes handoff/store writes into it. Mirror artifact was cleaned.

---

## ✅ Done this cycle (Unreleased)

- **Version drift fixed** — `pyproject.toml`/config fallback → 6.3.0; CHANGELOG `[6.3.0]` section.
- **Manifest lock hardened** — fingerprints now cover `description + inputSchema` (rug-pull via schema drift detected; re-baseline: delete `state/mcp_locks/aizee.json`).
- **`aizee security mcp`** — `McpAuditor` (14 detectors) wired to CLI; JSONC-tolerant config parsing; `--lock` persists rug-pull baselines.
- **Supply-chain stage in `security scan`** — `SupplyChainGuard` runs on .py/.ts/.js/.php/.go/.rs; first-party/alias/sibling-aware (`sys.stdlib_module_names`, import↔dist map, go.mod module, composer psr-4); honors `aizee-scan: ignore[-file]` markers; also surfaced pre-write via `lint_python` advisory (`scan_source`).
- **MCP tool annotations** — 31 tools carry `readOnlyHint`/`idempotentHint`/`destructiveHint` via `_annotate_tools()` post-registration.
- **22 orphan runtime modules deleted** (129→107 canonical) — `budget_escalation`/`service_catalog` were mislabeled (real callers) and stay; `ORPHAN_MODULES` now empty; `manifest.json` module map cleaned.
- **Scanner dedup** — same (rule,file,line) collapsed; bandit/ruff same-line sinks report once.
- **Deps refreshed within pins** — mcp 2.3.0, pydantic 2.14.1, cryptography 50.0.2, turbovec 1.1.2, graphifyy 0.9.91, ruff 0.17.1, mypy 2.4.0.
- Counts: runtime 107 / skills 140 / numbered wf 63 / stack 265 / tests ~7.0k.

- **v6.5.0 star-repo adoption pass complete** — verify dial (off/final/checkpoints/strict) on `kernel.act`, structured `doctor` engine (CLI --json + MCP `aizee_doctor`), uniform tool envelope, `find`/`goal` NL discovery, governed `gateway_proxy` (failover + enforcement on the LLM path), opt-in `output_filter` token compression, OpenSpec-style `specs/changes/` folders, `rules/ingest.yaml` memory routing, `config show --masked`/`apply --check`, root `SKILL.md` + `llms.txt` + `skill link`. Repo renamed to `m3taz-ahmed/aizee`; description/topics/discussions set; `v6.4.0` release published at 970fd78. PyPI publish + GIF + registries remain maintainer-side.
- Pytest coverage footgun: use path targets (`--cov=runtime/`), never module names — pytest-cov imports module targets early and `cryptography` PyO3 double-inits.
- **v6.5.0 star-repos batch-2 complete** — `aizee skill lint|scan` (authoring toolchain + security scan), `aizee hooks install|status|fire` (agentmemory harness hooks), `aizee abstract` (OpenViking L0/L1/L2 tiered loading), `SensitiveVault` + `kernel.act(sensitive_data=)` masking (browser-use), `GovernedApiSession` from curl/HAR (mimic), gateway `tiers` (flash/extraction), capture-time `secret_scrub` in ingest, `plugin.json` + README mcp-name marker.

### Gate status
- ruff ✅ mypy (205 files, strict) ✅ `aizee test --full` **7412 passed + 100.00% cov** ✅ `eval/harness.py` **all_pass** ✅ validate-globals (0 errors) ✅ `aizee skill scan` on self **ok (0 high)** ✅
- Pending: user approval to commit; PyPI publish + GIF + registries are maintainer-side.
- Generated `abstracts/` is gitignored (mirror tree, regenerates via `aizee abstract`); `skills/index.json` is gitignored too (regenerates via `aizee skill lint --write`).
- **Skill-library repair done** — `aizee skill lint` reports **141 skills / 0 issues / 0 collisions** (was 74+37). 73 skills got `triggers:` + `always: true` (triggers gate loading in `matches_context`; `always` preserves unconditional semantics). 43 negative triggers on colliding pairs; 5 files had unrecoverable Arabic mojibake (`O?U?`) replaced with valid triggers; `secret_scrub` prose-filter added (`Authorization: Distinguish…` FP).
- **Security review pass done** — `api_session` fail-closed: cross-host absolute URLs + cross-host 302 redirects refused (auth bundle can't leak); `extra_headers` masked into kernel gate. `gateway_proxy`: 10MB body cap + 64k prompt-gate window. `sensitive.mask_obj` preserves tuples. 7417 tests / 100% cov.
- graphify update refused overwrite (smaller graph — missing chunks); existing graph retained.

---

## ⚠️ Gotchas
- `aizee` PATH shim hardcodes `AIZEE_ROOT` to the deployment mirror — for working-repo runs use `python aizee_cli.py` or set `AIZEE_ROOT` explicitly.
- Scoped writes (`memory handoff`, `instinct-*`, `add`) resolve the *project* vault from `--project`/`AGENT_PROJECT_ROOT` — when `AIZEE_ROOT` points at the mirror, dev writes land there. Always pass `--root`/`--project` at the working repo for tests.
- Mirror `D:\server\aizee` is read-only; sync via `update_aizee.bat` only.
- validate-globals requires `[RULES]` marker in SKILL bodies; generated-artifact refs go in `IGNORED_FILE_REFS`.
- Never text-rewrite UTF-8 files via PowerShell (BOM/mojibake risk) — use Python.

> هذا الملف هو نقطة التوقف للاستمرار من اللابتوب. لا تبدأ أي مهمة جديدة قبل قراءته.
