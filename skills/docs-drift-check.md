---
name: docs-drift-check
category: checklist
description: Source-grounded doc link verification. Use when editing or adding markdown docs, READMEs, or specs — validate wiki file#symbol refs so documentation never drifts from the code.
triggers:
  - documentation
  - docs
  - readme
  - spec drift
  - dead links
  - doc links
personas:
  - dev
  - writer
---
[SKILL] docs-drift-check
[OBJ] Documentation must stay source-grounded — every wiki-style code reference in markdown must resolve to a real file and symbol.
[RULES]
1. [REQ] After editing or adding markdown docs, run `aizee check-docs` — broken refs fail the gate.
2. [REQ] Reference code as `[[path/to/file.py#symbol]]` — links are root-anchored with doc-relative fallback; symbols are verified per language (py/ts/js/rs/go).
3. [REQ] Keep config snippets (TOML `[[table]]`) inside backticks or fenced blocks — inline code is skipped, bare brackets are treated as links.
4. [CMD] Use `@aizee: [[doc-section]]` comments in source for code→doc backlinks where the doc owns the contract.
5. [PROHIBIT] Do not write `[[file]]` refs to generated, scratch, or temp paths.
