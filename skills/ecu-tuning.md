---
name: ecu-tuning
description: Open engine-management firmware (rusEFI/Speeduino/HaniCore/hellen-one), tuning software (LibreTune/TunerStudio INI ecosystem), flasher hardware, locked-bootloader reality, and engine simulators. Load for ECU/tuning/flashing questions.
triggers:
  - ecu
  - tuning
  - tuner
  - flash
  - remap
  - chip tuning
  - speeduino
  - rusefi
  - megasquirt
  - tunerstudio
  - libretune
  - hani
  - hellen
  - me7
  - med17
  - simos
  - boost
  - fuel map
  - ignition map
  - afR
  - wideband
  - engine management
---

[SKILL] ecu-tuning
[OBJ] Navigate ECU tuning/flashing correctly: open-EMS ecosystem, tuning-software landscape, flasher hardware, and the locked-bootloader reality for stock ECUs.
[COMPAT] skills/auto-domain-map.md, skills/obd-diagnostics.md (data acquisition), skills/vag-diagnostics.md (VAG flashing), skills/auto-mechanics-engines.md (engine concepts), tech-stack/automotive-ecu-internals.md (deep ECU internals + wave-1 Simos18 chain)
[RULES]
1. [REQ] Three target classes: (a) STOCK OEM ECU — locked bootloader (signature + seed-key + component protection), tune via OBD flash with signed files or bench exploits on specific parts; (b) OPEN EMS — rusEFI/Speeduino/HaniCore/hellen-one/MegaSquirt — fully open firmware + INI calibration; (c) GATEWAY/comfort modules — bench CAN flash (e.g. ContiTool/J533) is the deepest open path.
2. [REQ] Open EMS firmware: `rusefi` (GPL, standalone STM32), `speeduino` (GPL, Arduino-based), `MartinHani/HaniCore` (Bosch ME7 standalone, Infineon C167 — VAG 1.8T-era proof of openness), `andreika-git/hellen-one` (rusEFI hardware platform — NO OSI license listed, verify before commercial use), `Mazduino` (rusEFI/Speeduino-compatible + EFI Analytics TunerStudio).
3. [REQ] Tuning software: `RallyPat/LibreTune` (GPLv2, Rust+Tauri — the open TunerStudio-class tuner: base-map generator, 2D/3D VE/ignition/AFR tables, dashboards, AutoTune w/ AFR targets, datalogging, Lua 5.4 sandbox, WASM plugins, INI format compatible with Speeduino/rusEFI/FOME/epicEFI/MS2/MS3, MCP read-only server, AI assistant, pre-release/nightly); `ClassicMiniDIY/UltraLog` (log viewer); `AKCore/epictuner_public` (INI tuner tracker); commercial TunerStudio remains the reference for MS/rusEFI.
4. [REQ] Tuning concepts: fuel map = injector pulse-width vs RPM×load (VE% or absolute); ignition map = timing advance vs RPM×load; AFR target = stoichiometric 14.7:1 petrol / 14.5:1 diesel, open-loop vs closed-loop; VE table = volumetric efficiency; autotune = closed-loop fuel-trim learning.
5. [REQ] Wideband vs narrowband: narrowband O2 = switching around stoichiometric only (emissions feedback); wideband (5-wire LSU/UEGO) = full-range AFR measurement — REQUIRED for real tuning. `mck1117/wideband` = open wideband controller.
6. [REQ] Flasher hardware: commaai/panda + opendbc (wave-1 canonical, CAN FD + safety modes), `dspl1236/CerberusCAN` (VAG tri-CAN VCI, UDS+logger), `ecubus/EcuBus-Pro`, `roffe/gocanflasher` (Saab/GM Trionic method reference), FORScan (Ford OBD tooling), bench BDM/boot-mode clips for locked ECUs (per `tech-stack/automotive-ecu-internals.md`).
7. [REQ] VAG flashing reality: passenger ECUs (MED17/MED19/MG1/Simos/Bosch EDC) locked — no general open flasher. Open paths: (a) Simos18.x bench exploits (bri3d/VW_Flash lineage — FRF/ODX extractors, AUDI AES+LZSS decrypt, checksum fixers, TC1791_CAN_BSL), (b) J533 gateway bench-flash via ContiTool (SWaP/RSA-1024/CP/FACI), (c) Haldex Gen5 via OpenHaldex-C6, (d) standalone EMS swap.
8. [REQ] TCU/comfort-ECU tricks: TCU remaps ( DSG/Tiptronic shift maps), launch control/NLS (launch control, speed limiter delete) — these are coding/adaptation-level on many VAG cars, see automotive-tricks.md.
9. [REQ] Datalogging practice: log via OBD (python-can + DBC) or tuning tool; channels = RPM, MAP/MAF, coolant, IAT, lambda/AFR, ignition advance, injector duty, boost, knock-retard, cam phasing, throttle. Always log raw frames first.
10. [REQ] Engine sims for tuning practice: vICE (0-D cycle/BSFC), open-crank (J1939 HD diesel), DieselGen.jl (sizing), ICE_thermodynamic (MATLAB), LiU Diesel 2 (Simulink) — simulate before touching hardware.
11. [REQ] Safety: flash only with verified checksums + backup; brick risk real on locked ECUs; bench flash safer than OBD flash for gateway/TCU; never flash while driving; verify part-number compatibility before write.
12. [PROHIBIT] No pirated-crack guidance, no malware-laced tuning tools (UniCON-NECT/IE-Flash-Wizard/034-SPI quarantined), no odometer/emissions-delete instructions presented as safe — flag legal/warranty/emissions consequences explicitly.
13. [VER] ECU internals/boot chains/checksum layers → `tech-stack/automotive-ecu-internals.md`; VAG platform/engine genealogy → `tech-stack/automotive-vag.md`; wave-1 Simos18 exploit chain → bri3d/VW_Flash lineage.
