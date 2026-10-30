[TECH] Unreal Engine 5
[OBJ] AAA engine (C++/Blueprints) — Nanite/Lumen, Gameplay Ability System (GAS), Enhanced Input, UMG/CommonUI, Chaos physics, server-authoritative replication, Lyra/Mover patterns.
[RULES]
1. [REQ] Read `.uproject` `EngineAssociation` + `Build.version` + plugin versions `[VER-01]` — 5.0 vs 5.5+ differ sharply (GAS maturity, Iris replication, CommonUI).
2. [REQ] C++/Blueprint split: base classes + performance-critical paths in C++; Blueprints for designer logic, data-driven content, and glue — never business rules trapped in Blueprint-only graphs the codebase cannot refactor.
3. [REQ] UPROPERTY discipline: expose with minimal specifiers (`EditDefaultsOnly` over `EditAnywhere`, `BlueprintReadOnly` over write); metadata categories named; no public non-UPROPERTY state on engine objects.
4. [REQ] GAS for abilities/stats: `UAbilitySystemComponent` + GameplayAttributes + GameplayEffects + GameplayTags — attribute changes flow through effects/prediction, never raw property writes on replicated actors.
5. [REQ] Enhanced Input only: `UInputMappingContext` + `UInputAction` (Trigger/Pressed/Released semantics); legacy `InputComponent` axis/action bindings are deprecated patterns in new code.
6. [REQ] Replication is server-authoritative: state in replicated properties/`OnRep_*` or push-model `MARK_PROPERTY_DIRTY`; gameplay decisions on server; client sends `Server_*` RPC requests — competitive logic never trusts the client.
7. [REQ] Actor composition: `UActorComponent` for reusable behaviors (health, interaction, inventory); interfaces (`UINTERFACE`/`IInterface`) over casting to concrete classes; soft references (`TSoftObjectPtr`/`FSoftObjectPath`) for cross-level asset refs.
8. [REQ] Subsystem singletons: `UGameInstanceSubsystem`/`UWorldSubsystem`/`ULocalPlayerSubsystem` for services — not custom static singletons hanging off GameInstance casts.
9. [REQ] Asset management: PrimaryAssets + Asset Manager for streamed content; async loading (`FStreamableManager`) with handles; hard references only for bootstrap-critical assets.
10. [REQ] UMG/CommonUI: CommonUI for cross-platform UI (input routing, style, activatable stacks); widgets stay presentation-only — they bind to view model/subsystem state, never own gameplay state.
11. [REQ] Tick budget: no per-frame `Tick` on hundreds of actors — timers, delegates, `SetTickInterval`, or mass/ECS-style processors for high counts; `PrimaryActorTick` off by default in constructors.
12. [REQ] Testing: Functional Testing Framework (automation tests `IMPLEMENT_SIMPLE_AUTOMATION_TEST`) + Gauntlet for device runs; headless `-ExecCmds="Automation RunTests"`; visual stories need OBSERVED evidence (`rules/run-and-observe.md`).
13. [REQ] Build discipline: one `Target.cs` per build target (Game/Editor/Server/Client); modular `Build.cs` deps (trim unused modules — build time is a budget); dedicated-server target compiles clean.
14. [PROHIBIT] Game-mode/UI/state stored on the wrong owner (PlayerController vs PlayerState vs GameState — learn the framework roles); `GetAllActorsOfClass` in gameplay code; synchronous `LoadObject` on the game thread; Blueprint `Cast To` chains as architecture.
[COMPAT]
- 5.0-5.1: Nanite/Lumen GA, World Partition, GAS out of experimental, Chaos default.
- 5.2-5.3: Mover (experimental), PCG framework, improved Iris, CommonUI maturity, Substrate early.
- 5.4: Motion Matching, modular gameplay maturity, Nanite tessellation, retargeting rework.
- 5.5+: MegaLights, Iris progress, Mutable character customization, Fab marketplace integration — verify exact minor APIs post-cutoff.
[REFS]
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-6-documentation
- https://github.com/EpicGames/UnrealEngine (source access requires linked Epic account)
- https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-in-unreal-engine
