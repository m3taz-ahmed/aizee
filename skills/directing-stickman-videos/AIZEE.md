# aiZee vendoring note — directing-stickman-videos

Vendored 2026-11-18 from `kaomei/stickman-video-director` (MIT, see `LICENSE-UPSTREAM`).

## What was imported

Everything except heavy media: `SKILL.md`, `references/` (76 contract docs),
`scripts/` (57 helpers), `examples/`, `tests/`, `agents/openai.yaml`, `package.json`,
plus inside `assets/`: all JSON manifests/catalogs, licenses/CREDITS, executable
art-kit code (`*.py`, `*.cjs`, `*.mjs`), fonts (`*.ttf`), `*.svg`, `*.html`, `*.md`.

## What was excluded (~485 MB upstream)

- `assets/**/*.mp4|gif|webm` — approved baseline evidence + public showcases
- `assets/b-audio-library/**/*.{ogg,wav,mp3,m4a}` — bundled licensed music/SFX
- `assets/**/*.png|jpg` — sprite sheets, art kits, contact sheets

## Effect on the contract

- **A · Model Engine**: fully functional — storyboards, prompts, style contracts are all text.
- **B · Autopilot**: render pipeline (`scripts/`) + fonts + executable kits present.
  Missing: bundled audio library and baseline-reference MP4s. The skill's own rules
  cover this: "genuine tool limits permit disclosed best effort, never an equivalence
  claim" — disclose missing media, use `references/music-sourcing-and-license.md` for
  external sourcing, do not claim sample-equivalence.

## Re-vendoring media on demand

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/kaomei/stickman-video-director /tmp/svd
cd /tmp/svd && git sparse-checkout set skills/directing-stickman-videos/assets
```

Then copy needed subtrees into this skill dir. Keep binary media out of git history —
update `skills-lock.json` afterwards (`aizee skill lock-update`).
