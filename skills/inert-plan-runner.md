---
name: inert-plan-runner
category: tool
description: Inert JSON plan execution for multi-step tool orchestration. Use when coordinating several tool calls, fan-outs, approval-gated steps, or resumable runs — author a plan, never executable code.
triggers:
  - orchestrate
  - multi-step
  - plan
  - fan-out
  - fanout
  - batch tool calls
  - approval gate
  - resumable
personas:
  - dev
  - backend-api-expert
---
[SKILL] inert-plan-runner
[OBJ] Execute multi-step work as an inert, validated, resumable JSON plan — never as generated executable code.
[RULES]
1. [REQ] Prefer `aizee plan` over ad-hoc scripts when a task needs 3+ dependent tool calls, a fan-out over a collection, or an approval checkpoint.
2. [REQ] ALWAYS `aizee plan validate <file>` before `aizee plan run` — validation reports every issue at once (unknown tools, unbound vars, unbounded fan-outs) instead of failing mid-run.
3. [REQ] Every `fanout` MUST declare `max` — an unbounded fan-out is a validation error, not a runtime incident.
4. [REQ] Long or destructive runs MUST include a `{"op":"suspend"}` step as the approval gate; resume with `aizee plan resume <state.json> --plan-file <plan>` — settled tool calls never re-execute.
5. [REQ] Cite `plan_hash` in audit/approval artifacts — it content-addresses exactly what will run.
6. [CMD] Write plans to a temp file; mount only the tools the plan needs; keep expressions in the tiny DSL ($vars, paths, comparisons, len/int/str/float/sum/min/max/sorted/keys/values/abs/round, list+dict literals) — never attempt eval/exec.
7. [PROHIBIT] Never hand-edit generated code into a plan — a plan is data; if you need real code execution use `aizee codemode` instead.
