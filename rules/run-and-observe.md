[FILE] run-and-observe
[OBJ] Evidence standard for visual/interactive changes — "a parse check is not a run". Adapted from Claude-Code-Game-Studios (MIT).
[RULES]
1. [REQ] Any change the user can SEE or FEEL (UI, scenes, animations, gameplay feel, visual output) is not done until the artifact was launched, observed, and the observation retained (screenshot/recording + a one-line OBSERVED note). Lint, typecheck, and green tests prove syntax and logic — they do not prove the thing renders, reads, or feels right.
2. [REQ] Report one of three verdicts, verbatim-style: `OBSERVED — <what was on screen>` (with retained evidence), `NOT VERIFIED — <reason>` (engine/device/env unavailable — a blocker, never an inference that code is fine because it reads correctly), or `N/A — <reason>` (nothing observable, justified).
3. [REQ] Waivers are explicit and level-named: a waived check says `waived at <level>`; a waived observation and a forgotten observation must never produce the same artifact trail.
4. [REQ] Evidence lives where the project keeps QA artifacts (e.g., `production/qa/evidence/<story>/` on game pipelines); the evidence path is recorded in the closing note.
5. [PROHIBIT] Closing visual/UI/feel work on code review alone; asserting a screenshot exists without looking at it; substituting "it compiles" for "it runs"; inferring correctness from reading the diff.
