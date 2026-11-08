# Video Prompt Anatomy — Full Vocabulary

Source: consolidated from Google Veo 3.1 guide, Runway camera-terms reference, Replicate prompt-videos skill, Kling/Seedance/Hailuo official guides (Nov 2026).

## Shot types (framing)

| Term | Frame | Use for |
|---|---|---|
| Extreme wide / extreme long shot | Vast area, subject tiny | Landscape, isolation, scale |
| Wide / establishing shot | Full environment + subject | Openings, location-first storytelling |
| Full shot / long shot | Head to toe + some environment | Action, movement, fashion |
| Medium shot | Waist up | Dialogue workhorse, body language + expression |
| Medium close-up | Chest up | Conversation, reaction |
| Close-up | Face or key object fills frame | Emotion, dialogue, tension |
| Extreme close-up / macro | Single detail (eye, drop, texture) | Tension, microscopic detail |
| Two-shot | Two subjects in frame | Dialogue, confrontation |
| Over-the-shoulder (OTS) | Behind one subject, facing another | Conversations, perspective |
| POV / first-person | What the character sees | Immersion, subjective sequences |
| Top-down / bird's eye | Looking straight down | Food, products, choreography, geography |
| Worm's eye | Looking straight up from ground | Scale, confinement, dread |
| Dutch angle / canted | Tilted horizon | Unease, disorientation — use sparingly |

## Camera movements

| Term | What it does | Speed/duration required? | Best for |
|---|---|---|---|
| Static / locked-off | No camera movement | State "entirely motionless" explicitly | Tension, symmetry — hardest to hold; add "movement only from subject/scene elements" |
| Pan left/right | Rotates horizontally from fixed point | Yes | Following action, revealing landscape |
| Tilt up/down | Rotates vertically from fixed point | Yes | Revealing height, head-to-toe |
| Dolly in / push-in | Camera physically moves closer; background shifts | Yes | Tension, intimacy, reaction focus |
| Dolly out / pull-back | Camera retreats; environment expands | Yes | Reveals, endings, isolation |
| Truck left/right | Slides sideways parallel to subject | Yes | Walk-and-talks, matching pace |
| Pedestal up/down | Whole camera rises/drops vertically, level | Yes | Rising over obstacle to reveal |
| Zoom in/out | Lens magnifies; camera does NOT move | Yes | Emphasis — NOT the same as dolly |
| Crane shot | Mounted on crane, vertical/sweeping arcs | Yes | Dramatic reveals, scale |
| Aerial / drone shot | High-altitude flying movement | Yes | Establishing, sweeping geography |
| Handheld / shaky cam | Natural shake, imperfect framing | Describe texture ("subtle natural shake") | Documentary realism, urgency |
| Steadicam | Stabilized while walking | Yes | Following on foot without handheld rawness |
| Gimbal | Electronically stabilized, smoothest | Yes | Complex paths, walkthroughs |
| Whip pan | Very fast pan, motion-blur smear | Implied fast | Connecting subjects, energetic transitions |
| Orbit | Circles subject completely | Yes | Product shots, hero moments |
| Arc shot | Curved path around subject, no full circle | Yes | Motion for static subject |
| Crash zoom | Extremely fast zoom | Implied fast | Comedy beats, shock reveals |
| Dolly zoom / vertigo | Dolly + counter-zoom; background stretches | Yes | Disorientation, peak unease |
| Rack focus | Focus shifts between planes during shot | Describe speed ("slow rack focus") | Redirecting attention without moving camera |

### Multi-phase moves
Stacking verbs ("orbit and crane and push-in") fails. Instead describe what is in frame at each phase:
> "The camera arcs around the seated figure, then rises above the table to reveal the empty chairs surrounding her."

### Subject–camera relationship verbs
Always state how camera relates to subject motion:
- "camera follows the cyclist"
- "camera trucks left, matching the runner's speed"
- "camera leads the dancer, pulling back as she advances"
- "slow tilt up to reveal the skyline behind him"

### Truly static shots
Video models drift by default on locked-off shots. Fix with explicit language:
> "The camera is entirely motionless for the duration of the scene, with movement only occurring from the subject."

## Lens & focus

- Lenses: 14-24mm fisheye/super-wide · 24-35mm wide establishing · 35mm standard cinematic · 50mm natural · 85mm+ portrait/close-up · macro · telephoto (compression, isolation) · anamorphic (flares, oval bokeh)
- Depth of field: shallow (subject sharp, background blurred) · deep (all sharp) · bokeh · soft focus (hazy, memory/dream) · tilt-shift (miniature)
- Focus moves: rack focus (plane-to-plane shift) · pull focus · focus pull during move

## Composition

- Rule of thirds · centered/symmetrical · leading lines · frame within frame (doorway/window) · negative space · shallow foreground layering · headroom/nose room for faces

## Lighting & atmosphere

- Time of day: golden hour (warm, romantic) · blue hour (mysterious twilight) · midday hard sun · pre-dawn · deep night
- Setups: studio three-point · rembrandt (triangle on cheek) · film noir (deep shadows, hard key) · high-key (bright, even) · low-key (dark, shadow-dominant) · silhouette/backlight · neon-lit · practical lights (lamps, screens in-scene)
- Quality: soft/diffused vs hard/direct · volumetric rays/god rays · rim light · catchlights in eyes
- Atmospheric: rain · fog/mist · snow · dust motes in sunbeam · heat haze · haze/atmosphere · floating particles
- Color grade anchors: teal & orange · Kodak Portra (warm portrait film) · bleach bypass · desaturated/warm · IMAX vivid · VHS grain · 16mm/35mm film grain · "shot on 35mm film"

## Style anchors (max 2-3)

Named aesthetics the models parse: "cinematic", "documentary footage", "anime", "Pixar-style 3D", "claymation", "stop-motion", "80s synthwave", "film noir", "Wes Anderson symmetry", "Michael Mann neon night", "Roger Deakins naturalistic light", "Blade Runner 2049 orange/teal", "National Geographic documentary", "IMAX-scale", "hyper-realistic 8K" (quality anchors for fidelity).

## Temporal / pacing

- slow motion · 120fps · time-lapse · speed ramp · freeze frame · beat-synced cuts
- Evolution beats for short clips: "a flower bud slowly unfurling", "dawn breaking, sky gradually lightening"

## Audio layers (for audio-capable models)

Prompt ALL FOUR or the model guesses (and hallucinates — e.g., fake studio audience):

1. **Dialogue** — exact words or described intent. Format: `Character says: the line` (colon, not quotes, avoids subtitle rendering). Label speakers consistently in multi-character scenes ("the woman in pink says…", "the man with glasses replies…"). Length must fit clip duration (8s ≈ 2-3 short sentences).
2. **Ambient sound** — the place's soundscape: "rain on metal awnings", "distant city traffic", "forest birds", "the quiet hum of a starship bridge".
3. **Sound effects** — action sounds: "a door slamming", "glass breaking", "blade being drawn", "SFX: thunder cracks in the distance".
4. **Music** — genre/mood/instrumentation: "tense cinematic score", "soft jazz piano", "no music". Non-diegetic score vs diegetic (radio, busker) must be distinguished where the model supports it.

Pronunciation fix: spell tricky words phonetically ("foh-fur" not "fofr").

## Multi-shot / timecode structure

```
[0-4s]: Wide establishing shot, static camera, misty bamboo forest at dawn
[4-9s]: Medium shot, slow push-in, the fighter steps forward
[9-15s]: Close-up, orbit shot, the fighter strikes, slow motion
```

- Each block: shot type + camera + subject action + lighting/mood (+ SFX/dialogue where supported)
- Transition language between blocks: "hard cut to…", "seamless morph into…", "whip pan to…", "snap cut to…", "cut to…"
- Alternative parentheses format: `(0-3s) … (3-7s) …` — both parse on Seedance/Veo-class models
- Veo 3.1 timestamp format: `[00:00-00:02] …` with `SFX:` and `Emotion:` inline labels
- Kling 4.x structured format:
  ```
  [Asset Roles] @Image1 defines ___; preserve its ___.
  [Overall Settings] Scene: ___; visual style: ___; camera tone: ___.
  [Sequence of Events] 0–X s: ___ / X–Y s: ___ / Y s–end: ___
  [Audio] dialogue/voiceover + ambience + music + SFX
  ```

## Negative prompts — per model (critical differences)

| Model | Mechanism |
|---|---|
| Veo 3.1 / Gemini | Dedicated negative-prompt field + JSON controls. Describe what to exclude positively: "empty desert, no buildings" beats "no buildings". Avoid instructive "no/don't" phrasing. |
| Kling | No dedicated field — fold into main prompt with "avoid/without". Kling 4.x guidance: minimize negatives; only "no subtitles" and "no background music" are truly necessary exclusions. |
| Hailuo / MiniMax H3 | `BasicGuider` runs cfg=1, NO negative branch — ban lists add unwanted concepts. State what SHOULD appear instead. |
| Seedance 2.x | No true negative field — use positive description of the desired frame. |
| Sora 2 (legacy) | No negative prompt — state positives: "very focused and crisp", "avoid flicker", "no fast motion", "(no subtitles)". |
| Runway | No dedicated negative — fold exclusions into prompt naturally. |

Universal exclusions worth stating (in-model format permitting): blurry, low quality, distorted faces, warped hands, extra fingers, text artifacts, watermark, subtitles, logo, jitter, flicker, morphing, oversaturated.

## References & inputs (image/video/audio conditioning)

- **Image-to-video:** input image = first frame. Describe what CHANGES (action, camera), not the static scene already visible.
- **First + last frame:** model interpolates the transition (morphs, before/after, controlled arcs).
- **Subject/character refs:** reference images keep identity/product consistent across clips. Syntax varies: `[Image1]`, `@Image1`, "the character from image 1".
- **Video refs:** motion transfer — copy camera movement/gait from a clip.
- **Audio refs:** lip-sync to speech, cuts to beat. Match video duration ≈ audio length; transcribe dialogue into the prompt.
- **Multi-ref combo:** image (appearance) + video (motion) + audio (rhythm) + text (how they fit) = maximum control. Assign each ref a JOB: "Image 1 = mood/location, Image 2 = talent, Video 1 = camera move".

## Character consistency

- Repeat the character description VERBATIM across every prompt — word-for-word identical phrasing.
- Specify: age, hair, skin, build, exact garments/colors/materials, accessories, expression/demeanor.
- Vary scene/action/camera; never vary the character block.
- Keep ≤2 characters per generation for identity stability.
- Reference images beat text for facial consistency.

## Common failure modes → fixes

| Symptom | Cause | Fix |
|---|---|---|
| Subject glides instead of walks | Camera & subject motion unrelated | Add relationship verb ("matching her pace") |
| Weird impossible motion late in clip | Clip longer than the event | Shorten duration or tighten prompt; one action per clip |
| Fake laughter / studio audience audio | Audio not described | Write all 4 audio layers explicitly |
| Fast/truncated speech | Too much dialogue for duration | Cut lines; 8s ≈ 2-3 sentences max |
| Burned-in subtitles | Trained-on-subtitle bias | Colon syntax + "(no subtitles)" |
| Static shot drifts | Model defaults to motion | "Entirely motionless… movement only from subject" |
| Identity shifts across clips | Paraphrased character desc | Verbatim character sheet block |
| Morphing/warping | Too many simultaneous demands | One move per clip; split beats into separate generations |
| Generic "AI look" | Vague adjectives | Concrete nouns/verbs: "wet asphalt, neon signs in puddles" not "beautiful street" |
