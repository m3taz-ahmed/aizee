---
name: intake-glossary
trigger: intake, new project, unclear domain, ambiguous request, grill me, onboarding domain, shared language, ما فهمتش المجال
persona: ARCH
engine: null
---

# Intake → Shared-Language Glossary + ADRs

Alignment protocol before any non-trivial build. Adapted from `mattpocock/skills` (grill-me / grill-with-docs) and `cth9191/animate` intake.md — the fix for the #1 agent failure mode: building the wrong thing confidently. Produces two durable artifacts: a **glossary** (shared domain language) and **ADRs** (decisions with reasons).

## When to use

- The request touches a domain the agent hasn't modeled yet (new project, new business, new vocabulary).
- The user's words are ambiguous and two readings lead to different work.
- Any task where "the agent didn't do what I wanted" is a credible risk.

## Protocol

### Phase 1: Grill (align before build)

1. Ask the subject **openly, in plain prose** — never fabricate a multiple-choice industry/domain list; a made-up menu biases the answer and reads as you deciding for the user. Reserve option-questions for genuinely enumerable, low-stakes picks (art direction, format, tier) and always include "Other".
2. Ask only what you can't sensibly default. Infer everything you can from the repo, prior context, and the request itself first.
3. Prefer concrete over abstract: "what does the user do in the first 10 seconds" beats "describe your vision".
4. Play the understanding back for correction — a short restatement the user can confirm or fix, not a spec dump.

### Phase 2: Shared language (glossary)

1. Extract the domain's own vocabulary from the user's words — their terms, not textbook synonyms.
2. Write a glossary into `CONTEXT.md` (project root) or the spec's glossary section: `term → one-line meaning` in the project's voice.
3. Use the glossary terms in every artifact that follows — variable names, file names, docs, commits. A shared language is measured by use, not existence.
4. Concision test: if a concept takes >10 words to describe repeatedly, it earns a name.

### Phase 3: ADRs (decisions that are hard to re-derive)

1. Record each non-obvious decision as a one-paragraph ADR: context → choice → rejected alternatives → consequence. Store in `docs/adr/` or the spec's decisions section.
2. Only decisions someone would re-litigate later earn an ADR — obvious ones are noise.

### Phase 4: Spend estimate (when the path costs money/time)

Before expensive work (paid APIs, batch generations, long builds), state the estimate in plain numbers — what will run, what it costs, roughly how long — and get one explicit go-ahead. See `[MONEY-01]` in `rules/anti-patterns.md`.

## Artifacts

- `CONTEXT.md` or spec glossary — the shared language.
- `docs/adr/*.md` or spec decisions — the re-litigation-proof record.
- Story/design approval checkpoint — cheap gate before expensive work (see `68-preview-gates.md`).

## Checklist (done = measured)

- [ ] User confirmed the played-back understanding, not just answered questions.
- [ ] Glossary terms appear in the artifacts that followed.
- [ ] Every "?" in the spec resolved or explicitly deferred.
