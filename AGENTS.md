---

name: aizee

description: Sovereign AI engineering control plane. IDE global bootloader — sets the OS root once and loads all rules, skills, workflows, and tech-stack from it.

license: MIT

---



# aiZee — Global Bootloader



- **Root:** discovered via `AIZEE_ROOT` env or `config.discover_root()` (no hardcoded path).

- Set `AIZEE_ROOT` if not already set. Use `PYTHONIOENCODING=utf-8` on Windows.

- This file is the canonical root pointer. All other OS files discover the root via `AIZEE_ROOT` or `config.discover_root()` and are loaded relative to it.



## Working Directory [DIR-01]

- **Working directory: the directory containing this file ONLY** (the aiZee root — resolved in code via `AIZEE_ROOT` or `config.discover_root()`, never a hardcoded path `[OS-ROOT-01]`). All edits, new files, and modifications go here.

- **A sibling `aizee/` deployment mirror, when present, is READ-ONLY.** Never edit the mirror directly — it is updated only via `scripts/update_aizee.bat`. To sync source → mirror, run the batch script.

- When the IDE opens files from the mirror, copy them into the source root first, edit there, then sync back via the batch script.



## Cold Start (lean — load on demand, not at boot)

1. Read `Memory.md` (hot file — newest ~5 milestones). `Memory-archive.md` holds older history — read it only when the task needs it.

2. Pick the persona semantically from the **Persona Menu** below — no CLI call needed. Load ONLY the primary persona's `skills/<skill>.md` (or `skills/<skill>/SKILL.md`). Read a lord file ONLY when the active sub-task genuinely enters that lord's domain; the same for secondary personas — adopt the lens, load their skill file on demand.

   **Persona switch directive (mandatory):** If the user message STARTS with a persona command — `#انتحل`, `/انتحل`, `#reset`, `/reset`, `#persona`, `/persona`, `#redetect`, `#switch` (or Arabic `#شخصيات`, `/شخصيات`, `#بدّل`, `/بدّل`, `#حالة`, `/حالة`, `#مين`, `/مين`, `#معلومات`, `/معلومات`) — strip the token, choose from the Persona Menu semantically, announce `persona → <CODE> — <one-line reason>`, load the primary skill file, and act. For status commands (`#حالة`, `/status`, `#مين`, `/معلومات`) print the currently active persona set instead of acting. The adopted set persists for the session until a switch command or a clearly different domain; never silently ignore these commands.

   **Ambiguity escalation:** when 2+ personas are genuinely tied, either pick the closest and note it, or ask the user once — do NOT run a detection pipeline. `aizee persona detect --multi` remains available for explicit verification (`#redetect --cli`) and audits only; its keyword ranking is a fallback, never the default path.

3. If the current project has `spec.md`, read it before any action.

4. `global-roles.md`, `global-workflow.md`, `manifest.json`, `rules/*.md`, `ACTIVE_CONTEXT.md` — load ONLY when the task calls for them (role governance, workflow routing, vocabulary, prior project state). They are NOT boot-time reads.

## Persona Menu

30 personas. Pick by domain hints; the skill file lists its own lords by name — load them on demand only. Regenerate this table from `aizee persona catalog` after persona registry changes.

| Code | Primary skill | Domain hints | Lords |
|------|---------------|--------------|-------|
| ARCH | ai-agents-architect | architecture, scalability, scalable, system design, microservices | 17 |
| QA | qa-debugger | test, tests, testing, coverage, pytest | 8 |
| UX | frontend-ui-expert | ui, ux, design, user journey, user experience | 9 |
| DEV | backend-api-expert | backend, api, server, database, crud | 12 |
| SRE | sre | cloud, aws, gcp, azure, kubernetes | 9 |
| SEC | security-auditor | security, secure, vulnerability, zero trust, zerotrust | 12 |
| GAME | game-architect | game, game loop, gameplay, render, rendering | 6 |
| PLAY | google-play-warlord | google play, play console, play store, android publish, publish app | 0 |
| MOBILE | mobile-game-producer | mobile game, mobile app, fastlane, anti cheat, anticheat | 4 |
| DATA | data-engineer | data, database, sql, etl, analytics | 3 |
| ML | ml-engineer | machine learning, ml, model, training, inference | 9 |
| DEVOPS | devops-engineer | devops, cicd, ci/cd, pipeline, jenkins | 9 |
| API | api-architect | api, rest, graphql, microservices, integration | 5 |
| LEGAL | legal-compliance | gdpr, compliance, privacy, legal, data protection | 1 |
| PRODUCT | product-manager | requirements, user story, roadmap, product, user research | 0 |
| DOC | technical-writer | documentation, readme, api docs, changelog, technical writing | 2 |
| PERF | performance-engineer | performance, profiling, latency, benchmark, optimization | 4 |
| CV | cv-writer | cv, resume, curriculum vitae, السيرة الذاتية, سيرة ذاتية | 2 |
| FREELANCE | freelance-platforms | freelance, freelancer, upwork, fiverr, freelancer.com | 5 |
| DEVX | context-compressor | developer experience, dx, cli, tooling, devtools | 5 |
| MLOPS | ml-engineer | mlops, model deployment, model registry, feature store, model serving | 8 |
| FINOPS | finops | finops, cloud cost, cost optimization, billing, budget | 3 |
| MARKETING | marketing-strategy | marketing, digital marketing, التسويق, تسويق إلكتروني, تسويق رقمي | 3 |
| GROWTH | growth-loops | growth hacking, viral, فيروسي, referral, إحالة | 2 |
| BRAND | brand-kit | brand, براند, هوية, identity, positioning | 2 |
| EMAIL | email-marketing | email, newsletter, نشرة بريدية, drip, رسائل تلقائية | 1 |
| SOCIAL | social-media-marketing | social media, تواصل اجتماعي, تويتر, x platform, instagram | 2 |
| CRO | cro-optimization | cro, conversion, تحويل, a/b test, تجربة أ ب | 2 |
| SALES | b2b-cold-outreach | lead gen, cold email, رسالة باردة, outreach, اكتساب عملاء | 2 |
| AUTO | automotive-diagnostics-engineer | obd, obd2, obd-ii, can bus, canbus | 7 |




## Runtime Gate

- Route CONSEQUENTIAL actions through `runtime/kernel.py`: destructive ops, external side effects (push, publish, payments, messages), paid/budget actions, and multi-step orchestration plans.

- Use `aizee check <action> --args '{"tokens":N}'` or `Kernel.act` to validate policy + budget — one check per ACTION BATCH (a group of related calls), not per individual call.

- Routine local reads, searches, and in-session file edits run UNGATED — do not spawn a CLI call per operation.

- No destructive action without explicit user approval.

- Gate order: `Probity → Guardian → Policy → LoopDetector → Budget → Audit` (LoopDetector blocks repeated tool loops; Audit is hash-chained).



## Command Surface & Auto-Triggers `[TRIG-01]`

Every built-in capability below is installed and verified. Prefer the matching command over ad-hoc scripts — these are the supported paths.

| Command | Use when |
|---------|----------|
| `aizee plan validate\|run\|resume <file>` | Multi-step tool orchestration, fan-outs, approval gates — author inert JSON plans, never executable code (see `skills/inert-plan-runner.md`) |
| `aizee skill lock-check` / `lock-update` | After installing/updating skills, and before trusting the skill library (see `skills/skill-lock-integrity.md`) |
| `aizee mcp freeze <srv> [--check]` | After MCP config changes and before trusting an MCP server (see `skills/mcp-surface-integrity.md`) |
| `aizee check-docs` | After editing markdown docs — validates `[[file#symbol]]` refs (see `skills/docs-drift-check.md`) |
| `aizee models [--catalog] [--query]` | Choosing a model, checking cost/context/reasoning — offline catalog, no network needed |
| `aizee spec review <spec\|--file>` | Spec/plan review before implementation (EGM goldfish pipeline) |
| `aizee intel <domain>` | Domain intelligence: DNS/WHOIS/certs/subdomains/IP |
| `aizee eval` | Behavioral skill-scenario checks after changing skills/workflows |
| `aizee skill link --pack <dir>` | Packaging skills for other agent harnesses (claude/codex/cursor/opencode) |
| `aizee skill index [--out <file>]` | Regenerating `skill-index.json` — sha256-locked discovery index for harnesses |
| `aizee budget quote\|approve\|charge\|report` | Paid-action spend governance — quote → single-use approve → charge → report (MONEY-01) |
| `aizee spec derive-checklist <id>` | Deriving a verification checklist from spec requirement rows |
| `aizee find <q>` / `aizee goal <obj>` | Discovering the right skill/workflow for a task |
| `aizee routine <list\|match\|begin\|seen\|done>` | Recurring personal routines: named dossiers + durable cross-session state (see `workflows/66-routine-runner.md`) |

**Event-triggered rules (fire without being asked):**

- When a task's domain matches none of the loaded persona skills → run `aizee find <task description>` before implementing; 354 skills + 84 workflows are indexed (name + triggers + description) even when not persona-mapped.
- When the user references a standing/recurring task ("تابع X", "check X again", "follow up", a named routine) → run `aizee routine match "<message>"` before asking for context; ambiguous → present candidates, never guess.
- After adding/installing a skill → run `aizee skill lock-update`, then `aizee skill lock-check`.
- After changing an MCP server config → run `aizee mcp freeze <server> --check`.
- After editing `*.md` docs → run `aizee check-docs`.
- Orchestrating 3+ dependent tool calls or an approval checkpoint → use `aizee plan`, not a script.
- Before trusting generated orchestration → `aizee plan validate` first, cite `plan_hash` for approvals.

## Context & Memory

- Detect stack from `package.json` / `composer.json` and load matching `tech-stack/<pkg>-<ver>.md` only after reading the lockfile for the exact version (`[VER-01]`).

- If `graphify-out/graph.json` exists, prefer `graphify query` / `query_graph` (MCP) for architecture, dependency-path, and "where is X used" questions. Direct grep/read is fine for known targets and small lookups — graphify is not a gate on every search.

- Query Context7 MCP for external libraries/frameworks before implementation; use `aizee_mcp/aizee_server.py` for global context.

- Run `aizee memory ingest` when `rules/`, `tech-stack/`, or `workflows/` change; update `Memory.md` via `workflows/17-memory-sync.md` after every milestone (keep it hot — archive overflow to `Memory-archive.md`).



## Quality Gate

Before declaring done, run from the OS root:

- `ruff check .`

- `mypy` (strict, 233 files — run with the CI target list from `.github/workflows/validate.yml`; bare `mypy` has no default target)

- `aizee test --full` (full suite with coverage, parallel by default — ~180s, ~8,000 tests, 100% cov)

- `python eval/harness.py` (read-only: ruff + mypy + pytest + validate-globals)

For quick iteration: run ONLY targeted tests (`pytest path/to/test_file.py -q`) ~5s max. Full fast tier (`aizee test` — all non-slow, no cov) is ~60-120s on Linux / ~180s on Windows.

No `eval` in policy code.



## Project Testing Protocol (ANY project under aiZee)

Every project — Laravel, React, Python, Go, Node — follows two-tier testing `[TEST-07]`:

- **FAST tier** (during iteration): run ONLY targeted tests for the code you touched. ~5s max. See `workflows/testing-tiers.md` for per-stack commands.

- **FULL tier** (before declaring done): run the project's complete test suite + coverage. Must pass green.

- **FULL tier maxes machine resources** `[TEST-11]` — every project, old or new: use the stack's parallel runner at `cpu_count - 2` workers (leave the OS breathing room, never 100%). pytest-xdist, `vitest --maxWorkers`, `artisan test --parallel`, `go test -parallel`. GPU only if the suite runs real GPU-bound code (verify `nvidia-smi` util; mocked-model suites get zero gain — measured 151s CUDA vs 127s CPU on aiZee). Per-stack commands: `workflows/testing-tiers.md`.

- Never run the full suite on every change. Never skip the full suite before done.

- If the project has no test framework, write the first test for the touched code before declaring done `[TEST-09]`.



## Non-negotiable user policy

- No full test suites during iteration — use FAST tier (targeted `--filter=...` / `<file>` only).

- FULL test suite is mandatory before declaring done — no exceptions.

- No `git add .` / `git add -A` (`[GIT-06]`). No `git commit`, `git push`, destructive git, or unauthorized server actions without explicit user approval.

- Delete temporary/scratch/test files immediately after use.



## Shell Compatibility `[SHELL-01]`

- Detect the active shell before running commands. On Windows the default shell is **PowerShell** — never use bash syntax (`&&`, `||`, `2>nul`, `ls`, `cat`, `grep`).

- PowerShell equivalents: `;` instead of `&&`, `if ($?) { ... }` instead of `||`, `Test-Path` instead of `ls ... 2>nul`, `Get-ChildItem` instead of `ls`, `Get-Content` instead of `cat`, `Select-String` instead of `grep`.

- In workflow CMD steps, use `pwsh:` or `ps:` prefix for PowerShell commands on Windows; `bash:` for POSIX shells on Linux/macOS.

- When using `subprocess` in Python, pass command lists (not shell strings) to stay cross-platform. Use `shell=True` only when absolutely necessary and never with user input.



---



## Architecture



aiZee follows a layered design:



- **CLI / Entry Point** — `aizee_cli.py` parses commands, delegates to kernel.

- **Kernel (Facade)** — `runtime/kernel.py` routes to managers.

- **Managers** — `runtime/managers/` (PolicyManager, WorkflowManager, AgentManager, ChatManager).

- **Runtime Modules** — 162 governance modules in `runtime/`.

- **MCP Server** — `aizee_mcp/` exposes 53 tools via FastMCP (marketing tool modules gated via `disabledToolModules`).

- **Memory** — `memory/` SQLite + FTS5 + vector store.

- **Skills / Workflows / Tech-Stack** — declarative `.md` files loaded at runtime.



### Core Infrastructure



| Module | Purpose |

|--------|---------|

| `runtime/kernel.py` | Facade delegating to managers |

| `runtime/policy.py` | Policy evaluation engine |

| `runtime/budget.py` | Token/cost/call budget tracking |

| `runtime/audit.py` | Append-only audit log |

| `runtime/guardian.py` | Pre-action guardian gate |

| `runtime/probity.py` | Integrity verification |

| `runtime/persona.py` | Auto persona detection |

| `runtime/spec_engine.py` | Spec-driven development (4 phases) |

| `runtime/storage_backend.py` | Pluggable storage abstraction (memory/json/sqlite) |

| `runtime/service_catalog.py` | Multi-index skill/workflow catalog |

| `runtime/schemas.py` | Pydantic schemas + AizeeException hierarchy + PaginatedResult |



### Package Layout



```

aizee/                         # Sovereign root (AIZEE_ROOT)
├── aizee_cli.py               # CLI entry point
├── config.py                  # Root discovery + version
├── runtime/                   # Kernel + 162 governance modules
│   ├── kernel.py              # Facade
│   ├── managers/              # Policy/Workflow/Agent/Chat managers
│   ├── storage_backend.py     # StorageBackend protocol + factory
│   ├── service_catalog.py     # ServiceDescriptor + multi-index catalog
│   ├── schemas.py             # Pydantic + exceptions + pagination
│   └── ...                    # 162 governance modules
├── aizee_mcp/                 # MCP server (53 tools enabled)
├── memory/                    # SQLite + FTS5 + vector
├── skills/                    # 361 persona + lord skills
├── workflows/                 # 70 trigger-based execution protocols
├── rules/                     # Compressed behavioral rules
├── tech-stack/                # 285 version-locked stack references
│   └── spec-driven-templates/ # SDD templates (spec/plan/tasks/constitution/checklist)
└── eval/                      # Agent benchmark harness

```



## First Principles



When making changes, follow these priorities:



1. Preserve policy-governed behavior (never bypass kernel gates)

2. Match existing aiZee patterns (read neighboring code first)

3. Reuse existing modules (don't reinvent storage/catalog/exceptions)

4. Prefer correctness over convenience

5. Keep changes narrow and testable



## Adding a New Runtime Module



1. Create `runtime/<module>.py`

2. Add to `runtime/__init__.py` if it needs exports

3. Wire through `kernel.py` or the relevant manager

4. Add tests in `tests/test_<module>.py`

5. Update `Memory.md` if user-facing

6. Run quality gates: `ruff check .` + `mypy` + `pytest tests/test_<module>.py`



## Adding a New Skill



1. Create `skills/<name>/SKILL.md` (or `skills/<name>.md` for flat)

2. Add frontmatter with triggers, personas, tech_stack

3. Register in `PERSONA_SKILLS` mapping in `runtime/persona.py` if persona-linked

4. Test with `aizee persona detect --multi "<task description>"`

5. Run `aizee memory ingest` to refresh indexes



## Adding a New Workflow



1. Create `workflows/<NN>-<name>.md` (sequential numbering)

2. Add trigger keywords in the header

3. If it uses a runtime engine, document the engine module

4. Update `workflows/README.md` count



## Error Handling



- Raise `AizeeError` subclasses from `runtime/schemas.py`

- Use `PolicyDeniedError` for policy gate failures

- Use `BudgetExceededError` for budget limit hits

- Use `ValidationError` for input validation

- Use `StorageError` for storage backend failures

- All exceptions carry `error_code`, `severity`, and `context` dict

- Never use bare `Exception` — always an `AizeeError` subclass



## Storage Rules



- Use `StorageFactory` from `runtime/storage_backend.py` for new key-value stores

- Do not instantiate `InMemoryStorage` / `JsonFileStorage` / `SqliteStorage` directly

- Existing `MemoryStore` (SQLite) is unchanged — new code opts into the abstraction

- Backends are cached by path — repeat `create()` returns the same instance

- Call `factory.shutdown_all()` on process exit to flush + close



## Common Mistakes



- Bypassing `StorageFactory` and instantiating storage directly

- Using bare `Exception` instead of `AizeeException` subclasses

- Hardcoding paths instead of using `config.discover_root()`

- Assuming framework versions without reading lockfiles (`[VER-01]`)

- Running full test suite during iteration (use FAST tier)

- `git add .` / `git add -A` (`[GIT-06]`)

- Forgetting to update `Memory.md` after milestones

- Writing implementation code without Context7 MCP query first



## Human Handoff



If behavior is unclear:



1. Prefer aiZee spec (`spec.md`) and existing code behavior

2. Then `Memory.md` for recent context, `Memory-archive.md` for history

3. Then `global-roles.md` / `global-workflow.md` for governance rules

4. If a task requires broad architectural changes, stop and surface tradeoffs



## Code Style



- Use `from __future__ import annotations` in all Python files

- Strict typing — no `Any` without justification, no `mixed`/`unknown` abuse

- Class <300 lines, method <30 lines (`[CODE-03]`)

- Enums/constants over magic strings (`[CODE-04]`)

- SOLID & DRY (`[CODE-05]`)

- Constructor injection (pass dependencies in `__init__`)

- Self-explanatory code over comments

- Always use braces in conditionals (for JS/TS projects)

- Never leave a `catch`/`except` block empty — log with context

- Follow existing project patterns



## Logging



- Use structured logging (dict-based, not f-strings in hot paths)

- Avoid noisy logs in performance-critical paths

- Log error context: error_code, severity, operation, user (if relevant)



## Pull Request Guidelines



- Keep changes focused — avoid unrelated refactors

- Preserve behavior unless the task explicitly requires change

- Update docs (`Memory.md`, `CHANGELOG.md`) when user-facing

- Conventional commits: `feat:`, `fix:`, `perf:`, `docs:`, `chore:`, `refactor:`

- Stage only files YOU modified (`git add <file>`, never `git add .`)

- No `git commit` / `git push` without explicit user approval

## Worker-Agent Contract

Adopted from cua's AGENTS.md — durable work lives in GitHub, not in local queues.

- The issue/RFC carries the problem; the pull request carries the execution.
  A reviewer must not need local scheduler/worktree state to understand the work.
- When the account has write access, push the work branch to the canonical repo —
  not a personal fork.
- Keep progress in the linked PR description, not periodic status comments.
- Route suspected vulnerabilities through SECURITY.md privately — never a public
  issue, log, or screenshot.
- `aizee work poll` lists open issues via the gh CLI; unassigned + `help wanted`
  rank first (pull model).
- Releases are per-version tags (`vX.Y.Z`) with GitHub release notes — there are
  no component release streams.
