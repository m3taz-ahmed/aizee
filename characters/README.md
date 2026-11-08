# Character Library

Canonical store for recurring AI-video characters. Global to aiZee — works across all projects.

## Convention

```
characters/
├── README.md             # this file
├── _template-char.md     # copy this to create a character
├── <name>-char.md        # THE SHEET — canonical description + metadata
└── <name>-char/          # ASSETS folder (same basename, no extension)
    ├── ref-front.png     # reference images → image-to-video / character refs
    ├── ref-full.png
    └── ref-voice.wav     # optional audio ref for lip-sync/voice models
```

- `*-char.md` files are the registry — glob `characters/*-char.md` lists every character.
- `*-char/` folders hold that character's reference assets.
- Names resolve via frontmatter `aliases:` (Arabic + English spellings).

## The one rule that matters

Every character sheet contains ONE block marked `VERBATIM:` — the canonical English description.
**Paste it word-for-word into every prompt, unchanged.** Verbatim repetition across generations is
what holds facial identity, wardrobe, and proportions consistent. Never paraphrase it per-clip.

Everything else in the sheet (voice, palette, notes) informs prompt choices but is not pasted.

## Consistency levels

VERBATIM is the baseline. For stronger locks, add the optional `## Consistency anchors` block
(see `_template-char.md`): locked seeds / character LoRA / turnaround refs for generative video,
or a `rig:` pointer for coded paths where the character is built once as data and reused
identically. Generative-video rule of thumb: verify the keyframe still BEFORE paying to animate,
and carry the previous segment's last frame forward as the next segment's top reference.

## Usage

- Mention a character by any alias in a video request → the agent loads the sheet automatically.
- "سارة", "sara", "Sara", "ساره" all resolve to `sara-char.md` if aliases are declared.
- To create: copy `_template-char.md` → `<name>-char.md`, fill it, optionally add a `<name>-char/` folder for refs.
- Sheet creation needs only 2-3 visual details from the user (build, palette, one signature trait) — the agent writes the canonical English block.
