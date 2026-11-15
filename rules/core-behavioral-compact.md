[FILE] core-behavioral-compact
[OBJ] Non-negotiable behavioral core principles.
[RULES]
1. [REQ] Think Before Coding `[BEH-01]`: State assumptions. If <80% clear, stop and ask.
2. [REQ] Simplicity First `[BEH-02]`: Write minimal required code. No speculative abstractions.
3. [REQ] Surgical Changes `[BEH-03]`: Touch ONLY requested lines. Match existing style. No drive-by refactoring.
4. [REQ] Goal-Driven Execution `[BEH-04]`: Define success criteria first as testable checks.
5. [REQ] Rules Re-Verification `[BEH-05]`: EVERY change must re-verify against ALL governing rules loaded in the session (bootloader, rules/*, task-contract, security). A violation found at any point → fix, then re-review the whole change until clean. Deliverables must work correctly for ANY user, not only the author's environment — verify as a cold user would (fresh clone, missing config, first run).
6. [REQ] Deterministic Repro `[DET-01]`: where determinism is required (renders, evals, replays, golden outputs) use seeded RNG + virtual/fixed clock and stable inputs; unseeded `random()`/wall-clock inside a deterministic path is a bug, not a flake.
