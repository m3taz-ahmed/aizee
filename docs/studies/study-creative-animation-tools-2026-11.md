# Ideas-Repo Study — 2026-11-12

Source: `temp/ideas_repo/*.webp` — 10 showcase slides (two carousels, @martiendejong_dev: an 8-slide "2D animation tools" set + a 13-slide "VFX/creative stack" set). All 10 repos cloned `--depth 1` to `temp/ideas_repo/repos/`. Personas: ARCH + ai-agents-architect.

Question asked: how can aiZee benefit — anything to take or develop into the project?

## Inventory

| Repo | Stars | Lang | License | Last push | Tool |
|------|------:|------|---------|-----------|------|
| `opentoonz/opentoonz` | 8.2k | C++ | NOASSERTION (BSD-derived) | 2026-11-12 | 2D animation studio |
| `friction2d/friction` | 2.0k | C++ | GPL-3.0 | 2026-11-12 | 2D motion graphics |
| `freemocap/freemocap` | 10.8k | TS+Py | AGPL-3.0 | 2026-11-11 | markerless mocap |
| `synfig/synfig` | 2.4k | C++ | GPL-3.0 | 2026-11-08 | vector 2D animation |
| `effekseer/Effekseer` | 2.1k | C/C# | MIT | 2026-10-30 | particle FX editor+runtime |
| `theatre-js/theatre` | 13.0k | TS | Apache-2.0 | 2024-08-14 (stalled) | web motion editor |
| `pencil2d/pencil` | 1.9k | C++ | GPL-2.0 | 2026-11-12 | hand-drawn 2D animation |
| `AcademySoftwareFoundation/openvdb` | 3.5k | C++ | Apache-2.0 | 2026-11-09 | sparse volume data |
| `svgdotjs/svg.js` | 11.9k | JS | MIT | 2026-08-04 | SVG DOM library |
| `NatronGitHub/Natron` | 5.7k | C++ | GPL-2.0 | 2026-07-24 | node-graph compositor |

## Per-repo findings (evidence → adoptable pattern)

### Natron — `repos/natron`
- `Engine/Cache.h` + `CacheEntry.h` — content-addressed render cache: each node hashes inputs+params (`getHash`) → cache key; memory+disk tiers.
- `HostSupport/` — OpenFX plugin host: stable C ABI; plugins declare params/contexts/actions, host stays generic.
- `Engine/` vs `Gui/` split — headless engine, optional UI.
- **Take:** hash-keyed step memoization; plugin descriptor ABI.

### OpenToonz — `repos/opentoonz`
- `toonz/sources/common/tfx/` — pull-based render DAG: `tfxcachemanager`, `tpassivecachemanager`, `tpredictivecachemanager`, `tcacheresourcepool`. Predictive manager speculatively renders nodes likely needed next.
- `common/tparam/` — `tdoubleparam` keyframed params; `tparamuiconcept.h` attaches UI-render hints to param schema (schema→UI, same as Theatre propTypes).
- `toonzfarm/{tfarm,tfarmclient,tfarmcontroller,tfarmserver}` — distributed task farm: controller chunks DAG work, servers lease+heartbeat.
- `common/txsheet/` — exposure sheet = tabular scene timeline.
- `common/expressions/` — param expressions.
- **Take:** predictive prefetch, farm lease/heartbeat worker model, param-UI-concepts.

### OpenVDB — `repos/openvdb`
- `openvdb/openvdb/openvdb/tree/` — Root→Internal→Leaf sparse hierarchy; tiles flagged active/inactive.
- `nanovdb/` — flattened, immutable, GPU-friendly compiled grids (build once, serve read-only).
- `tools/` + `openvdb_ax/` — AX expression DSL compiled to IR over grids; ValueAccessors cache lookup paths for O(1) repeat access.
- **Take:** immutable compiled snapshot export for memory/index; active/inactive tile model (extends `memory/sectors.py`+`heat.py`); accessor path-caching for catalog hot paths.

### FreeMoCap — `repos/freemocap` (AGPL — concepts only)
- `freemocap/pubsub/` — `pubsub_topics.py`: dataclass Topics auto-register via `__init_subclass__`; `pubsub_manager`/`pubsub_relay` decouple pipeline from UI and websocket.
- `core/pipeline/{abcs,posthoc,realtime}` + `pipeline_stage_timer.py`/`pipeline_timing_reporter.py` — stage abstraction with per-stage timing instrumentation.
- `core/tasks/{calibration,mocap,triangulation}` — task registry; stage artifacts on disk, re-runnable from any stage.
- `api/{http,websocket,routers}` + `freemocap-ui/` Electron — thin UI over the event bus.
- **Take:** typed pub/sub event bus; per-stage timing; multi-view triangulation as an ensemble-verification analogy (calibrate shared ground truth, then fuse views).

### Theatre.js — `repos/theatre`
- `packages/dataverse/` — `Atom.ts`, `pointer.ts`, `prism/` — path-addressed reactive state (`val(pointer)`), lenses/prisms for derived sub-state.
- `packages/core/src/propTypes/` — prop-type schema auto-drives Studio's editor UI.
- `packages/studio/` — `Scrub.ts` timeline scrubbing, `PaneManager`, `IDBStorage` offline persistence.
- **Take:** schema→dashboard panes; pointer-style path addressing for memory/graph; Scrub → audit-log timeline replay.

### Synfig — `repos/synfig`
- `synfig-core/src/synfig/valuenodes/` — ~100 ValueNode types (`add`, `average`, `atan2`, `animated`, `bline`, `bone`…): every parameter is a computed node in a dataflow graph; links make params parametric without keyframes.
- **Take:** extend `call_plan` expression AST with "value nodes" that compute step args from memory/state/other steps.

### Friction — `repos/friction`
- `src/core/Expressions/` — `propertybindingparser`, `framebinding`, `scenebinding`, `valuebinding`, `expressionpresets`: JS-expression property-binding DSL with dependency tracking.
- `src/core/Animators/` — `graphanimator` + `complexanimator` container hierarchy.
- **Take:** same binding model for plan args / deps.yaml placeholders.

### Pencil2D — `repos/pencil`
- `core_lib/src/activeframepool.{h,cpp}` — bounded pool of "active" frames = working-set cache for current timeline window.
- `core_lib/src/onionskinsubpainter.{h,cpp}` — onion-skin = ghost overlay of prev/next states.
- `core_lib/src/structure/` — Object/Layer/KeyFrame separation.
- **Take:** onion-skin = ghost-state diff for plan dry-runs and memory writes; bounded working-set pool for graph/memory hot queries.

### Effekseer — `repos/effekseer`
- `Dev/Cpp/Effekseer` runtime core + `EffekseerRenderer{DX9,DX11,DX12,GL,Metal,LLGI,Vulkan}` backend matrix + `Dev/Editor` C# tool.
- `Dev/*.i` SWIG interface files + `gen_swig.bat` — one core → many language/engine bindings (Unity/UE/Cocos/DXLib runtimes).
- **Take:** validates existing direction — `harness_exporter.py` (skills→claude/codex/cursor/opencode) is the same one-core/many-bindings pattern; aiZee MCP server = binding surface over the kernel.

### SVG.js — `repos/svg.js`
- `src/modules/{core,optional}` — every API is a chainable module registered onto shared classes; `svg.js.d.ts` single type surface.
- **Take:** fluent plan-builder DSL emitting inert plan JSON (`Plan().step(...).fanout(...).suspend()`); mixin-style module registration.

## Cross-cutting → aiZee map

| Pattern | Source | aiZee today | Proposal |
|---------|--------|-------------|----------|
| Typed event bus / pubsub | FreeMoCap `pubsub_topics` | none found | `runtime/event_bus.py` — dataclass Topics auto-register via `__init_subclass__`; feeds dashboard live view, MCP progress, audit taps |
| Content-hash step memoization | Natron `CacheEntry` | resume skips settled steps *within a run* only | `runtime/step_cache.py` — hash(tool+args+env)→artifact store; resume across runs, skip when args unchanged |
| Predictive prefetch | OpenToonz `tpredictivecachemanager` | none | during plan exec, prefetch next-step tool/skill/context by static look-ahead |
| Schema→UI (param UI concepts) | Theatre propTypes, Toonz `tparamuiconcept` | `runtime/schemas.py` + dashboard (static) | UI-hint annotations on pydantic schemas/skill frontmatter → auto-rendered dashboard panes |
| Value/param binding | Synfig ValueNodes, Friction bindings | `call_plan` tiny-AST exprs (step env only) | extend expr AST with memory/state/cross-step refs |
| Timeline replay / scrub | Theatre `Scrub`, Natron curves, Pencil timeline | audit hash-chain exists, no replay view | `aizee replay <run>` + dashboard "dope sheet" of tool calls |
| Fluent plan DSL | SVG.js | hand-authored JSON plans | `runtime/plan_builder.py` — chainable builder emitting inert JSON (keeps inertness guarantee) |
| Farm lease/heartbeat workers | toonzfarm | `mcp_orchestrator` fan-out | lease+heartbeat+retry for long-running fan-out workers (local pool first; GH issues as queue per worker-agent contract) |
| Immutable compiled snapshot | NanoVDB | `memory ingest` rebuilds | export flattened read-only memory/index snapshot for fast cold-start + distribution |
| Onion-skin ghost diff | Pencil2D | `plan_diff_validator` exists | apply ghost-diff view to plan dry-run + memory write preview |
| Bounded working-set pool | Pencil `activeframepool` | `approval_cache.py`, catalog indexes | cap hot-path caches by working-set window, not unbounded |
| Multi-view consensus | FMC calibration→triangulation | `llm_attestation`, EGM goldfish | already analogous — calibrate rubric first, fuse reviewer "views" |
| One core / many bindings | Effekseer SWIG | `harness_exporter`, MCP server | already analogous — keep, formalize binding registry |

## Ranked adoption candidates

1. **`runtime/event_bus.py`** — typed pubsub (FreeMoCap pattern). Unblocks dashboard live progress, MCP progress reporting, decoupled audit/observability taps. Clear gap, self-contained.
2. **Step memoization in `call_plan`** (Natron hash cache) — persist step results keyed by content hash; survives re-runs with edited args. High value, small surface.
3. **`runtime/plan_builder.py` fluent DSL** (SVG.js) — safer plan authoring, output stays inert JSON. Low effort, DX win.
4. **Predictive prefetch** (OpenToonz) — look-ahead warm-up during plan exec.
5. **Schema UI concepts → dashboard** (Theatre/Toonz) — annotate pydantic/frontmatter, auto-render panes.
6. **`aizee replay` audit timeline** (Theatre Scrub analog) — session dope-sheet + point-in-time state.
7. **Farm lease model** (toonzfarm) — heartbeat/lease/retry for fan-out workers.
8. **ValueNode/binding expressions** (Synfig/Friction) — compute plan args from refs.
9. **Immutable memory snapshot export** (NanoVDB analog).
10. **Onion-skin dry-run diff + bounded working-set cache** (Pencil2D).

## Licensing

- Adaptable with attribution: Effekseer (MIT), svg.js (MIT), theatre (Apache-2.0), openvdb (Apache-2.0).
- Patterns-only (re-implement, no vendoring): Natron (GPL-2.0), Friction (GPL-3.0), Synfig (GPL-3.0), Pencil2D (GPL-2.0), OpenToonz (BSD-derived custom), FreeMoCap (AGPL-3.0 — concepts only).

## Non-goals

These are desktop creative apps (Qt/C++, Electron/TS); nothing ships into aiZee directly. Value is architectural patterns, not code or the tools themselves (except optionally listing the animation tools in `useful-repos.md` for the video/motion pipeline).
