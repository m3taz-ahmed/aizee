[FILE] release-version-parity
[OBJ] Any version change or release must update every version-bearing surface and every install/update path — one command, no hand-edited literals.
[RULES]
1. [REQ] Single source of truth: `pyproject.toml` `version =`. `config.VERSION` derives from it. Never hardcode the version in code.
2. [REQ] ALWAYS release via `python scripts/release.py --version x.y.z --title "..."` — start with `--dry-run`. Never bump literals by hand.
3. [REQ] The canonical bump fan-out (`scripts/release.py::PLAIN_BUMP`): `pyproject.toml`, `manifest.json`, `plugin.json`, `server.json`, `config.py`, `scripts/validate-globals.py`, `scripts/validate-globals.ps1`; plus README badge/`Version`/`الإصدار` lines in `README.md` + `README-AR.md`, and a new `## [x.y.z]` CHANGELOG heading. Session work lives under `## [Unreleased]` until release moves it.
4. [REQ] If a NEW file acquires a version literal, add it to `PLAIN_BUMP` in the same commit. `validate-globals.py` is the safety net that catches missed bumps — it must stay green.
5. [REQ] README links/images must be absolute GitHub URLs — PyPI renders relative ones as 404. `release.py` blocks the release on any relative link (`REL_LINK_RE`).
6. [REQ] New dependency ⇒ update ALL of: `deps.yaml` (kind/severity/install, consumed by `scripts/update.py` for existing users), `pyproject.toml` `[project.dependencies]` or an `[project.optional-dependencies]` extra (new users / PyPI), and a README extras hint if user-facing. Never declare a package nothing imports.
7. [REQ] Optional extras must be documented in the install section of BOTH READMEs (EN + AR). `vector` = torch path; `vector-lite` = fastembed/ONNX torch-free path for 6 GB VRAM.
8. [REQ] Release gates run in order: `validate-globals` → `aizee test --full` (100% coverage floor, Windows-measurable) → `scripts/build_osroot_bundle.py` (wheel ships README+version) → commit/tag/push → `gh release create` → optional `--publish-pypi` (needs `UV_PUBLISH_TOKEN`).
9. [REQ] The deployed `aizee/` mirror is updated only by `update_aizee.bat` AFTER the release lands — never edit the mirror, never bundle an unbumped version.
10. [PROHIBIT] Tagging or publishing without the full test suite passing; `--skip-tests` exists only for local dry validation, never for a pushed release.
11. [PROHIBIT] Version literals in Memory.md or docs/studies/ reports — those are point-in-time artifacts and must not participate in bumps.
