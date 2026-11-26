---
name: graphify
description: Query the graphify knowledge graph for architecture/dependency questions. Trigger /graphify.
---

[FILE] graphify skill
[OBJ] Knowledge graph exploration.
[TRIGGER] `/graphify`
[RULES]
1. [REQ] If `graphify-out/graph.json` exists, prefer graphify for architecture, dependency-path, and "where is X used" questions.
2. [CMD] `graphify query "<question>"` — get scoped subgraph.
3. [CMD] `graphify path "<A>" "<B>"` — dependency path.
4. [CMD] `graphify explain "<concept>"` — related concepts.
5. [PROHIBIT] Do NOT route every search through graphify — direct grep/read is fine for known files and small lookups.
6. [CMD] `graphify update .` after code edits.
