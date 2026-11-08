# Per-Model Prompt Formats & Specs

Verified against official docs Nov 2026. Specs change fast — if a generation behaves oddly, re-check the provider's current docs before assuming the skill is wrong.

## Quick spec table

| Model | Aspect ratios | Resolution | Duration | Audio | Negatives |
|---|---|---|---|---|---|
| Google Veo 3.1 | 16:9, 9:16 | 720p/1080p (4K on Standard) | 4/6/8s (+7s extensions to ~37s) | Native, incl. dialogue | Dedicated field / JSON |
| OpenAI Sora 2 Pro ⚠️ API shut down 2026-09-24 | 1280×720, 720×1280 (+1920×1080, 1080×1920 Pro) | 720p/1080p | ≤20s | Native | None — positives only |
| Kling 3.0/4.0 | 16:9, 9:16, 1:1 (+21:9 on 4.0); i2v follows image | 720p/1080p/4K | 3-30s (4.0), 3-15s (3.0) | Native on newer tiers | Fold "avoid/without" into prompt |
| Runway Gen-4.5 | 1280:720, 720:1280 (API); more ratios i2v | 720p native; 4K via separate upscale API | ~5-10s per gen | Gen-4.5 has audio on some tiers | None dedicated |
| ByteDance Seedance 2.0/2.5 | 21:9→9:16 set + adaptive; follows start image | 480p-4K (2.0), ≤1080p 10-bit (2.5) | 4-15s (2.0), 4-30s (2.5) | Native, unified AV | None — positive description |
| MiniMax Hailuo H3 | adaptive, 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 | 768p or 2K, 24fps, dims ×32 (native 1344×768) | 4-15s | Native, 3-field structure | NONE — cfg=1, no negative branch |
| Alibaba Wan 3.0 / 2.7 | 16:9, 9:16, 1:1, 4:3, 3:4; i2v follows image | ≤1080p | 2-30s (3.0), 2-15s (2.7) | Optional audio (3.0); 2.2 open weights = silent | Model-dependent |
| Luma Ray 3.2 | 9:16, 3:4, 1:1, 4:3, 16:9, 21:9 | varies | varies | varies | varies |
| Grok Imagine Video | 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3 | varies | varies | varies | varies |
| xAI/Grok, Pika, LTX | check current docs | | | | |

Aspect-ratio gap: NO major model outputs native 4:5 (Meta feed-ads favorite). Workaround: generate 3:4 or 9:16 and crop.

## Google Veo 3.1 (Vertex AI / Gemini API / Flow)

Formula: `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]`

Template:
```
[shot type + composition], [subject], [action], [setting/context with time of day],
[camera movement with direction], [lens + depth of field], [lighting quality + color],
[mood/atmosphere], [style anchors]. Audio: [dialogue/SFX/ambience/music].
```

Example:
```
Medium shot, a tired corporate worker rubbing his temples in exhaustion in front of
a bulky 1980s computer in a cluttered office late at night. Harsh fluorescent overhead
lights and the green glow of a monochrome monitor. Retro aesthetic, shot as if on
1980s color film, slightly grainy. Audio: the hum of a CRT monitor, a distant phone
ringing twice, no music.
```

- Multi-shot: `[00:00-00:02] … [00:02-00:04] …` timestamp blocks; inline `SFX:` and `Emotion:` labels.
- Features: first+last frame interpolation, ingredients-to-video (≤3 reference images), add/remove object, extension (+7s each).
- JSON mode available for programmatic control — each key = one direction.
- Dialogue: quotation marks OK on Veo (`A woman says, "We have to leave now."`) — differs from Sora/Kling colon convention; when unsure, colon works everywhere.
- Negative: dedicated field; phrase exclusions as desired-absence ("empty landscape, bare ground").

## Kling (kling.ai / Kuaishou)

Formula: `Subject + Subject Description + Subject Movement + Scene + (Camera Language + Lighting + Atmosphere)`

- Describe subject with multiple short sentences: appearance, hairstyle, clothing, posture.
- Movement must suit ~5s: straightforward, visible actions.
- Camera: named moves (push-in, pan, tilt, tracking, orbit) + speed. Kling also has UI camera controls (horizontal, vertical, zoom, pan, tilt, roll + 4 Master Shots) — do NOT double-direct: if using UI controls, keep prompt camera language minimal.
- Multi-shot: "Multi-Shot" mode names shots in order; or timecode blocks.
- Audio: native on current tiers; keep dialogue short.
- Negatives: Kling 4.x says minimize; only exclude "subtitles" and "background music" when unwanted. Avoid over-constraining.
- Elements/character refs: build a character from 2-4 images or a video; reuse verbatim description otherwise.
- Duration trap: don't give 10s to a 5s event — model fills extra time with invented motion.

## Runway Gen-4.5

Camera formula: `[Shot size] + [Angle] + [Movement + direction + speed] + [Subject & action] + [Lens/look] + [Lighting/mood] + [What the shot reveals]`

- Strongest at precise camera language; one motivated move per shot is the reliable pattern.
- Static shots need explicit lock: "The camera is entirely motionless for the duration of the scene, with movement only occurring from the subject."
- Multi-beat sequences: generate each beat as its own clip, cut in Runway Multi-Shot app — keeps cut points under your control.
- Gen-4.5 accepts combined camera terms but phased description beats stacked verbs.
- API: `ratio` is required (1280:720 or 720:1280 t2v; more options i2v). No resolution field — 4K requires separate `POST /v1/video_upscale` (magnific_video_upscaler_creative).
- Image refs: character/object reference inputs supported.

## ByteDance Seedance 2.0 / 2.5

- Heaviest reference model: up to 9 images + 3 videos + 3 audio files + text. Assign each input a job with `[Image1]`/`[Video1]`/`[Audio1]` syntax.
- Audio is unified with video (same architecture) — describe sound design in detail; dialogue one-shots well.
- Timecode prompting is a signature strength: `[0-4s]: … [4-8s]: …` dense blocks parse reliably, "doesn't hallucinate even with this density".
- Overdescribe: pack concrete detail; quality anchors "hyper-realistic, 8k" + style/cinematographer tags push fidelity.
- Escalation pattern wide→medium→close-up→ECU maps to ~15s.
- Does NOT accept reference images/videos containing real human faces (2.0) — use stylized/illustrated refs or generated characters.
- 2.5 adds: 30s, 50 references, storyboard input (≤15 panels).

## MiniMax Hailuo / H3 (hailuoai.video / fal.ai / ComfyUI)

Three-field prompt structure:
```
integrated_multimodal_description: [Shot 1] … timed shots, camera, action, dialogue
overall_soundscape: ambient + physical SFX + non-verbal (1-4 sentences; N/A only if truly silent)
non_diegetic_music: score only, audience-only (1-3 sentences; N/A if none)
```

- Camera moves as bracket commands after description: `[Push in]`, `[Pan left]`, `[Static shot]`, `[Zoom in]`, `[Truck right]`, `[Tilt up]`, `[Pedestal down]`, `[Arc shot]`, `[Tracking shot]`, `[POV]`, `[Roll]` — append amplitude ("with small amplitude") and speed ("at fast speed").
- Dialogue: `<d>[English] line</d>` verbatim; speaker IDs `(S1)`, `(S2)` assigned in order of first speech; describe voice at first mention.
- Resolution: native 1344×768 @16:9; all dims multiples of 32; `length` = frames @24fps (124 ≈ 5s), snapped to 17k+5.
- NO negative prompts (cfg=1, no negative branch) — state what should appear.
- R2V retention markers for reference mode: `fully_copy`, `partially_copy`, `reference`, `weak_reference`.
- On-screen text: English double quotes per string, verbatim, original language.

## OpenAI Sora 2 (⚠️ API deprecated Sept 24, 2026 — app may still exist; verify before relying)

- Prompt = cinematography brief, not contract. Same prompt → different results (feature, not bug).
- Shorter clips follow instructions better; start short even though 16s/20s exist.
- API params (model, size, seconds, character IDs) are NOT prompt-controlled — duration lives in `seconds` param.
- Structure: short labeled lines — prose scene → `Cinematography:` (shot+angle, mood) → `Actions:` beats → `Dialogue:` block → `Audio:` line.
- One main subject + one main action; beats as counts/steps ("takes four steps, pauses, turns").
- Beats format: `0-2s`, `2-4s`, `4-6s`; 4s clip = 1-2 beats max.
- Character continuity: ≤2 characters, reuse descriptors verbatim, mention uploaded character name verbatim.
- Image input locks composition/first frame — prompt describes what happens NEXT.
- Invariants for edits/extensions: "same shot", "keep background", "continue forward in time".
- Text: quote exact strings, specify placement, avoid motion blur.

## Alibaba Wan (3.0 / 2.7 / 2.2 open)

- 2.2 open-weights = no audio; 3.0 adds optional audio + omni reference.
- Aspect: 16:9, 9:16, 1:1, 4:3, 3:4 (2.7); i2v follows image shape.
- Lip-sync capable (Wan 2.5 lineage) — give dialogue + describe delivery ("commanding tone, emphasis on X").
- Structure follows the universal formula; timestamp blocks work.
- Good budget option (~half the cost of premium models on aggregators).

## Universal fallback template (any model)

```
[shot type], [angle], [subject + action + setting], [camera move + speed +
relationship to subject], [lens + DoF], [lighting + atmosphere], [style anchors],
[audio layers if supported]. Duration: [N]s. Aspect: [ratio] — set in params.
```
