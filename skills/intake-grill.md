---
name: intake-grill
category: checklist
description: Requirements intake that produces a shared language — glossary + architecture decision records — before any implementation. Use at kickoff of ambiguous or cross-cutting work, before spec/plan.
triggers:
  - intake
  - grill
  - kickoff
  - requirements gathering
  - glossary
  - ADR
  - shared language
  - ambiguous requirements
personas:
  - pm
  - arch
invoke: user
---
[SKILL] intake-grill
[OBJ] Turn ambiguous requirements into a durable shared language (glossary + ADRs) so every downstream agent and review reads the same nouns. Ported from mattpocock/skills' grill-with-docs; protocol: `workflows/67-intake-glossary.md`.
[RULES]
1. [REQ] `[INTAKE-01]` Ask in batches, not drips — one grouped question set per round (max ~5), each question carrying the assumption it tests. Silence on a question = the assumption stands; record that.
2. [REQ] `[INTAKE-02]` Every answer lands in durable artifacts, not chat: `docs/intake/<project>/glossary.md` (canonical terms — name, meaning, non-meaning) and `docs/intake/<project>/adr-NNN-<slug>.md` (context → options → decision → consequences).
3. [REQ] `[INTAKE-03]` Glossary entries name concepts the implementation will reuse — entities, states, roles, limits. If two people could name the same thing differently, it needs a glossary row.
4. [REQ] `[INTAKE-04]` An ADR exists for every choice with a real alternative — never for foregone conclusions. One decision per file; superseded ADRs stay and link forward.
5. [REQ] `[INTAKE-05]` Downstream artifacts cite the language: spec REQs reference glossary terms by name, and contradictions between spec and glossary are a check failure, not a shrug.
6. [PROHIBIT] `[INTAKE-06]` Do not start implementation while a glossary term is contested or an ADR is unwritten — cheap words now beat expensive renames later.
7. [CMD] Close intake by summarizing: glossary rows added, ADRs filed, open questions remaining, and the REQ ids each downstream task must trace to.
