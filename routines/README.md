# `routines/` — Recurring Routine Dossiers

A **routine** is a named, invocable standing task: a private markdown dossier
(standing context + protocol + rules) plus a JSON state file that survives
across sessions. Solves the "I explained everything yesterday — do I have to
paste it all again?" problem: the agent resolves the routine from your message,
reads where it left off, runs, and writes back.

Only the template and examples ship in this directory. Real (private)
dossiers live in the two gitignored/home scopes below.

## Scopes (name-resolution priority)

| Scope | Directory | Use for |
|---|---|---|
| `project` | `refs/routines/` (gitignored) | private routines tied to this OS/machine |
| `user` | `~/.aizee/routines/` | private routines that follow you everywhere |
| `shipped` | `routines/` (this dir) | templates + shareable examples only |

## Lifecycle

```bash
aizee routine new <kebab-name> --scope user --trigger "وظايف" --trigger "jobs"
aizee routine match "<user message>"   # agent-side: resolve from free text
aizee routine begin <name>             # claim today's run_id (idempotent)
aizee routine seen <name> --check id1  # dedup store — report only NEW items
aizee routine seen <name> id1 id2      # record reported ids
aizee routine done <name> --summary "..." --artifact runs/2026-11-13.md
```

Agent protocol: `workflows/66-routine-runner.md`. Schema: `aizee.routine-state.v1`
(runs capped at 50, seen-ids capped at 5000, atomic writes).

## Dossier sections

`[CONTEXT]` standing facts · `[PROTOCOL]` steps per run · `[RULES]` prohibitions ·
`[STATE]` human mirror of the JSON state.

Frontmatter: `name` (kebab-case), `triggers` (AR+EN phrases — matched by
substring, so Arabic works), `schedule` (advisory: `manual`/`daily`/`weekly`),
optional `state` path override.
