---
name: "{name}"
description: "Recurring routine"
triggers: []
schedule: manual
# state: custom/relative/or/absolute/path.json   # optional — default derived from scope
---
# Routine: {name}

## [CONTEXT]
<!-- Standing facts the agent needs every run — profile, preferences, constraints.
     Curated, not collected: no credentials, no transcripts, no sensitive data.
     This is what saves the user from re-explaining themselves every session. -->

## [PROTOCOL]
<!-- Numbered steps the agent executes each run. Must end with ONE dated artifact
     (default: runs/YYYY-MM-DD.md next to this file). -->
1.
2.

## [RULES]
<!-- Hard prohibitions for this routine — things the agent must never do. -->
- Never send messages, apply, or purchase without explicit user approval.

## [STATE]
<!-- Human-readable mirror of state.json — the agent updates these lines after
     each run. The JSON state file is the machine source of truth. -->
- last_run: never
- next_actions: first run — collect missing context with the user.
