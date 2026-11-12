# aiZee — Comprehensive Review Prompt (reusable)

> **الاستخدام:** انسخ الملف ده كله كأول رسالة في جلسة مراجعة جديدة. البرومبت
> مصمم يشتغل مع أي agent (Devin / Claude / Codex). نتيجته: تقرير severity-
> gated + كل المشاكل الحقيقية اتصلحت والبوابات رجعت خضرا.
>
> **Usage:** Paste this entire file as the first message of a review session.
> The agent runs a full multi-persona audit, fixes real findings, re-verifies
> every gate, and reports — no issue left at "found but not fixed."

---

You are performing a **complete, exhaustive review of the aiZee codebase**
(repo root: the directory containing `aizee_cli.py`; on this machine
`E:\server\.ai`, deployment mirror `E:\server\aizee` — read-only, sync via
`scripts/update_aizee.py`).

## Persona directive

Start by adopting the required reviewer personas. If the platform supports
`aizee persona detect --multi "<task>"`, run it and load the returned
skills. Otherwise adopt ALL of these lenses for the whole review:
**SEC** (security-auditor), **QA** (qa-debugger), **ARCH**
(ai-agents-architect / ai-code-review-lord), **UX**, **LEGAL**, **SRE**.
Every finding gets a severity: **BLOCK** (must fix now), **WARN** (fix,
justify if deferred), **INFO** (note only).

## Phase 0 — Orient (read before judging)

1. Read `AGENTS.md`, `Memory.md`, `spec.md`, `CHANGELOG.md` head,
   `docs/BOOTLOADER.md`, `docs/CAPABILITIES.md` — know what the project
   *claims* before checking what it *does*.
2. `git status --short` and `git log --oneline -10` — current change
   surface; review changed lines first (diff-aware), then sweep the rest.

## Phase 1 — Health battery (run all, fix failures)

Run from the repo root; record each result:

```
aizee doctor                        # env, policy, dirs, deps, crypto, MCP, capability
python eval/harness.py              # ruff + mypy + pytest(cov) + scenarios + validate-globals
aizee test --full                   # full suite (xdist, all cores - 2)
aizee skill lock-check              # skills integrity (expect 0 changed/missing)
aizee check-docs                    # [[file#symbol]] doc→code links
python scripts/sync_docs.py         # canonical counts — rerun if it reports drift
aizee deps                          # dependency health
aizee security scan <repo>          # OWASP-2025 SAST — expect 0 blockers
aizee mcp freeze --check            # MCP surface integrity
graphify update .                   # knowledge graph refresh (after code edits)
```

Version consistency: `pyproject.toml`, `config.py`, `manifest.json`,
`plugin.json`, `server.json`, both READMEs, `CHANGELOG.md` top heading —
all must show the same version.

## Phase 2 — Security sweep (SEC / OWASP-2025)

Grep the core (`runtime/`, `dashboard/`, `aizee_cli.py`, `memory/`,
`aizee_mcp/`) — NOT vendored dirs (`skills/`, `refs/`, `_bmad/`):

- `eval(|exec(|pickle\.|os\.system|shell=True|__import__`
- `Access-Control-Allow-Origin.*\*` — wildcard CORS forbidden
- Secret literals: `sk-[A-Za-z0-9]{20,}`, `ghp_`, `AKIA[0-9A-Z]{16}`,
  `xox[bap]-`, `password\s*=\s*["'][^"']+`
- `except\s*:` bare, `except Exception:\s*pass` — empty swallows
- `yaml.load(` without `safe_load`; `f"SELECT`/`f'SELECT` dynamic SQL
- Path params → filesystem: any user-controlled string interpolated into
  a path must pass a containment check (`relative_to`, never
  `startswith`) and an id whitelist (`[A-Za-z0-9._-]` for filename parts)
- `subprocess.run` calls: list args, no shell strings from user input,
  timeouts set, `check=` deliberate
- URL/scheme handling, `webbrowser.open`, `requests.get(url)` — SSRF
- Auth surface: dashboard routes require token; `/api/health` public by
  design; POST requires `X-Requested-With`; CORS is origin-allowlisted
- Fail-closed: an error must deny, never `except: allow`

## Phase 3 — Correctness sweep (QA)

- `TODO|FIXME|XXX|HACK` without ticket tag in `runtime/`
- Every `read_text(`/`write_text(`/`open(` must pass `encoding="utf-8"`
  (Windows default cp1252 silently corrupts)
- `Path` joins vs string concat; `\\` literals in paths; `os.sep` misuse
- Dead code, duplicate logic, unreachable branches
- Crash surfaces: unguarded `dict[key]`, `int(str)`, `json.loads` without
  a typed catch; every `except` logs or re-raises — never silent
- `lstrip`/`rstrip`/`startswith` misuse on paths (dotfiles, sibling dirs)

## Phase 4 — Architecture review (ARCH)

- File sizes: flag new monoliths >700 lines (existing ones are known)
- Circular imports: `python -c "import runtime.<each new module>"`
- New key-value stores must go through `StorageFactory`
  (`runtime/storage_backend.py`) — never instantiate backends directly
- Errors must be `AizeeError` subclasses (`runtime/schemas.py`) — never
  bare `Exception` in new code
- `from __future__ import annotations` in every new Python file
- `config.discover_root()` — no hardcoded roots

## Phase 5 — UX & docs review

- `aizee --help`: every dispatched command appears; each new flag has a
  help string
- README command table vs actual argparse — flags, not positionals where
  the parser expects flags
- Error messages: actionable, name the fix, no raw tracebacks at CLI
- First-user journey: run the documented quick-start end-to-end in a
  clean state dir
- `check-docs` stays at 0 broken after any markdown edit

## Phase 6 — Legal review

- `LICENSE` MIT, `NOTICE` lists deps; new adopted concepts recorded in
  `tech-stack/useful-repos.md` + a `repo-study-*.md` report
- Clean-room discipline: GPL/AGPL sources = ideas only, never code;
  MIT/Apache = attribution in the study doc
- No vendored code without its license file

## Phase 7 — Platform review

- New code: `pathlib`, no `shell=True`, no backslash paths, no
  `os.startfile`/`icacls` outside a `platform.system()=="Windows"` guard
- `.bat`/`.cmd` files must be CRLF (`.gitattributes` enforces)
- POSIX wrappers exist for any Windows-only script
- `--root` honored by every command that touches state (never a hidden
  `discover_root()` bypass); drive-relative paths (`E:foo`) rejected

## Phase 8 — Source-control triage

- `git status --short`: classify every entry — work-product vs stray
- `git check-ignore` state/, dist/, temp/, graphify-out/, .env, brain/,
  .agents/, `audit_signing.key`, `_osroot.tar.gz` — all must be ignored
- Stray artifacts (scratch dirs, `server.ai/`, `.coverage.*` shards) —
  investigate origin, delete only after confirming disposable
- Stage only files the current session modified — never `git add .`
- No commit/tag/push without explicit user approval

## Phase 9 — Fix + verify loop (mandatory)

For every real finding: fix → add/adjust a regression test → FAST tier
(`pytest <file> --no-cov`, ~5s) → after all fixes, FULL battery again
(harness + check-docs + sync_docs) → `graphify update .` →
`python scripts/update_aizee.py` (mirror sync) → append a dated entry to
`Memory.md`. Never report a problem you could have fixed.

## Phase 10 — Report

Deliver: persona set used · per-gate table (pass/fail) · findings table
(severity, file:line, fix applied, regression test) · intentional/
vendor findings classified · remaining known issues · version state ·
mirror/sync state · temp size · a 3-line summary for the user.

## Known non-bugs — do NOT re-flag (verified)

- `runtime/deps.py:412` `shell=True` — trusted-manifest install runner,
  documented; repo-controlled content
- `aizee_cli.py` doctor wiring `except: pass` — optional-kernel probe
- `runtime/codemode/_child.py` `exec` — AST-scanned sandbox,
  `aizee-scan: ignore` marker — its purpose
- `icacls ... (R,W)` on `audit_signing.key` — tamper-resistant by design
  (owner can't delete without an `F` grant)
- Monoliths `aizee_cli.py` (~3200), `kernel.py` (~1300), `server.py`
  (~1300) — pre-existing; note, don't re-architect unprompted
- `installed version` in `doctor` ≠ source version — package artifact
- `ResourceWarning: unclosed sqlite` in pytest output — pre-existing
  suite noise
- Security-scan hits inside `skills/`, `refs/`, `_bmad/`, vendored
  assets — third-party content, not aiZee code
- `aizee impact` at the deployment mirror analyzes the *mirror's* git
  repo — correct; use `--root` for the source repo
- Embedded `$ref` inside a longer string stays literal by design —
  `$step.x` must be the whole arg value

## Out of scope (deferred — don't build unprompted)

Post-commit `graphify update` hook (slows commits) · monolith
refactoring · i18n of graph summaries · figma tooling.
