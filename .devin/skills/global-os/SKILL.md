[FILE] global-os skill
[OBJ] Bootstrap aiZee context — lean, on demand.
[RULES]
1. [REQ] Read `AGENTS.md` canonical — it is already auto-injected by the harness; read from disk only if it was truncated.
2. [REQ] Read `Memory.md` (hot file). `Memory-archive.md` only when history is needed.
3. [REQ] Pick persona semantically from the Persona Menu in `AGENTS.md`; load only the primary skill file. Lords + secondary skills load on demand.
4. [REQ] `manifest.json` — read ONLY when routing to a workflow.
5. [REQ] `global-roles.md` / `global-workflow.md` / `rules/*.md` — read ONLY when the task needs role governance, workflow routing, or specific vocabulary.
6. [REQ] Apply version gate `[VER-01]` before loading `tech-stack/*.md`.
7. [REQ] Use Context7 MCP for external libs; graphify for architecture/dependency questions (see graphify skill).
