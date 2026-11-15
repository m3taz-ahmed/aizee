---
name: preview-gates
trigger: expensive work, batch generation, paid api, long build, preview first, draft first, بوابة قبل الصرف, approval checkpoint
persona: ARCH
engine: null
---

# Preview Gates — Cheap→Expensive HITL Ordering

Ordering protocol for work whose cost is concentrated at the end (batch generations, long renders, paid API calls, multi-file migrations). Adapted from `cth9191/animate` (story→look→storyboard gates) and `scroll-world` (anchor-still→batch, previz-tier→full-model). The rule: **gate cheap representations of the expensive thing before paying for the expensive thing** — each gate exists to keep the big spend from being wasted, not to re-ask permission.

## When to use

- Any run where the final step dominates cost: video/image generation batches, paid model calls, large refactors, long test/export renders.
- Multi-agent fan-outs where a wrong shared artifact would be built N times (`plan` fan-out with a shared spec/preamble).

## Protocol

### 1. Decompose the cost curve

Identify the artifact that is cheap to produce but predicts the expensive outcome — that artifact is the gate:

| Expensive thing | Cheap predictor (the gate) |
|---|---|
| N generated assets | ONE anchor asset in final style, approved, then reused as the style reference for the batch |
| Full render/final model | Draft-tier render (lower res/cheap model) that preserves every property being validated |
| Multi-file refactor | The transformed skeleton of the hardest file + the migration contract |
| Long pipeline run | Idempotent pipeline's dry-run listing what WOULD be produced |

### 2. Sequence the gates cheap→expensive

- Order approvals so the cheapest disconfirming evidence arrives first.
- One spend approval at intake (state the full estimate in plain numbers — `[MONEY-01]`); subsequent gates verify *fit*, they do not re-ask permission.
- Hard gates: an unapproved anchor/preview blocks the batch — proceeding is a contract violation, not a judgment call.

### 3. Make the gate the thing itself where possible

The strongest preview is the real artifact at small scale — an approved storyboard panel that IS the final renderer's output at t≈0, a draft render from the same pipeline — never a separate mock that can drift. If the preview and the deliverable share no code/render path, the preview can lie.

### 4. Idempotent production

Write the batch so re-running skips finished work (output-hash/existence check) — a crash or a single failed item re-rolls only that item and never repays completed work.

## Checklist

- [ ] Gate artifact shares the final pipeline's code path (no mock drift).
- [ ] Spend estimate stated once, in numbers, before the first paid step.
- [ ] Re-roll granularity = single failed item, never the batch.
- [ ] Gate order documented in the run log (what was approved when).
