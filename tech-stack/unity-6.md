[TECH] Unity 6
[OBJ] Unity engine 6000.x line (formerly Unity 2023+) — C# MonoBehaviour + optional DOTS/ECS, URP/HDRP render pipelines, Addressables, UI Toolkit, Netcode for GameObjects.
[RULES]
1. [REQ] Read `Packages/manifest.json` + `ProjectSettings/ProjectVersion.txt` for the exact editor+package versions `[VER-01]` — Unity 6.0 vs 6.1+ APIs differ (e.g., `RenderGraph` maturity).
2. [REQ] MonoBehaviour lifecycle discipline: `Awake` self-setup, `OnEnable` wiring, `Start` cross-object init, `OnDisable` teardown; never touch other objects' components in `Awake`.
3. [REQ] `Update` is render-delta: gameplay sim in `FixedUpdate` (fixed timestep physics) or a manual tick; never `Time.deltaTime` inside `FixedUpdate` (use `Time.fixedDeltaTime`).
4. [REQ] SerializeField over public: `[SerializeField] private` fields for designer values; `public` only for real API. Config/tuning data in `ScriptableObject` assets, never in prefab overrides.
5. [REQ] Find-free hot paths: cache component refs at init; no `FindObjectOfType`/`GetComponent`/`SendMessage` per-frame; `TryGetComponent` over null-check patterns.
6. [REQ] Allocation hygiene: no LINQ/closures/`yield` allocations in per-frame code; object pooling (`ObjectPool<T>`) for projectiles/enemies/VFX; `StringBuilder`/`NativeArray` where needed.
7. [REQ] Scenes as composition: additive scene loading for levels; `DontDestroyOnLoad` only for true app services; scene-specific managers in the scene, not global.
8. [REQ] Addressables for content: assets/levels behind addressable groups with async load/release handles (`Addressables.Release`); `Resources/` folders only for tiny bootstrap assets.
9. [REQ] UI: UI Toolkit for new runtime UI (USS/UQuery/data binding); uGUI maintained for legacy canvases — pick one system per feature, do not mix event models casually.
10. [REQ] DOTS/ECS is opt-in: use Entities + Burst for high-entity-count sims (crowds, projectiles, sim cells); hybrid pattern keeps GameObjects for presentation — profile before committing.
11. [REQ] Testing: Unity Test Framework — EditMode tests (pure logic, no scene), PlayMode tests (runtime/scene); CI via `-batchmode -runTests -testPlatform EditMode`; screenshot evidence via captured game view for visual stories (`rules/run-and-observe.md`).
12. [REQ] Builds: define per-platform scripting symbols; `Development Build` flag for profiling builds; IL2CPP for release; pin `EditorBuildSettings` scene list in CI checks.
13. [REQ] Netcode: server-authoritative state for multiplayer; `NetworkVariable` for replicated state, RPCs for events — no client-authoritative competitive logic.
14. [PROHIBIT] Singleton `Instance` statics for everything; `Update()` polling for state that events cover; `Resources.Load` in hot paths; coroutine chains for logic that needs cancellation (use `async`/state machines); editor-only APIs (`UnityEditor`) in runtime asmdefs.
[COMPAT]
- 6.0 (6000.0): STP upscaler, RenderGraph (URP), GPU Resident Drawer, ECS for Entities 1.3, WebGPU early.
- 6.1+: RenderGraph default-on path, deferred+ improvements, updated Input System defaults; verify package versions in manifest post-cutoff.
- Legacy: Unity 2021/2022 LTS APIs (non-RenderGraph URP, old Input Manager) still dominate shipped projects — confirm before assuming 6000.x-only APIs.
[REFS]
- https://docs.unity3d.com/6000.0/Documentation/Manual/
- https://docs.unity3d.com/Packages/com.unity.test-framework@latest
- https://docs.unity3d.com/Packages/com.unity.addressables@latest
