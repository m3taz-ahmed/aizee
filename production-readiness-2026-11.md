# Production Readiness — v6.9.0 (2026-11-12)

Scope: PyPI release readiness + per-platform adaptation review for the
creative-tools adoption pass (10 new capabilities).

## PyPI / packaging

| Check | Status | Notes |
|-------|--------|-------|
| Wheel contents | ✅ | `runtime*/memory*` package globs ship all new modules automatically |
| Entry points | ✅ | `aizee = aizee_cli:main` — new commands ride the existing CLI |
| Dependencies | ✅ | only `pyyaml` needed by new code (already declared); `types-pyyaml` in dev extras |
| Python floor | ✅ `>=3.10` | `types.UnionType`, `X | Y` unions used — both are 3.10+ |
| Version surfaces | ✅ | pyproject, config fallback, manifest ×2, plugin.json, server.json ×2, README badges ×2, validate-globals ×4 — all read 6.9.0 |
| osroot bundle | ⚠️ | rebuilt automatically by `release.py` (not run — no commit authorized) |
| Release command | — | `python scripts/release.py 6.9.0 "Creative-tools adoption pass" [--publish-pypi]` — does bump+validate+tag+push; **needs explicit approval** |
| PyPI `aizee` name | ✅ already claimed (6.8.x published) |

## Platform matrix

| Surface | Windows | Linux | macOS | Action taken / remaining |
|---------|---------|-------|-------|--------------------------|
| Source→mirror sync | `update_aizee.bat` (robocopy) | **was missing** → `scripts/update_aizee.py` + `update_aizee.sh` | same `.sh` | ✅ implemented (dry-run verified; found+fixed prune bug that would have deleted junction'd skills) |
| Installers | `install.bat`/`install.ps1` | `install.sh` | `install.sh` | ✅ already covered |
| Paths | `pathlib` everywhere incl. new code | same | same | ✅ |
| SQLite URIs | `file:{path}` worked | same | same | hardened → `_ro_uri()` (POSIX separators + quoting) |
| Env vars | `os.path.expandvars` handles `%X%`/`$X` | same | same | ✅ |
| Subprocess | command lists, no `shell=True` in new code | same | same | ✅ |
| Signals | `KeyboardInterrupt` paths kept | same | same | ✅ |
| Line endings | `.bat` CRLF; Python LF via git | same | same | warnings only, non-blocking |
| Farm concurrency | single-process locks (threads) | same | same | ⚠️ cross-process lease races possible — bounded by reaper; documented limitation, `fcntl`/`msvcrt` locks are a later upgrade |
| SSE/dash | `ThreadingHTTPServer` + 20-client cap | same | same | ✅ |

## What actually changed for each platform

1. **New portable mirror sync** — `scripts/update_aizee.py` (stdlib
   filecmp+shutil, robocopy `/MIR` equivalent) + `update_aizee.sh`
   wrapper. Same exclusion lists + deployment markers + self-mirror
   guard as the `.bat`. Dry-run verified: 43 copied, 0 removed.
2. **Snapshot URIs** — `memory/snapshot.py` `_ro_uri()` quotes paths so
   dirs with spaces/`%`/`#` work on every OS.
3. **No platform-specific code needed** in the ten new modules — all
   stdlib + `pathlib`.

## Remaining production actions (need approval)

- `scripts/release.py 6.9.0 "<title>"` — bump+gate+tag (does a commit).
- `--publish-pypi` — builds + uploads the wheel (network + credentials).
- MCP registry `server.json` publish for the new version.
- Deploy mirror already synced via the new portable script.

## Verification evidence (this session)

- `aizee plan ghost` — onion-skin render OK
- `aizee plan run --memo` ×2 — `cache_hits: 2` on re-run
- `aizee farm submit×2 → work → status` — 2 tasks done
- `aizee check` → `aizee events tail` — ActionEvent persisted
- `aizee replay` — 384 audit frames rendered as dope sheet
- `aizee memory snapshot` — 5077 rows, sha manifest + SHA256SUMS written
- `aizee ui --spec` — control pane JSON emitted
- `update_aizee.py` — mirror synced (43 files)
