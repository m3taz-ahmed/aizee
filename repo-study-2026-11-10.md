# Repo Study — Agentic Video + Dev/PM Tooling Wave (2026-11-10)

**Scope:** full-internet + GitHub sweep for (A) video/image creation — coded, algorithmic, motion-graphics, generative, agent-driven — and (B) tools that make a "programmer beyond description + complete project manager". 80+ repos cloned to `temp/repo-study-2026-11-10/`; ComfyUI + 12 nodes installed to `~/.aizee/media/apps/`; ~8 uv tools + repomix + ComfyUI venv installed on this machine.

**Hardware constraint that shapes every recommendation:** RTX 4050 Laptop, **6 GB VRAM**, Windows. Everything below is filtered through "works on 6 GB or is free/cloud".

---

## 0. The headline finding

The 2026 frontier moved from "AI video models" to **agentic video production systems**: repos that turn the coding agent itself into a video studio — pipelines as YAML manifests, stage-director skills, tool registries, decision logs, approval gates. OpenMontage (79k★, AGPL), nexu-io/open-design (107k★, Apache-2.0), diffusionstudio suite, heygen/hyperframes (81k★, already installed), kinetograph (Rust GPU compositor). aiZee's `skills/video-produce` already routes to kits; this wave gives it a much deeper pattern library + new engines to route to.

For **local generation on 6 GB**, the answer is not one model — it's **Wan2GP** ("GPU poor" one-stop app: Wan2.x, LTX-2.x, HunyuanVideo-1.5, MiniMax H3, LongCat, Flux, Qwen-Image, TTS, 3D) + **ComfyUI** (installed) with GGUF/low-VRAM nodes + **FramePack** (13B on laptop GPUs). HunyuanVideo-1.5 and Wan2.2-TI2V-5B are the realistic model picks; MiniMax H3 works in WanGP at 480p (license excludes US/EU/UK/KR — Egypt is fine).

---

## 1. AGENTIC VIDEO SYSTEMS (study-first tier)

| Repo | ★ | License | What it is | Adopt |
|---|---|---|---|---|
| `OpenMontageInc/OpenMontage` | 79k | AGPL-3.0 | Full agentic video studio: 13 pipeline YAMLs (`animated-explainer`, `documentary-montage`, `character-animation`, `localization-dub`, `avatar-spokesperson`…), stage-director skills, tool registry w/ provider contracts + capability envelope, decision_log append-only, backlot live board, 93 agent skills (hyperframes family, manim best-practices, gsap-*, threejs-*, provider skills for Veo/Kling/Seedance/LTX-2/H3/Gemini-Omni/Pika/Atlas/DashScope/HeyGen/ElevenLabs/Google). Real-footage path: corpus retrieval from Archive.org/NASA/Wikimedia/Pexels → CLIP search → edit → render. **AGPL — patterns only, no vendoring.** | Pipeline manifest + stage-director + decision-log + capability-envelope patterns for `video-produce` v2; skill contents readable as reference |
| `nexu-io/open-design` | 107k | Apache-2.0 | Collaborative AI design-agent workspace (motion/prototypes/sites/apps/dashboards/presentations/images/videos) | Ecosystem hub; sibling tools below are the focused extracts |
| `nexu-io/html-anything` | 9.5k | Apache-2.0 | Agentic HTML editor: 75 skill templates × 9 surfaces (magazine, decks, résumé, poster, XHS cards, tweet cards, prototypes, data reports, **HyperFrames videos**); auto-detects 9 agent CLIs; 1-click export | Skill-pack format + surface taxonomy worth mirroring |
| `nexu-io/motion-anything` | 1k | Apache-2.0 | Chat-native motion engine: 403 motion recipes, 230 portable skills, 4 triggers/13 verbs/spring easing/keyframe editor; exports JSON·CSS·React·Lottie·MP4·GIF; zero deps | **Motion recipe library = gold for motion-graphics kit** |
| `nexu-io/html-video` | 4.8k | Apache-2.0 | Programmatic HTML→video on laptop, pluggable render engines, 21 templates, AI soundtrack | Third HTML→video path alongside hyperframes/kinetograph |
| `nexu-io/codex-slides` | 975 | MIT | Slide studio in agent: prompt→deck→PPTX/PDF, 45 templates/73 styles, MCP server (38 tools) | Deck pipeline pattern for PM/docs work |
| `nexu-io/nexu` | 3.3k | — | Desktop client bridging CLI agents to IM (WeChat/Feishu/Slack/Discord) | Remote-control pattern for long renders |
| `nexu-io/harness-engineering-guide` | 696 | — | Open guide to agent runtimes | Reading |
| `diffusionstudio/editor` | 3.5k | — | "VS Code of video editing, built for agents" — **Windows binary available** | GUI fallback + MCP target |
| `diffusionstudio/core` | 1.2k | — | Browser video engine on WebCodecs (`@diffusionstudio/core` npm) | In-browser preview/compositing |
| `diffusionstudio/agent` | 300 | — | Python video composer agent (embeddings-driven) | Agent-side editing logic |
| `diffusionstudio/lottie` | 5.7k | — | Text-to-Lottie generator driven by agent skills | Lottie output path for character/logo animation |
| `diffusionstudio/skills` | 148 | — | `diffusion:editor` + `diffusion:watch` agent skills (needs desktop app + MCP) | Install via `npx skills add diffusionstudio/skills` — same channel as aiZee skill publishing |
| `0xS4N4TG/kinetograph` | 485 | — | **Rust GPU compositor, no browser**: Remotion-API TS in → MP4 out; also renders HyperFrames projects as-is; WebGL/shaders/3D/WebAudio. Beta 0.3. | Fastest deterministic render path candidate — watch maturity |
| `hypit-ai/hypit` | 28k | — | "Clone any viral video with agents" — face/words/B-roll swap, 100 variants/cmd | Reference-derivative pipeline (matches video-produce reference flow) |
| `waooAI/waoowaoo` | 14.8k | — | "Industry-first" controllable film platform: script→storyboard→assets→video, agent+canvas | Full-stack reference impl (Chinese-first) |
| `HBAI-Ltd/Toonflow-app` | 21k | — | AI short-drama/motion-comic tool: script, storyboard, character/scene asset mgmt, infinite canvas, MCP+plugins, self-host | Character/scene asset pipeline reference |
| `IgorShadurin/app.yumcut.com` | 912 | — | Next.js local-first short-video factory: script→voice→visuals→captions→9:16 edit, batch+API hooks | Lean reference for MPT-style pipeline |
| `LingyiChen-AI/AIComicBuilder` | 1.9k | — | Script→animated comic→video w/ character design + storyboarding | Comic pipeline niche |

## 2. CODED VIDEO ENGINES (the "video by code/math" layer)

| Repo | ★ | License | Role |
|---|---|---|---|
| `remotion-dev/remotion` | 72k | Company license (free for individuals/small cos) | **The** React→MP4 engine: scenes, spring animations, `@remotion/captions`, lambda/cloud render. aiZee already references it via kits |
| `midrender/revideo` | 4.2k | MIT | TS scene graph → headless render API + React player; agent-writable scenes |
| `motion-canvas/motion-canvas` | 19.7k | MIT | Generator-based TS animation (the engine behind 3B1B-style videos); Revideo fork adds video-editing semantics |
| `Vanilagy/mediabunny` | 7.5k | MIT | Pure-TS media toolkit — "FFmpeg for the web": mux/demux/convert MP4/WebM/MP3/HLS in browser or Node |
| `ffmpegwasm/ffmpeg.wasm` | 17.9k | MIT | FFmpeg compiled to WASM — in-browser transcode |
| `Zulko/moviepy` | 15k | MIT | Python video editing (compose/trim/effects) — scripting glue layer |
| `mifi/editly` | 5.6k | MIT | Declarative JSON→video CLI+API |
| `WyattBlue/auto-editor` | 5.8k | Unlicense | Cut silence/boring parts automatically — EDIT path staple |
| `Breakthrough/PySceneDetect` | 5.4k | BSD | Scene-cut detection lib/CLI — segment planning input |
| `kkroening/ffmpeg-python` | 11k | Unlicense | Pythonic ffmpeg filter graphs |
| `mifi/lossless-cut` | 45.8k | MIT | Lossless trimmer GUI (binary, not cloned) |
| `SubtitleEdit/subtitleedit` | 14.9k | MIT | Windows subtitle editor |
| `arch1t3cht/Aegisub` + `Aegisub/Aegisub` | 1k/3.4k | BSD | ASS/SSA authoring — karaoke-style captions |
| `ThaUnknown/jassub` + `libass/libass` | 210/1.2k | — | WASM ASS renderer for preview |
| `CapSoftware/Cap` | 24.7k | — | Open-source Loom (screen record→share) — demo/walkthrough capture |
| `obsproject/obs-studio` | 79k | GPL | Screen recording/streaming standard |
| `ShareX/ShareX` | 40.9k | GPL | Windows capture/upload swiss-army |
| `blender/blender` | 21.8k(mirror) | GPL | **bpy headless = free VFX/motion-graphics render farm on this laptop** — OpenMontage already uses it for 3D shots |
| `NatronGitHub/Natron` | 5.7k | GPL | Open Nuke — node-graph compositing |
| `opentoonz/opentoonz`, `tahoma2d/tahoma2d` | 8.1k/685 | — | OpenToonz lineage (Ghibli tool) 2D animation |
| `penpot/penpot` | 62k | MPL | Open Figma — design→asset source |
| `excalidraw/excalidraw` + `dai-shi/excalidraw-animate` | 135k/2.1k | MIT | Sketch→animated SVG→video (whiteboard/explainer style) |
| `processing/p5.js` 24k · `paperjs/paper.js` 15k · `pixijs/pixijs` 48k · `konvajs/konva` 14.9k · `fabricjs/fabric.js` 31.5k | — | — | Creative-coding render libs usable inside HyperFrames/kinetograph compositions |
| `greensock/GSAP` 30k + `greensock/gsap-skills` 18k | — | Standard/no-charge | Animation lib + **official agent skills** (core/frameworks/react/scrolltrigger/timeline/plugins/utils/performance) — installable skill pack |
| `airbnb/lottie-web` 32k · `rive-app/rive-wasm` 1k · `mojs/mojs` 18.9k | — | — | Vector animation runtimes |

## 3. GENERATIVE VIDEO — LOCAL PATH (the 6 GB reality)

**Hub:** `Comfy-Org/ComfyUI` (146k★) — **installed** at `~/.aizee/media/apps/ComfyUI` with custom nodes: ComfyUI-Manager, GGUF (city96), VideoHelperSuite, AnimateDiff-Evolved, WanVideoWrapper (kijai), IPAdapter-plus, TTS-Audio-Suite, RMBG, LivePortraitKJ, Impact-Pack, KJNodes, **ReActor** (face swap).

| Repo | ★ | Role on 6 GB |
|---|---|---|
| `deepbeepmeep/Wan2GP` | 11.5k | **The pick.** One-stop app "for the GPU poor": Wan2.1/2.2, MiniMax H3, LTX-2/2.3/2.5, HunyuanVideo 1/1.5, LongCat, Kandinsky, LTXV, MagiHuman + image (Flux/Qwen/Z-Image/Ideogram4) + TTS + 3D. System-RAM offload, GGUF quants, `wangp-agent` dir = agent interface. Cloned — run its `installation/` flow when ready |
| `lllyasviel/FramePack` | 17.3k | Next-frame prediction: 13B video models on laptop GPUs, length-invariant context (anti-drift). Cloned |
| `Wan-Video/Wan2.1` + `Wan2.2` | 17-18k | Apache-2.0 open weights; TI2V-5B fits ~8 GB w/ ComfyUI offload (6 GB = tight but WanGP/GGUF path exists) |
| `Lightricks/LTX-Video` (v0.9.x) + **`Lightricks/LTX-2`** | 11k/10k | **LTX-2.5 is current** (Aug 2026): native audio+video, multi-shot, distilled variants; community license free <$10M rev. v0.9.x repo archived-ish — use LTX-2 |
| `Tencent-Hunyuan/HunyuanVideo` + `HunyuanVideo-1.5` | 12.7k/4.6k | 1.5 = lightweight 8.3B, ~14 GB w/ offload — GGUF Q4 in WanGP/ComfyUI is the 6 GB path |
| `MiniMax-AI/MiniMax-H3` | 11.7k | 33B open weights w/ stereo audio; WanGP 480p path; license excludes US/EU/UK/KR (not Egypt) |
| `meituan-longcat/LongCat-Video` | 9.4k | MIT, 13.6B, long-clip continuation — catalog |
| `ModelTC/lightx2v` | — | Unified low-VRAM inference framework (T2V/I2V/T2I/I2I + digital human), Apache-2.0, Docker images — strong candidate engine |
| `hao-ai-lab/FastVideo` | 4.8k | Accelerated inference + post-training for video gen |
| `SkyworkAI/SkyReels-V2` (1.3B/14B) + `SkyReels-A1` (portrait) | 7.8k/583 | Small variants fit laptops |
| `genmoai/mochi` · `jy0205/Pyramid-Flow` · `guoyww/AnimateDiff` · `zai-org/CogVideo` · `modelscope/DiffSynth-Studio` · `FoundationVision/Waver` · `PKU-YuanGroup/Helios` · `guandeh17/Self-Forcing` · `thu-ml/Causal-Forcing` · `NVIDIA/Cosmos` · `NVlabs/Sana` · `Stability-AI/generative-models` (SD3/SVD) | — | Model zoo — catalog in useful-repos |
| `black-forest-labs/flux` | 26k | Official FLUX.1 inference — image gen on 6 GB via GGUF (flux1-schnell Q4/Q8 in ComfyUI) |
| `lllyasviel/stable-diffusion-webui-forge` · `vladmandic/sdnext` · `lllyasviel/Fooocus` (53k) · `invoke-ai/InvokeAI` (29k) · `mcmonkeyprojects/SwarmUI` · `AUTOMATIC1111/stable-diffusion-webui` (165k) · `LykosAI/StabilityMatrix` | — | Image-gen UIs; **SD.Next & SwarmUI are the actively-developed picks for video models too** |
| `QwenLM/Qwen-Image` | 8.4k | Image gen+edit w/ strong text rendering — pairs w/ Wan ecosystem |
| `cubiq/ComfyUI_IPAdapter_plus` · `lllyasviel/ControlNet` · `tencent-ailab/IP-Adapter` · `instantX-research/InstantID` · `ToTheBeginning/PuLID` · `TencentARC/PhotoMaker` | — | **Character/identity consistency stack** — feeds `characters/` library (IP-Adapter refs, InstantID/PuLID face-lock, ControlNet pose/edge) |
| `kijai/ComfyUI-WanVideoWrapper` · `Kosinkadink/ComfyUI-VideoHelperSuite` · `city96/ComfyUI-GGUF` | — | ComfyUI video plumbing — installed |

## 4. TALKING HEAD / AVATAR / FACE (local)

`OpenTalker/SadTalker` 14k · `Rudrabha/Wav2Lip` 13k · `KlingAIResearch/LivePortrait` 19k · `TMElyralab/MuseTalk` 6.9k · `fudan-generative-vision/hallo` 8.7k · `Zejun-Yang/AniPortrait` 5k · `TMElyralab/MusePose` 2.7k · `magic-research/magic-animate` 10.9k · `MooreThreads/Moore-AnimateAnyone` 3.5k · `lipku/LiveTalking` 10k (realtime interactive) · `antgroup/echomimic_v2` 4.7k · `facefusion/facefusion` 30k · `hacksider/Deep-Live-Cam` 97k · `Gourieff/ComfyUI-ReActor` (installed) · `SkyworkAI/SkyReels-A1` · `PunithVT/ai-avatar-system` · `modstart-lib/aigcpanel`.

→ For aiZee `characters/`: **LivePortrait + MuseTalk + IPAdapter/InstantID in ComfyUI** is the practical local identity stack; facefusion/Deep-Live-Cam for face-swap edits.

## 5. SPEECH / MUSIC / AUDIO (local, 6 GB-friendly)

| Repo | ★ | Note |
|---|---|---|
| `hexgrad/kokoro` | 10k | Kokoro-82M — tiny, runs on CPU, great quality — **best default local TTS** |
| `rhasspy/piper` | 11k | Fast local neural TTS, many voices/langs |
| `snakers4/silero-models` | 6k | TTS + VAD + STT models, torch.hub one-liners |
| `SWivid/F5-TTS` | 15.5k | Flow-matching TTS, voice clone from ~15s ref |
| `index-tts/index-tts` | 25k | Industrial zero-shot TTS + emotion control |
| `FunAudioLLM→QwenAudio/CosyVoice` | 24k | Multilingual TTS family |
| `RVC-Boss/GPT-SoVITS` | 64k | 1-min voice cloning, singing too |
| `myshell-ai/OpenVoice` · `OpenBMB/VoxCPM` · `fishaudio/fish-speech` · `k2-fsa/OmniVoice` (600+ langs) · `coqui-ai/TTS` (XTTS-v2) · `debpalash/VoiceStudio` (106k claim, verify) · `0xShug0/audio.cpp` (C++ all-in-one TTS/STT/VAD/VC/music, no Python) · `diodiogod/TTS-Audio-Suite` (ComfyUI node: RVC/Echo-TTS/Qwen3-TTS/CozyVoice/IndexTTS-2/Chatterbox/F5/Higgs/VibeVoice) | — | Voice cloning/engines zoo — installed ComfyUI node covers most |
| `facebookresearch/audiocraft` (MusicGen/AudioGen/EnCodec) · `ACE-Step/ACE-Step` + `fspecii/ace-step-ui` · `multimodal-art-projection/YuE` (YuE2) · `Stability-AI/stable-audio-tools` · `suno-ai/bark` · `riffusion/riffusion-hobby` | — | Local music/SFX generation |
| `facebookresearch/demucs` | 10k | Source separation (vocals/drums/bass) — installed via uv |
| `Anjok07/ultimatevocalremovergui` | 27k | UVR5 GUI — stems for remix/dub |
| `m-bain/whisperX` | 25k | Whisper + **word-level timestamps + speaker diarization** — cloned; needs torch env (ComfyUI venv can host it) |
| `jianfch/stable-ts` | 2.3k | Stabilized whisper timestamps — installed via uv |
| `readbeyond/aeneas` | 2.9k | Forced alignment (existing transcript ↔ audio sync) |
| `pyannote/pyannote-audio` | 10.8k | Diarization/segmentation |
| `librosa/librosa` | 8.8k | Beat/onset analysis — **beat-synced edits need this** — installed via uv |

## 6. DUBBING / SUBTITLES / LOCALIZATION PIPELINES

`Huanshere/VideoLingo` 19k (Streamlit: yt-dlp→Qwen3-ASR+ForcedAligner word timing→term-consistent translate→segment→dub) · `jianchang512/pyvideotrans` 19.7k (GPL, full translate+dub GUI, many engines) · `krillinai/OpenCreator` 14k (AI workspace w/ skills: krillinai-cli/cover/pipeline/render-horizontal/render-vertical/subtitle/tts) · `buxuku/SmartSub` 6k (desktop: transcribe/translate/dub/burn, GPU) · `liuzhao1225/YouDub-webui` 5.8k · `ThioJoe/Auto-Synced-Translated-Dubs` 1.7k · `GuanYixuan/pyJianYingDraft` + `pyCapCut` (**JianYing/CapCut draft generation** — export real edit timelines!) · `Aseiel/VideoHighlighter` (Ollama-based local video analyzer/highlights) · `estebanstifli/LocalText2Voice` (audiobook/storyboard local app) · `DrewThomasson/ebook2audiobook` 20k.

→ aiZee EDIT/dub path upgrade: whisperX (word timing) + stable-ts + edge-tts/F5-TTS + ffmpeg ASS burn (libass via ffmpeg) or pyJianYingDraft for CapCut deliverables.

## 7. FACeless / FACTORY PIPELINES

Already installed: `harry0703/MoneyPrinterTurbo` (in `~/.aizee/media/apps/`). New: `ddean2009/MoneyPrinterPlus` 7.3k (batch + auto-publish CN platforms + chatTTS/GPT-SoVITS/faster-whisper + SD/ComfyUI image) · `IgorShadurin/app.yumcut.com` (lean Next.js factory) · `ATH-MaaS/Pixelle-Video` 29k (full-auto short engine) · `HBAI-Ltd/Toonflow-app` · `SamurAIGPT/AI-Faceless-Video-Generator` · `SaarD00/AI-Youtube-Shorts-Generator` (Gemini+EdgeTTS+FFmpeg) · `OpenMontage documentary-montage pipeline` (real-footage corpus path — unique).

## 8. ENHANCE / RESTORE / SEGMENT / UNDERSTAND

`k4yt3x/video2x` 22k (SR+interp framework) · `AaronFeng753/Waifu2x-Extension-GUI` 17k (all-in-one: waifu2x/Real-ESRGAN/RIFE/RTX-VSR/DAIN) · `TNTwise/REAL-Video-Enhancer` 2.4k (cross-platform GUI) · `mafiosnik777/enhancr` (TensorRT) · `hzwer/Practical-RIFE` + `nihui/rife-ncnn-vulkan` (vulkan=portable) · `bloc97/Anime4K` 21k · `sczhou/Upscale-A-Video` · `xinntao/Real-ESRGAN` 37k · `Fanghua-Yu/SUPIR` 5.7k (photo restoration) · `Sanster/IOPaint` 23k (lama inpaint object removal — pip-installable) · `danielgatis/rembg` 25k (bg removal — installed via uv) · `imgly/background-removal-js` + `addyosmani/bg-remove` (browser/on-device) · `facebookresearch/sam2` 20k (video segmentation) · `gaomingqi/Track-Anything` 7k (SAM+XMem+E2FGVI tracking) · `IDEA-Research/Grounded-Segment-Anything` 17k · `LiheYoung/Depth-Anything` 8k (depth for VFX) · `google-ai-edge/mediapipe` 37k (face/pose/hand tracking) · `deepinsight/insightface` 30k · `CMU-Perceptual-Computing-Lab/openpose` · `m-bain/whisperX` (above) · `Evil0ctal/Douyin_TikTok_Download_API` 21k (self-hosted TikTok/Douyin/Bilibili API **with MCP server + offline STT**) · `imputnet/cobalt` 46k (media downloader API) · `yt-dlp/yt-dlp` 206k (**installed via uv**).

## 9. DEV / PM TOOLING ("مبرمج فوق الوصف + مدير مشاريع")

### Spec-driven development (the PM-in-code layer)
- `github/spec-kit` **149k** — official SDD toolkit (`.specify`, presets, extensions, integrations, templates). Heavy but canonical.
- `Fission-AI/OpenSpec` **74k** — spec→plan→tasks→apply flow, `openspec/` + `schemas/` + `skills/`; aiZee already has OpenSpec-style `specs/changes/` — **compare & align**.
- `bmad-code-org/BMAD-METHOD` **55k** — agile AI-driven dev: Clarify→Plan→Build→Learn loop w/ agent personas (PM/architect/dev/QA) as skills+tools. **Closest thing to "AI project manager".**
- `spec-kitty/spec-kitty` 1.7k — `spec→plan→tasks→next→review→accept→merge` CLI + governance packs.
- `Pimzino/spec-workflow-mcp` 4.3k — MCP server + live dashboard + VSCode ext for spec workflows.
- `gemini-cli-extensions/conductor` 3.8k — SDD plugin for agent CLIs.
- `Gentleman-Programming/agent-teams-lite` 1.2k — orchestrator + 9 sub-agents, pure markdown, zero deps.
- `sno-ai/mda` 616 — `.mda` markdown superset → compiles to SKILL.md/AGENTS.md/MCP-SERVER.md/CLAUDE.md, JSON-schema validated, Sigstore-signed — **directly relevant to aiZee's multi-adapter rules sync**.

### Agent harness / context / memory
- `davila7/claude-code-templates` **33k** — open registry+CLI for Claude Code components (agents/commands/skills/hooks/MCPs/settings/mods) — installable catalog.
- `hesreallyhim/awesome-claude-code` **57k** — canonical list.
- `yamadashy/repomix` **29k** — repo→single AI-friendly file (**installed via bun**).
- `mufeedvh/code2prompt` 7.7k · `coderamp-labs/gitingest` 16k — same class (catalog).
- `thedotmack/claude-mem` **115k** — persistent memory across sessions for every agent harness (Claude/Codex/Cursor/Gemini/Hermes/Copilot/OpenCode…) — compressed recall injection; aiZee MemoryStore is the sovereign equivalent — study its compression/handoff formats.
- `DeusData/codebase-memory-mcp` **48k** — local code-intelligence graph + MCP + change-aware test selection (graphify competitor/complement).
- `rohitg00/agentmemory` 30k · `iOfficeAI/AionUi` 34k · `manaflow-ai/cmux` (macOS only) — agent memory/UI layer.
- `tt-a1i/archify` **95k** — idea→interactive HTML diagram agent skill.
- `affaan-m/ECC` 300k — already adopted by aiZee (see ACTIVE_CONTEXT).
- `JuliusBrussee/caveman` 118k — token-cutting skill (aiZee already uses CAVENMAN comms).
- `coreyhaines31/marketingskills` 59k — CRO/copy/SEO/growth skills.
- `NeoLabHQ/context-engineering-kit` 1.8k — context-engineering Claude skills + CodeRabbit OSS alt.
- `ai-boost/awesome-prompts` 9k · `Meirtz/Awesome-Context-Engineering` 3.3k · `Windy3f3f3f3f/how-claude-code-works` 3.8k · `wquguru/harness-books` 3.2k · `dair-ai/Prompt-Engineering-Guide` 80k — research shelf.
- Agent browsers: `vercel-labs/agent-browser` 48k · `citrolabs/ego-lite` 22k · `browseros-ai/BrowserOS` 14k · `nanobrowser/nanobrowser` 14k · `jo-inc/camofox-browser` 12k · `Tencent/BrowserSkill` 10k — logged-in-session automation for agents (playwright already installed).

### PM / knowledge / docs
- `makeplane/plane` **62k** — open Jira/Linear/Monday/ClickUp alt (issues, sprints, docs, triage; has AI features) — **top self-hosted PM pick**.
- `opf/openproject` 17k — enterprise PM (Gantt, time tracking, agile).
- `croffasia/itsaplan` 2.2k — Linear/Plane alt where **teams and AI agents work side by side**.
- `mattermost-community/focalboard` 26.5k — Trello/Notion/Asana alt (kanban).
- `Leantime/leantime` 12k — goals-first PM for non-PMs (ADHD/autism/dyslexia-friendly).
- `super-productivity/super-productivity` 23.5k — todo+timeboxing+Jira/GitLab/GitHub integrations.
- `toeverything/AFFiNE` 74k · `AppFlowy-IO/AppFlowy` 78k · `outline/outline` 41k · `docmost/docmost` 22k — Notion/Confluence alternatives (docs+wiki+whiteboard).
- `docsifyjs/docsify` 31k · `withastro/starlight` 9.5k · `fuma-nama/fumadocs` 13.6k · `facebook/docusaurus` — docs-site generators.
- `wonderunit/storyboarder` 3.9k — classic free storyboard app (stick-figure frames) — pre-visualization for video briefs.

### Automation / orchestration
- `n8n-io/n8n` **210k** — fair-code workflow automation, 400+ integrations, native AI — the PM-automation backbone candidate.
- `activepieces/activepieces` 25k — AI agents+MCPs+automation, ~400 MCP servers.
- `windmill-labs/windmill` 18k — code-first workflows/apps/agents orchestrator.
- `kestra-io/kestra` 30k — declarative YAML control plane for data/infra/business/AI workflows.
- `triggerdotdev/trigger.dev` — durable background jobs (catalog).

### Code-quality / repo tooling
- `jesseduffield/lazygit` 83k · `jdx/mise` 36k (polyglot tool/env/task mgr) · `casey/just` 36k (command runner) · `sharkdp/fd` 45k · `sharkdp/bat` 61k · `ajeetdsouza/zoxide` 40k · `junegunn/fzf` 84k · `orhun/git-cliff` 12.5k (changelog gen) · `gitbutlerapp/gitbutler` 21k (GitButler VCS client) — terminal/devx layer.
- `biomejs/biome` 26k · `oxc-project/oxc` 23k — fast lint/format toolchains.
- `nrwl/nx` 29k ("amplifies developers AND AI agents") · `vercel/turborepo` 31k ("build system for coding agents") · `moonrepo/moon` 4k — monorepo layer.

## 10. WHAT WAS INSTALLED ON THIS MACHINE

| Item | Where / how |
|---|---|
| ComfyUI + 12 custom nodes | `~/.aizee/media/apps/ComfyUI` (git-init'd in place; nodes: Manager, GGUF, VideoHelperSuite, AnimateDiff-Evolved, WanVideoWrapper, IPAdapter-plus, TTS-Audio-Suite, RMBG, LivePortraitKJ, Impact-Pack, KJNodes, ReActor) — **venv `.venv` (py3.12) + torch cu128 + requirements installing in background** |
| uv tools | `yt-dlp`, `moviepy`, `scenedetect`, `auto-editor`, `demucs`, `stable-ts`, `rembg[cpu]`, `librosa` — isolated envs, no base-python pollution |
| repomix | `bun add -g repomix` |
| 81 study clones | `temp/repo-study-2026-11-10/<org>__<repo>` (depth-1; blobless for giants) |
| Already present (prior waves) | ffmpeg 9.0.2+NVENC shim, hyperframes 0.9.23, bun 1.4.4, playwright+chromium, faster-whisper, edge-tts, kits {cinecode, bang-motion, motion-graphics, motion-design}, apps {MoneyPrinterTurbo, Vvveb} |

## 11. RECOMMENDED NEXT ACTIONS (for user decision)

1. **Try the free local video path end-to-end:** Wan2GP install (`installation/` subsystem) OR ComfyUI + Wan2.2-TI2V-5B GGUF / LTX-2.5 distilled via `kijai/ComfyUI-WanVideoWrapper` — first real AI-generated clip on this GPU.
2. **Adopt OpenMontage patterns into `skills/video-produce` v2** (AGPL = ideas only): `pipeline_defs/*.yaml` manifests, stage-director skills, append-only `decision_log`, capability-envelope preflight (`provider_menu_summary`), reference-video entry (`video-reference-analyst`), approval gates. Biggest single upgrade available.
3. **Install skill packs:** `npx skills add diffusionstudio/skills` · `greensock/gsap-skills` · `adithya-s-k/manim_skill` · `iart-ai/motion-skills` packs · `nexu-io` skills (motion-anything/html-anything) — evaluate then port winners into `skills/`.
4. **PM layer:** `plane` (self-hosted Jira) vs keeping aiZee-native task workflows; `n8n` for automation glue; `mda` format for multi-adapter doc sync.
5. **Dubbing/subtitle path:** whisperX word-timing + edge-tts/F5-TTS + libass burn — upgrades EDIT path.
6. **Character consistency:** wire `characters/` sheets → IPAdapter/InstantID/PuLID refs in ComfyUI + LivePortrait/MuseTalk for talking shots.

## 11b. IMPLEMENTED (2026-11-10, non-video/audio per user)

**Personas adopted:** DEVOPS + DEVX (aizee persona detect) — skills devops-engineer + context-compressor.

**Installed & verified:**
- mise 2026.11.5 (scoop) → `mise use -g` {fd 10.5.2, bat 0.26.1, zoxide 0.10.0, fzf 0.75.0, lazygit 0.66.3, just 1.59.0, git-cliff 2.14.2, biome 2.6.6, hyperfine 2.0.0}; `mise activate` written to both PowerShell profiles.
- npm -g: n8n 2.47.3 · @markdown-ai/cli (mda) 1.1.7 · @fission-ai/openspec 1.17.0 · @pimzino/spec-workflow-mcp 2.2.7 · agent-browser 0.42.0 · oxlint 1.93.0.
- uv tools: spec-kitty-cli 3.2.7 · specify-cli 1.3.4.dev0 (github/spec-kit).
- cargo: code2prompt 4.3.0. bun: repomix 1.19.0 (+`~/.bun/bin` added to user PATH).
- scoop GUI: super-productivity 20.0.0 · gitbutler 0.23.3 (CLI `but`).
- ComfyUI: venv complete, torch 2.11.0+cu128, `torch.cuda.is_available()=True` on RTX 4050.
- skills.sh → `~/.agents/skills` (symlinked to 50+ agent harness dirs): **archify**, **marketingskills** (~40 skills: seo/cro/ads/email/sales/launch...), **BMAD-METHOD** full (bmad agents: Mary analyst, Winston architect, Amelia dev, John PM, Sofia PO, Sally UX + bmod-* workflows).
- MCP: `spec-workflow` added to `.devin/mcp_config.json`.
- `deps.yaml`: +22 dep entries (44 total) — `aizee deps check --root E:\server\.ai` all OK.

**Deferred (video/audio):** Wan2GP install, gen-model downloads, whisperX env, TTS engines, dub pipelines — per user instruction.

**Known caveats:** n8n install-scripts were npm-allowScripts-blocked (sqlite3/isolated-vm native builds) — `n8n --version` passes; first real `n8n` launch may need `npm rebuild` inside its global dir or allow-scripts config. Docker daemon off → plane/openproject/outline/docmost/AFFiNE/AppFlowy stay documented-only (heavy self-host stacks). claude-mem/codebase-memory-mcp/agentmemory not auto-installed (hook other agents' configs / heavy indexing) — patterns in useful-repos.

## 12. LICENSE FLAGS

- **AGPL (study only, no vendor):** OpenMontage, pyvideotrans, domain-digger(prev), Vvveb(prev).
- **GPL:** Blender, Audacity, HandBrake, Aegisub(ish), OBS, ShareX, pyJianYingDraft(? check per-repo).
- **Company/source-available:** Remotion (free ≤ certain size — check current license for commercial use).
- **Community/revenue-capped:** LTX-2.x (<$10M rev free), MiniMax H3 (territory exclusions — Egypt OK), HunyuanVideo (Tencent community license — check territory clause).
- **Apache/MIT (safe to study + port patterns):** everything else flagged above.
