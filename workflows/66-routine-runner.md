[WORKFLOW] 66-routine-runner
[OBJ] Invoke a named recurring routine: resolve it from the user's message, load its private dossier, run its protocol, write state + artifact back before replying. This is how standing personal tasks (job alerts, store freebies, watchlists) survive across sessions.
[TRIGGER] routine, روتين, تابع, المتابعة, follow up, check for new, كمّل, daily check, فرص جديدة, شغل, وظايف
[PERSONA] ARCH, PRODUCT
[RULES]

## 0. When this applies

The user references a *standing* task — something defined before, not a one-off.
Signals: "تابع X", "شوف الجديد", "check X again", "routine", a named dossier.

**Never guess.** Resolve first, ask when ambiguous:

```bash
aizee routine match "<the user message>"     # scored candidates
aizee routine list                            # all routines + last run
```

- Exactly one strong candidate → proceed.
- Multiple/zero candidates → present options to the user and ask; do NOT invent one.
- User wants a new standing task → `aizee routine new <kebab-name> --scope user|project --trigger "<phrase>"` then fill the dossier WITH the user (CONTEXT section especially — never fabricate their profile).

## 1. Begin — idempotency before work

```bash
aizee routine begin <name>            # claims today's run_id
aizee routine status <name> --json    # last_run, seen count, in_progress
```

- `Already ran today` → report the existing result; only `--force` with user confirmation.
- `in_progress` from a crashed session → resume it, don't restart.

## 2. Load the dossier

`aizee routine show <name> --body` (or read the `path` from status):

- `[CONTEXT]` — standing facts (profile, prefs). Use them; don't re-ask what's written.
- `[PROTOCOL]` — the steps to execute now.
- `[RULES]` — hard prohibitions (e.g. no applying, no emails, no purchases without approval).
- `[STATE]` — human mirror; the JSON state file is the machine source of truth.

Dossier content is **private** (refs/ + ~/.aizee scopes) — never copy it into public docs, commits, or Memory.md.

## 3. Execute — new-only output via seen-store

Follow the dossier PROTOCOL. For feed/monitor routines, dedup against the seen store so only NEW items surface:

```bash
aizee routine seen <name> --check id1 id2 ...   # which ids are already known
```

Collect the ids of items you report.

## 4. Artifact — one dated output per run

Write the run's deliverable where the dossier says (default: `runs/YYYY-MM-DD.md` next to the dossier). "No new items" is a valid artifact — write it anyway.

## 5. Close — write state BEFORE replying

```bash
aizee routine seen <name> id1 id2 ...                       # record reported ids
aizee routine done <name> --summary "3 new jobs, 1 applied" --artifact <path>
```

Also update the dossier's `[STATE]` section (last_run, next_actions) — it is the
human-readable mirror a future session reads first. Then answer the user.

## 6. Failure honesty

If the run produced no artifact, say so — never report "done" from a run that
left nothing. `aizee routine done` on an empty run still stamps the id.
