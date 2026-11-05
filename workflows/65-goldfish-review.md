# Workflow 65 — Goldfish Spec Review

> **Trigger:** `goldfish`, `review spec`, `fresh-context review`, `stress-test design`, `egm-review`
> **Engine:** `runtime/spec/review.py` — `aizee spec review <spec_id|--file doc.md> [--preset]`
> **Source:** Ported from `google/elephant-goldfish-model` (Apache-2.0, `resources/LICENSE-EGM`)

## Overview

An **Elephant** (the primary agent, full context) drafts a design document. **Goldfish** reviewers — subagents spawned in **fresh, zero-conversation context** — audit it against versioned rubrics. The human owns trade-offs and approval.

> **Invariant:** a review in the same context is NOT a Goldfish review. If the harness cannot spawn fresh subagents (`run_subagent`, `Agent`/Task, `invoke_subagent`, `spawn_agent`), STOP and say so.

## Files

- `resources/goldfish_personas/*.md` — 10 stateless reviewer personas (zoom_out, inventive_catalyst, comprehension, design_critic, structural, style, implementation_readiness, codebase_details, synthesizer, bootstrap_orchestrator)
- `resources/document_standards/*.md` — rubrics: `zoom-out-standard`, `feature-spec-standard`, `implementation-readiness-standard`, `heilmeier-standard`, `re-implementation-standard`
- `resources/execution_instructions.md` — mandatory gates: design-only scope, ONE question per turn, contradiction audit (no write-tools that turn), artifact-first, no summary blocks

## Protocol

1. **Plan** (deterministic): `aizee spec review <spec_id> [--preset interactive|uninterrupted|feature_spec|implementation]` or `aizee spec review --file <doc.md>`. Returns the semantic split (feature vs `## Detailed Implementation Plan` boundary), ordered stages with reviewer sets, line ranges, artifact names, and `max_reaudits: 1`.
2. **Execute stages in order.** For each stage, spawn one fresh subagent per reviewer; give it ONLY: its persona file, the target standard, the doc + its line range, and `GoldfishContext` files (all stages except 6 = comprehension reads the doc alone, no context). Write each report to the stage's artifact filename — never dump reports in chat.
3. **Checkpoint gates** (interactive preset only): after each stage ask exactly ONE question: proceed / update-doc-and-re-run / resolve-with-elephant / pause. Stages 7 & 9 add "resolve findings" — Elephant classifies each finding `PROPOSE FIX` vs `CONTEST` in `goldfish_review_report.md`, applies approved edits, then recalculates line bounds.
4. **Convergence cap:** max 1 re-audit per stage; afterwards residual findings become accepted trade-offs.
5. **Uninterrupted preset:** run all stages, then consolidate with `runtime.spec.review.consolidate_findings()` → `consolidated_review_report.md` (Traceability Matrix, Blocker/Major/Nit).

## Execution Constraints (all stages)

- Artifact-first: briefs, drafts, reports → files; chat gets paths only
- Critique first: weakest points before merits; no glazing, no validating adjectives, no apologies
- One question at a time; structured-question tools get `len(questions) == 1`
- Linked files inside the working dir join `GoldfishContext` automatically; external links/URLs need explicit approval (saved locally before review)

## aiZee Gates

- Stage artifacts land in the project working dir (or `.dev/docs/` if configured)
- Reviewers are read-only: no file writes, no fixes — findings only
- Budget: pass `aizee check` before spawning (each subagent turn is LLM spend)
