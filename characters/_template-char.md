---
name: <character-name-lowercase>
aliases: [<arabic-name>, <English-Name>, <common-misspellings>]
voice: <age, pitch, pace, accent — or "N/A">
style: <photorealistic cinematic | anime | 3D animated | claymation | etc.>
created: <YYYY-MM-DD>
---

# <Character Name>

## Canonical description

```
VERBATIM: <ONE paragraph, English. Age, build, hair, skin, exact garments + colors +
materials, accessories, expression/demeanor. This exact text is pasted unchanged into
every prompt — write it once, well.>
```

## Voice / delivery

- <How they speak: pace, tone, accent, speech patterns. "N/A" if silent roles only.>

## Palette & signature details

- Palette: <2-4 colors that identify them>
- Signature: <one detail that makes them recognizable at a glance>

## Usage notes

- <Shot types that work best / worst for this character>
- <Lighting or style pairings that suit them>
- Ref images: `<name>-char/` (add files there as they are produced)

## Consistency anchors (optional — add per production need)

Consistency levels, weakest → strongest. VERBATIM above is always required; add anchors only when the user wants higher fidelity:

- `seed:` <locked generation seed(s) per model> — generative path only
- `lora:` <path to character LoRA> — trained identity, strongest generative lock
- `turnaround:` <paths to angle-matched refs: front/side/back/expressions> — for image-conditioned video models
- `rig:` <path to code-drawn rig/assets or profile file> — coded paths (cinecode/bang-motion/motion-*): the character IS data, identical by construction
- `voice-ref:` <path to ref-voice.wav> — lip-sync/voice models
