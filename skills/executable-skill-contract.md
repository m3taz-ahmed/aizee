---
description: Contract for executable scripts bundled inside skills — flags, exit codes, determinism, honesty
---

# Executable Skill Contract

Any script shipped inside a skill (`scripts/`, `bin/`, detectors, analyzers)
MUST satisfy this contract before the skill is considered installable.
Derived from unslop-anything's `detect.js` design — the best reference
implementation of a zero-dependency executable skill script.

## Required behaviors

1. `--json` — machine-readable output on stdout. Pretty printing is for
   humans only when `--json` is absent.
2. `--version` — prints the script version and exits 0.
3. `--self-test` — runs embedded fixtures (at least one clean + one bad
   sample) and exits non-zero if the script misclassifies them.
4. Exit codes: `0` clean/success, `1` findings/runtime failure,
   `2` usage error. Document deviations in the script header.
5. No network access by default. If a network mode exists it is opt-in via
   an explicit flag and documented.
6. Deterministic output: same input → same findings in the same order.
   Sort results; never iterate hash-maps/filesystem order directly.
7. Zero required dependencies beyond the language runtime unless the
   SKILL.md declares them in its frontmatter.

## Honesty requirements

- State what the script CANNOT detect (static analysis limits, no runtime
  insight, no product comprehension) in both `--help` and the SKILL.md.
- Findings are evidence, not truth: output must frame hits as leads
  requiring in-context verification, never as verdicts.
- Cap output size; truncate with an explicit `truncated: true` marker.

## Distribution requirements

- Pinned versions and checksums for anything the installer downloads.
- NEVER `curl | sh`. Package-manager or vendored copies only.
- The skill's `SKILL.md` must list every script, its flags, and its exit
  codes in a references file or the main body.
