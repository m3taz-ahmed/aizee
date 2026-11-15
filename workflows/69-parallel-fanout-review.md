---
name: parallel-fanout-review
trigger: parallel agents, fan out, subagent per task, multi-agent build, scene files, dispatch parallel, وكيل متوازي
persona: ARCH
engine: null
---

# Parallel Fan-Out + Per-Step Review

Dispatch protocol for splitting one build across isolated agents/workers. Adapted from `cth9191/animate` (one `src/era-NN.js` file per agent with boundary checks) and `obra/superpowers` (subagent-driven-development: fresh agent per task + review each). The rule: **each agent owns files, never shares them; every agent's output gets reviewed before the next depends on it.**

## When to use

- A plan decomposes into independent slices (scenes, modules, files, test batches, doc sections).
- Multi-step orchestration where steps are independent — use `aizee plan` fan-outs, not ad-hoc scripts.

## Protocol

### 1. Freeze the shared contract first

Before any fan-out: the shared artifacts are written, approved, and immutable — preamble/style, interfaces, base types, file layout, acceptance checks. Agents receive the contract, never renegotiate it. If the contract must change mid-flight, that is an `aizee task amend`, not an agent's initiative.

### 2. File-level ownership

- Each agent's declared `files:` scope is exclusive — two agents never write the same file (parallel writers share nothing, per open-edit's `row-*.json` lesson).
- Boundary files (bridges, headers, shared kits) are owned centrally, passed read-only.
- An agent needing a shared-file change reports back; the orchestrator applies it.

### 3. Dispatch with explicit seams

Each dispatch states: owned files, time/panel/section bounds, the shared contract, what "done" means (the per-task checks), and where evidence goes (which file/log). Fresh context per agent — no reliance on shared memory.

### 4. Per-step review gate

- After each agent returns: run its task's checks (its declared acceptance) BEFORE downstream consumers start. A bad seam found at agent N+1 costs N rework.
- Join points get explicit boundary checks (animate's era-file boundary validation; scroll-world's SSIM seam gate).
- Review is measured, not eyeballed — cite the check output `[TASK-11]`.

### 5. Bounded repair

A failing agent output gets bounded re-dispatch (`[LOOP-01]`, ≤5 rounds); on cap, stop and report the failing seam with its numbers.

## Checklist

- [ ] Shared contract frozen + approved before first dispatch.
- [ ] No file in two agents' scopes.
- [ ] Every agent output has checkable acceptance cited in review.
- [ ] Boundary/seam checks run at each join.
