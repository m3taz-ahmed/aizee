---
name: writing-skills
category: checklist
description: Behavior-shaping authoring rules for SKILL.md files. Use when creating or editing any skill — skills are behavior code, not prose, and text changes are gated by eval evidence.
triggers:
  - write a skill
  - edit a skill
  - new skill
  - skill authoring
  - SKILL.md
  - skill wording
personas:
  - dev
  - arch
invoke: auto
---
[SKILL] writing-skills
[OBJ] Author skills as behavior-shaping programs: every line must change agent behavior measurably, and every edit ships with eval evidence. Ported from obra/superpowers' writing-skills + usethisskill's proven-badge discipline.
[RULES]
1. [REQ] `[SKILL-01]` A skill is behavior code, not documentation. Write instructions to the agent ("do X when Y"), not explanations for a reader ("X is..."). Cut any line that would not change what the agent does.
2. [REQ] `[SKILL-02]` Eval-gated edits: any change to skill wording needs before/after behavioral evidence — run `aizee eval` on the affected scenario set and record pass-rate deltas in the change record. No "obviously better phrasing" merges.
3. [REQ] `[SKILL-03]` The `description:` field is a retrieval surface, not a summary — it decides whether the skill loads at all. Write it for matching ("Use when...") and keep `triggers:` concrete nouns/verbs a user or task would actually contain.
4. [REQ] `[SKILL-04]` One skill, one job. If a skill needs "and also" in its [OBJ], split it. Lazy-load depth: put rare details in a sibling reference file and point at it, like animate's SKILL.md controller + grammar/* docs.
5. [REQ] `[SKILL-05]` Declare `invoke:` honestly — `user` for skills a person calls explicitly (intake, audits), `auto` for trigger-fired behavior rules. See `runtime/rule_frontmatter.py:_as_invoke`.
6. [REQ] `[SKILL-06]` Rules carry strength tags: `[REQ]` mandatory, `[PROHIBIT]` hard stop, `[CMD]` command. A skill without a `[PROHIBIT]` has no teeth — include the failure mode it prevents.
7. [PROHIBIT] `[SKILL-07]` Never state a rule you cannot check or the agent cannot follow. "Be careful with X" is noise; "verify X with Y before Z" is a rule.
8. [CMD] After authoring: `aizee skill lint` (description+collision check), `aizee skill lock-update` + `lock-check`, `aizee memory ingest`, and index via `aizee skill index --write` when distributing cross-harness.
