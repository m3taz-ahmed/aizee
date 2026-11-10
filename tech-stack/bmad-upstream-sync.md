# BMAD-METHOD Upstream Sync Runbook

How to update the vendored BMAD layer inside `.ai` — **no global install
required or desired**.

## Layout

| Path | Role | Tracked? |
|---|---|---|
| `skills/bmad-*`, `skills/bmod-*` | BMAD skills (vendored upstream content + aiZee frontmatter) | yes |
| `_bmad/` | BMAD runtime contract — `config.toml`, `scripts/*` (`resolve_config.py`, `roster.py`, `setup.py`, `tickets.py`…) | no (gitignored) |
| `_bmad-output/` | Ticket tree output (initiative/epic/story artifacts) | no (gitignored) |

`_bmad/` must keep its exact name — every BMAD skill references
`{project-root}/_bmad/scripts/*` literally. Do not rename or relocate it.

## Update procedure

1. **Fetch upstream** into a temp dir (never overwrite in place):

   ```powershell
   git clone --depth 1 https://github.com/bmad-code-org/BMAD-METHOD temp\bmad-upstream
   ```

   (or `npx skills add bmad-code-org/BMAD-METHOD --skill <name> -y` into a
   scratch dir for single-skill updates)

2. **Diff** upstream skill dirs against `skills/bmad-*` / `skills/bmod-*`.
   Vendored copies carry extra frontmatter (`personas:`, `triggers:`) —
   preserve those blocks; take upstream body/reference/script changes.

3. **Copy changed files** into `skills/` — keep aiZee frontmatter intact.

4. **Refresh `_bmad/scripts`** if upstream changed them: re-run the setup
   script or copy the script files directly (they are plain Python, no
   install step):

   ```powershell
   uv run --no-cache temp\bmad-upstream\skills\bmad\scripts\setup.py `
     --project-root . --skill temp\bmad-upstream\skills\bmad --status
   ```

5. **Re-apply trigger enrichment** if skills were re-vendored:

   ```powershell
   python scripts/enrich-bmad-triggers.py
   ```

6. **Re-lock + verify:**

   ```powershell
   python aizee_cli.py skill lock-update
   python aizee_cli.py skill lock-check
   python aizee_cli.py skill lint
   python scripts/validate-globals.py
   ```

7. **Sync the mirror:** `scripts/update_aizee.bat`.

## Fresh-project onboarding

For any project that should use BMAD: check `<root>/_bmad/` exists → if
not, run `setup.py --status` then setup (creates config + modules). Add
`_bmad/` + `_bmad-output/` to that project's `.gitignore`.
