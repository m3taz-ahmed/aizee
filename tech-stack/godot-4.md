[TECH] Godot 4
[OBJ] Open-source game engine (MIT) — node/scene architecture, GDScript 2.0, C# (.NET), GDExtension, built-in 2D/3D, lightweight editor.
[RULES]
1. [REQ] Read `project.godot` + `.godot/` version stamp before assuming the minor version — `[VER-01]` applies: features differ across 4.0 -> 4.5 (e.g., `PhysicsServer2D` APIs, shader built-ins).
2. [REQ] Scene tree thinking: everything is a `Node` in a tree; compose scenes from reusable `.tscn` files; use `instantiate()`/`PackedScene` not deep copy-pasted branches.
3. [REQ] Signals over polling: connect node signals (`button.pressed`, custom `signal health_changed`) for decoupling; use `Callable` binds and `CONNECT_*` flags deliberately.
4. [REQ] GDScript 2.0 typing: use static types (`var hp: int = 10`, `func move(d: Vector2) -> void`), `@export` for designer-tunable values, `@onready` for node refs, `@tool` only when editor-time execution is intended.
5. [REQ] Autoloads sparingly: singletons (`AutoLoad`) for true global services (save, audio bus, scene transition); gameplay state lives in the scene tree or explicit state objects — no singleton soup.
6. [REQ] Fixed-step sim: physics/game logic in `_physics_process(delta)` at fixed tick; rendering/interpolation in `_process(delta)`; never tie simulation to render rate.
7. [REQ] Resources for data: custom `Resource` subclasses (`.tres`) for items/abilities/tuning tables; JSON only for interop — resources get inspector support + type safety.
8. [REQ] Groups + layers: use groups for queries (`get_tree().get_nodes_in_group`), physics layers/masks as named bitmask constants — never magic collision numbers.
9. [REQ] Scene edits in the editor: hand-edit `.tscn`/`.tres` only for trivial fields — binary-ish serialization means malformed edits corrupt silently; prefer `EditorScript`/`tool` scripts for bulk ops.
10. [REQ] C# (.NET build): use when the team is C#-native or needs NuGet — it is a separate export path (`Godot.NET.Sdk`), cannot mix freely with GDScript export templates, and adds AOT/size cost on mobile.
11. [REQ] GDExtension for hot paths: engine-level perf (terrain, physics servers, big data crunching) goes to GDExtension (C++/Rust via godot-rust), not GDScript micro-optimization.
12. [REQ] Testing: GUT (GDScript) or gdUnit4 for unit/integration — headless via `godot --headless -s addons/gut/gut_cmdln.gd`; scene-level smoke via a boot-test scene; observe evidence rule applies (`rules/run-and-observe.md`).
13. [REQ] Export discipline: `.export_presets.cfg` versioned; per-platform feature tags; `embed_pck` and encryption settings decided per release channel.
14. [PROHIBIT] `get_node()` string paths scattered through code (use `@export var` node refs or unique-name `%Node` syntax); logic in `_ready()` that depends on sibling order; per-frame `load()`/`instantiate()` of heavy scenes without pooling; editing `project.godot` values at runtime expecting persistence.
[COMPAT]
- 4.0-4.1: GDScript 2.0, Vulkan renderers, tilemap rework. Breaking vs 3.x everywhere — never port 3.x snippets blindly.
- 4.2: `AnimationTree` rewrites, `CodeEdit`, C# on Android, `ResourceSaver` flags.
- 4.3: `Parallax2D`, audio interactive music, `Waypoint2D`, multi-window support fixes.
- 4.4: typed dictionaries, `AGL`/`Metal` progress, Jolt physics option, embedded game window.
- 4.5+: shader baker, stencil buffer, `ScriptLanguage` cleanup, accessibility features (screen-reader hooks); verify minor APIs post-cutoff via Context7 `/godotengine/godot-docs` or official docs.
[REFS]
- https://docs.godotengine.org/en/stable/
- https://github.com/godotengine/godot-docs
- https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/index.html
