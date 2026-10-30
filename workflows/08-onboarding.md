[WORKFLOW] 08-onboarding
[OBJ] Project Onboarding & AI Architect Initialization.
[TRIGGER] onboarding
[RULES]
1. [REQ] Fast Path: Read operating protocols from `.ai` root. Do not rely on assumptions. Act as Principal 10x Engineer.
2. [REQ] Context Loading Sequence:
   - Layer 0: `core-behavioral-compact.md`, `global-roles.md`
   - Layer 1: `anti-patterns.md`
   - Layer 2: On-demand (e.g. `security-standards.md`)
   - Layer 3: Task workflow + Detected Tech-Stack
3. [REQ] First Time Setup: Create `Memory.md`. Verify `.gitignore`. Run Tech-Stack Scan.
4. [REQ] Baseline Audit: Check architecture, security (`guarded=[]`), `composer audit`, test coverage, tech debt.
5. [REQ] Handoff Summary: Output Detected Stack, Rules Loaded, Red Flags, Recommended First Action.
[ADOPT]
When the project already exists and carries its own docs/artifacts (CCGS /adopt pattern) — migrate it into the aiZee flow instead of starting clean:
1. [REQ] Detect: inventory existing artifacts (docs, specs, tests, CI, changelogs, design docs) and map each to the aiZee equivalent (spec_engine spec/plan/tasks, workflows, rules, tech-stack, memory).
2. [REQ] Format audit: for each artifact, check whether its format is compatible or needs conversion (e.g., free-form GDD -> template sections; loose ADRs -> numbered adr-NNNN form).
3. [REQ] Classify: keep-as-is / convert / retire. Retired docs are archived, never deleted silently — the user confirms the retire list.
4. [REQ] Migration plan: ordered write list (paths + target format + owner section) presented for approval before a single file moves.
5. [REQ] Summary + write: execute the approved plan; write `.ai/active-context.md` with the migrated state and detected stack.
6. [REQ] First action: recommend the single next step (usually the first uncovered gap the migration surfaced) — never "onboarded, good luck".
