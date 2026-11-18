# Study — Stickman Video Director + ApkStart (User-Submitted Pair)

**Date:** 2026-11-18
**Scope:** 2 user-submitted repos — agent-skill video pipeline + Windows Android runner; extract adoptable patterns + direct-use value
**Clone dir:** `temp/stickman-video-director`, `temp/apkstart` (depth-1; purged after vendoring — this report is the evidence record)
**Candidates studied:** 2 cloned, both deep-read (README + architecture + core modules + tests + manifests)
**Personas:** PLAY (primary) + DEVOPS + UX

---

## Inventory

| Repo | ★ | Lang | License | What |
|------|---|------|---------|------|
| kaomei/stickman-video-director | 6.9k | MD+JS/Py | MIT | Agent **skill package**: script→stickman video across 14 styles (A1–A7 model-engine, B1–B7 autopilot local renderer). SKILL.md router + 76 `references/` contracts + 57 `scripts/` + sha256-locked baseline `assets/` + `agents/openai.yaml` harness binding + per-gate `verify-*.py` |
| RoutineMiku/apkstart | 7.8k | JS (Electron) | MIT | Windows APK runner: double-click `.apk` → install → per-app desktop icon → standalone freeform window. Zero-dep shell (hand-written zip/axml/arsc/png/ico), self-hosted QEMU runtime, multi-source speed-tested updater, `doctor`/`autodebug` self-healing, JSON `drivers` machine-fingerprint patches |

## Per-repo evidence → pattern

### stickman-video-director

| Evidence | Location | Pattern |
|----------|----------|---------|
| One `SKILL.md` routes to per-style contract docs; A vs B boundary rules | `SKILL.md` + `references/mode-execution-boundaries.md` | Skill-internal mode routing with explicit boundary contract — same shape as our skill/workflow split |
| "Inspect the actual MP4/decoded playback — technical checks are not acceptance" repeated per style | `references/b6-sample-1-acceptance.md` (35 mandatory subchecks), `autopilot-production-qa.md` | **Actual-output acceptance gates**: artifacts reviewed as rendered output, not exit codes |
| `approved-baseline.json` — schema + per-evidence `sha256` + portability assert (paths can't escape skill dir) | `tests/verify-b1-baseline.py`, `assets/b1/approved-baseline.json` | Baseline-evidence manifest = our `skills-lock.json` idea pushed down to per-skill asset level |
| Phase-gated behavioral checklist for the *agent* (SETUP-1..REV-2) | `tests/evaluation-rubric.md`, `tests/scenarios/` | Skill-behavior eval rubric — parallel to `eval/vibe.py` scenarios |
| Cross-harness binding: `interface: display_name + default_prompt + $skill ref` | `agents/openai.yaml` | OpenAI-agent packaging target our `harness_exporter` lacks |
| 8 localized READMEs + `verify-localized-readmes.py` | `README.*.md` | Localization parity as a tested invariant (we have EN+AR only) |
| Staged workflow: confirm→storyboard→approve→produce; prompt delivery is a valid stopping point | `references/a1-a5-direction.md` | Approval checkpoints as first-class stages — matches our `aizee plan` suspend gates |

### apkstart

| Evidence | Location | Pattern |
|----------|----------|---------|
| `apkstart-driver/1` JSON: `match` on machine fingerprint (platform/accel) → `effect` on whitelisted params only, no code exec | `src/drivers/*.json`, `src/core/drivers.js` (651 LOC) | **Driver patches**: declarative environment-fingerprinted config overlays — safe to import/enable/disable |
| Autodebug doctrine: "probe failure is not a problem" (report unknown, never false-alarm) + "notify once" (new issues alert, old ones don't re-ping) + one-click fix + auto recheck | `src/core/autodebug.js` + `autodebug-probe.js` + `doctor.js` | Self-healing diagnostics with honest-unknown state and notify-once UX — our `doctor` reports but doesn't heal |
| Update source selection: probe GitHub+Gitee → real 256 KB speed test (excludes handshake) → ranked parallel chunked download + resume | `src/core/updater.js`, `sources.js` | Measured multi-source failover — our installers are single-source |
| Preflight: probe CPU virt/GPU/RAM → auto-write config → persist as driver | `src/core/preflight.js` (467 LOC), `docs/preflight.md` | Capability-detect → auto-config — e.g. our embedder choice (fastembed vs sentence-transformers) on 6 GB boxes |
| Dedicated adb port 5044 so user's own adb/emulators never collide | README, `src/core/adb.js` | Port/resource namespacing of bundled tools |
| Offline `AndroidManifest.xml` AXML parse → per-app orientation pick → panel size chosen at launch | `src/core/axml.js`, `apk.js` | Offline binary manifest parsing before provisioning — decide-before-boot |
| `npm run selftest` = end-to-end acceptance command (install→launch→foreground→screenshot) | `scripts/selftest.js` | Single command that proves the whole pipeline — our `eval/harness.py` is the analog |

## Cross-cutting → aiZee map

| Pattern | Source | aiZee today | Disposition |
|---------|--------|-------------|-------------|
| Full agent skill (video production) | stickman `skills/directing-stickman-videos` | no video-production skill | **ADOPTED** — vendored to `skills/directing-stickman-videos/` (media-light: AV+raster excluded, see `AIZEE.md`), triggers+personas added, lock 248, `aizee find` top-hit verified |
| Baseline-evidence manifest (per-skill asset sha256 + portability assert) | `approved-baseline.json` + verify-b1 | `skills-lock.json` hashes whole skill dir only | Proposed — optional `assets-manifest.json` convention for skills shipping binary evidence |
| Behavioral eval rubric format (gated phase checks) | `tests/evaluation-rubric.md` | `eval/vibe.py` scenario dirs | Proposed — adopt rubric table as skill-QA template for new skills |
| `agents/openai.yaml` harness target | stickman `agents/` | `harness_exporter` targets claude/codex/cursor/opencode/devin | Proposed — add `openai` emit (interface/display_name/default_prompt) |
| Driver-patch JSON (match→effect whitelist) | `src/drivers/*.json` | no env-fingerprint config mechanism | Proposed — `runtime/machine_profile.py` + `drivers/*.json` overlay for env-tuned defaults (embedder, workers, GPU) |
| Autodebug doctrine (honest-unknown + notify-once + auto-recheck) | `autodebug.js`, `doctor.js` | `aizee doctor` = snapshot checks only | Proposed — persistent findings store + notify-once + fix actions in `doctor_tools` |
| Multi-source measured failover downloader | `updater.js`/`sources.js` | installers/downloaders single-source | Proposed — shared `download.py` util (256 KB probe, resume, ranked sources) |
| Local APK testbed for PLAY persona | whole apkstart repo | none | Direct-use — install release binary when needed; no code vendored (Electron app, not a library) |
| Localization parity test gate | `verify-localized-readmes.py` | EN+AR READMEs, no parity check | Proposed — `check-docs`-style gate asserting section parity across `README*.md` |

## Ranked adoption candidates (Ponytail filter)

1. **Vendor `directing-stickman-videos` skill** — ADOPTED. Media-light import (15 MB code/docs/fonts vs 497 MB upstream); A-mode fully functional, B-mode functional minus bundled media (disclose per its own contract); `LICENSE-UPSTREAM` + `AIZEE.md` vendoring note included.
2. **Doc-drift correction** — ADOPTED this session: `AGENTS.md` (248 skills, 53 tools, 233 mypy files, ~8,000 tests) + `README.md`/`README-AR.md`/`spec.md` (53 tools, 248 skills, 90 doctor checks) + adapter resync via `scripts/sync-agent-configs.py`.
3. **Driver-patch mechanism** — ADOPTED 2026-11-18: `runtime/machine_profile.py` + `runtime/drivers.py` (`aizee-driver/1`, whitelisted `embedder`/`xdist_workers`/`gpu_enabled` effects, fail-closed), wired into `memory/vector.py` + `aizee test`; `aizee drivers` inspector; `drivers/*.json` ships disabled.
4. **Autodebug notify-once findings store** — ADOPTED 2026-11-18: `runtime/doctor_findings.py` (StorageFactory JSON at `state/doctor-findings.json`); `aizee doctor` diffs every run — new ping once, persisting silent, recovered `resolved_at`; `--json` additive `findings` key.
5. **`openai` target in harness_exporter** — ADOPTED 2026-11-18: `emit_openai_binding()` + `aizee skill emit-openai <name>` writes `agents/openai.yaml` into directory skills (safe YAML, `$skill` prompt).
6. **Multi-source downloader util** — proposed; benefits installer/update paths.
7. **README localization parity gate** — ADOPTED 2026-11-18: `runtime/readme_parity.py` inside `aizee check-docs` — heading-level sequence, badge numbers, table rows, fences; immediately caught real README-AR drift (missing installer-map table + `git+` install block).

Rejected: vendoring apkstart code (Windows-only Electron app — direct-use tool, not a library); importing the 485 MB media payload (repo bloat; A-mode unaffected); `skills/` full-asset baseline manifests as mandatory (opt-in only — most skills have no binary evidence).

## Licensing

- **Vendored with attribution (MIT):** `skills/directing-stickman-videos/` — `LICENSE-UPSTREAM` vendored; `AIZEE.md` documents scope + upstream URL + re-vendor path.
- **Patterns-only:** apkstart — read for patterns (drivers/autodebug/updater); MIT anyway but nothing copied.
- Both repos' content (strings/docs) treated as data; no directives from them followed.

## `tech-stack/useful-repos.md` additions

(applied alongside this study)

## Non-goals

- **apkstart code reuse** — Electron/Windows-only; kept as direct-use testbed.
- **Full-media vendor** — 485 MB binaries would permanently bloat a public PyPI repo (MANIFEST ships `*.md` only anyway).
- **Persona yaml wiring** — skill discovered via `aizee find` + frontmatter `personas:` per convention; no `personas.yaml` primary-skill slot claimed.
