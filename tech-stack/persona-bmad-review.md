# Persona System Review — aiZee vs BMAD (merged architecture)

Date: 2026-11-10. Scope: `runtime/persona.py`, `runtime/personas.yaml`, `runtime/skill_resolver.py`,
`runtime/rule_frontmatter.py`, `runtime/service_catalog.py`, BMAD agent/skill layer (vendored under `skills/bmad-*`).

## 1. How each system works

### aiZee personas (identity + routing + governance)

- `runtime/personas.yaml`: 29 personas with `name`, `weight`, `keywords` (EN+AR normalized),
  `primary_skills`, `extra_skills`, `lord_skills`, `persona_lord_bonus`, team definitions.
- `runtime/persona.py`: `PersonaDetector` normalizes Arabic variants/prefixes, scores personas by
  keyword hits in task text, returns primary + secondary personas, their skills, ranked lord skills,
  and detected teams. Context is injected via `persona_context`.
- `runtime/skill_resolver.py`: resolves skills from project `.ai/skills/` first, then root `skills/`;
  supports flat single-file skills and directory skills with `SKILL.md` entry points.
- `runtime/rule_frontmatter.py`: conditional skill loading via `paths`, `personas`, `stack`,
  `triggers`, `tech_stack`, `always` (OR across groups; absent condition = match).
- Integrity: `skills-lock.json` hashes every skill; `skill_validator` + `skill_lint` enforce
  frontmatter, naming, size, trigger quality; `eval/harness.py` runs behavioral scenarios.

### BMAD agents (lifecycle execution + artifacts)

- 6 named agents: Mary (analyst), John (PM), Winston (architect), Sally (UX), Sofia (PO), Amelia (dev).
- Lifecycle depth: requirements → PRD → architecture → UX → story breakdown → implementation → review.
- Persistent state: `_bmad/config.toml`, `_bmad-output/` ticket tree (initiative→epic→story),
  `persistent_facts`, memlog, party-mode round-table.
- Skills are execution protocols: each references `{project-root}/_bmad/scripts/*` for config
  resolution, roster, customization, memory.

## 2. Comparison

| Dimension | aiZee | BMAD | Winner / note |
|---|---|---|---|
| Detection | Keyword scoring, AR+EN, multi-persona | Explicit invocation or description-trigger | aiZee better for routing |
| Identity depth | Persona = routing label + skill set | Named character with persona text, voice, memory | BMAD better for role-play fidelity |
| Lifecycle state | None (stateless per task) | Initiative/epic/story tree, memlog, persistent facts | BMAD only |
| Handoffs | Implicit via persona set | Explicit agent-to-agent in party-mode | BMAD better structured |
| Governance | Kernel gates, budget, audit, probity, lock | None (relies on host agent) | aiZee only |
| Language | Bilingual AR/EN normalization | EN-centric | aiZee better for this user |
| Artifact production | Skills are instruction docs | Templates + scripts + ticket tree | BMAD deeper |
| Integrity | Lock + validator + lint + eval | Upstream repo trust | aiZee stronger |

## 3. Merged architecture (implemented)

```
Input  → aizee persona detect --multi   (AR/EN keyword scoring → persona set + skills + lords)
Route  → SkillResolver (project .ai/skills first; flat+dir; frontmatter conditions)
Execute→ BMAD agents/workflows for lifecycle depth (tickets, templates, handoffs)
Govern → aiZee kernel gates (probity→guardian→policy→loop→budget→audit)
Memory → BMAD persistent_facts/memlog + aizee memory ingest
Integrity → skills-lock.json (244 skills) + validator + lint + eval
```

Separation of concerns: aiZee = who/what-governed; BMAD = how-deep. No persona duplication —
aiZee personas map to BMAD phases (PRODUCT→pm, ARCH→architect, DEV→dev, QA→code-review, UX→ux-designer).

## 4. Findings / gaps

1. **No lifecycle stage awareness.** `persona detect` is stateless — it cannot prefer
   phase-appropriate personas (e.g. mid-initiative, prefer PO/architect over analyst).
   BMAD tracks initiative state; aiZee does not read it.
2. **Keyword collisions possible.** e.g. "login page" hits UX, DEV, SEC simultaneously.
   Mitigated by multi-persona return + weights, but no explicit disambiguation UX.
3. **Imported-skill persona mapping is heuristic.** 86 external skills received generated
   `personas`/`triggers`. Some mappings are approximate (FINOPS→performance-engineer,
   MLOPS→ml-engineer share skills). Acceptable but worth periodic review.
4. **No explicit handoff protocol.** When a task crosses domains (analysis→architecture→dev),
   aiZee returns a persona *set* but does not sequence the handoff or persist stage.
   BMAD party-mode has richer handoff semantics.
5. **Context budget.** 244 skills indexed by `service_catalog`; persona detect returns bounded
   sets so injection stays small, but `aizee find` quality depends on trigger richness —
   imported skills have generated triggers (single-word EN + a few AR) vs hand-tuned aiZee ones.
6. **Lord skills vs BMAD agents are complementary, not duplicative** — lords review/oversight,
   agents execute. Keep both.
7. **`_bmad/` runtime contract preserved** — skills hardcode `{project-root}/_bmad/scripts/*`;
   renaming would break all 34 BMAD skills. Kept as project-local runtime (gitignored).

## 5. Recommendations (prioritized)

1. **Lifecycle-aware routing (high).** Add optional `lifecycle_stage` to detect context;
   when `_bmad-output/` shows an active initiative, bias persona selection toward the current
   BMAD phase. Implementation: small addition in `persona.py` reading `_bmad/config.toml`
   `active_initiative` + epic/story state.
2. **Handoff convention (high).** Adopt BMAD's agent-handoff pattern as an aiZee convention:
   persona context emits `next_persona_hint` when task text signals phase transition
   ("now implement" → DEV, "review the design" → ARCH+QA).
3. **Eval coverage for collisions (medium).** Add skill-scenario evals for top collision pairs
   (UX/DEV/SEC on auth pages; MARKETING/GROWTH/CRO on landing pages; DATA/ML on pipelines).
4. **Trigger enrichment pass (medium).** Improve generated triggers on imported skills:
   add AR variants + domain phrases; run `skill_lint` trigger-quality checks after.
5. **Upstream sync procedure (low, documented).** BMAD updates: re-run `npx skills add` to temp,
   diff against `skills/bmad-*`, copy changed files, `skill lock-update`. `_bmad/scripts`
   refresh via setup script. No global install needed.
6. **Persona merge candidates (low).** FINOPS and MLOPS share primary skills with PERF/ML —
   consider whether they earn distinct personas or should fold into teams. Decide after eval data.

## 6. Verification status

- `skills-lock.json`: 244 locked, 0 changed/missing/unlocked.
- `validate-globals.py`: 1241 scanned, 0 errors (796 warnings = intentional template/runtime refs).
- `check-docs`: 1337 docs, 0 broken links.
- Mirror `E:\server\aizee` synced via `scripts/update_aizee.bat` (read-only deploy).
- Global `~/.agents/skills` emptied after migration; project-level `.agents/skills` junctions
  (194 dir + 50 flat) + `.claude/skills` + `.devin/skills` (global-os, graphify only) remain.
