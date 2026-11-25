# Automotive Open-Source Ecosystem — CarPlay / Headunits / Diagnostics / Tuning — 2026-11-25

**Scope:** deep-research wave-2 (deep-research-prompt v2.0, API-read mode): map the **entire open-source repo ecosystem** around cars — mechanics, electrics, and car computers — with emphasis on **phone-projection stacks (CarPlay / Android Auto / dongles / AWDL)**, **VAG-group diagnostics + coding + flashing + immobilizers**, **ECU tuning/flashing**, **engine management firmware**, and **engine/mechanics simulation**. User framing: "tricks" = hidden features, coding, adaptations, modifications — not literal exploitation.
**Run date:** 2026-11-25 · **Personas:** DEV primary, DEVX secondary, DOC tertiary (`backend-api-expert`, `context-compressor`, `technical-writer`)
**Runtime gate:** `aizee check deep-research` — allow
**Run workspace:** `temp/auto-research-2026-11-25/` (candidate ledger ~110 rows, claims ledger C1–C21, coverage map, API-read manifest)
**Companion:** wave-1 study `study-automotive-ecu-vag-opel-2026-11-25.md` already internalized domain knowledge into `tech-stack/automotive-*.md` (7 files). This wave-2 report catalogs the **repo/tool ecosystem** and ships **5 new skills** (§7).

---

## 1. Executive summary

Wave-2 mapped ~110 candidate repos across 6 domains. Three structural findings:

1. **Phone-projection is the most open, fastest-moving automotive software domain.** Three complete open CarPlay receiver generations now exist (dongle-proxy → full-protocol reimplementation → MFi-chip Android apps), plus a near-complete Android Auto stack (aasdk + open-headunit + 248-proto dump + Pi headunit). The wireless transport (AWDL) is reverse-engineered (seemoo-lab/owl) but no consumer Linux wireless-CarPlay product exists — the dongle-firmware path (catplay Carplay2Air, ludwig-v RE) is where the frontier moved in 2026.
2. **VAG diagnostics is era-segmented and only partially open.** K-line KWP1281 (pre-2004) → CAN KWP2000/VWTP1.6 → UDS/VWTP2.0 (MQB) → DoIP. Open coverage: CerberusCAN (single Teensy 4.1 VCI spanning all eras incl. lossless CP-session logging — the best new artifact), PyVCDS (archived), kw1281test (still the Immo3 key-coding tool), ediabaslib (Ediabas interpreter). Flashing remains locked by design; the deepest open flashing artifact is `mqb_contitool` (Continental J533 gateway bench-flash over CAN incl. Component Protection internals) + `VAG-CP-Docs` (CC0 system documentation).
3. **The "tricks" layer is knowledge, not code.** Hidden features live in adaptation channels, long-coding bytes, engineering modes, and retrofit chains — documented across vwcoding.ru, ilovecarmods, Ross-Tech wiki, OBD Eleven forums. The durable open-source artifacts for tricks are: VCDS function taxonomy (official docs), MIB2 dev-mode→GEM unlock chain, Immo3 key adaptation guide, mqb-pm exlap channel matrix, and ContiTool's engineering-mode/FACI-bootloader surface.

**Safety position:** defensive/knowledge framing throughout. No theft playbooks, no immobilizer-bypass procedures, no seed-key algorithms reproduced. Three GitHub orgs impersonating tuning brands (`UniCON-NECT`, `IE-Flash-Wizard`, `034-SPI` — all created 2026-11-22) quarantined as probable malware SEO-spam.

## 2. Method

- GitHub repo search API + topic/org sweeps (opencardev, commaai, seemoo-lab, catplay-labs, dspl1236, perkthefox, Mr-MIBonk, iDoka, jaredthecoder)
- Deep README extraction via GitHub MCP `get_file_contents` / api.github.com for 20 shortlisted repos + 5 documentation sites
- Meta-index decode: `awesome-canbus` (547 lines) + `awesome-vehicle-security` (394 lines)
- No clones executed (API-read mode) → zero candidate-code execution surface; limitation: no source-level audit beyond READMEs
- Ledgers: `temp/auto-research-2026-11-25/` — candidate-ledger (~110 rows), claims-ledger (C1–C21), coverage-map, queries, errors

## 3. Domain A — Phone projection (CarPlay / Android Auto / dongles / AWDL)

### 3.1 CarPlay protocol stack (what the repos actually implement)

iPhone→head-unit CarPlay = HomeKit pairing → iAP2 (accessory protocol over USB or Wi-Fi) → AirPlay audio/video (H.264) → optional CarPlay video channel (H.265 for Ultra). Wireless CarPlay tunnels the USB session over AWDL. Every open repo maps to one layer:

| Layer | Open artifacts |
|---|---|
| Full receiver (all layers) | `catplay` (Rust, from-scratch iAP2+HomeKit+MFi — the reference impl), `LIVI` (Rust+Slint, GPLv3, 1212★, wired+wireless, hw decode, ships LIVI OS + Link dongle), `xcertplay`/`DiPlay` (Android, reuse Carlinkit-recovered MFi accessory identity), `OpenXPlay-Relay` (AGPLv3 rust crates carplay-iap2/carplay-airplay) |
| Dongle-proxy client | `FastCarPlay` (GPLv3 C++, 169★ — Carlinkit/Autobox client, Pi Zero 2W capable), `react-carplay` (MIT, 898★ — Electron UI for Carlinkit cpc200, canbus camera trigger), `carplay-client`/`pycarplay` (AutoBox lineage, original Tesla-HU HTML client) |
| Dongle firmware | `catplay` Carplay2Air (open firmware, Ingonic X1600EN successor to i.MX6UL Carlinkit Mini Ultra), `ludwig-v/wireless-carplay-dongle-reverse-engineering` (full RE doc: HW map, fw structure, root exploits, U2W/U2AW/U2AC segmentation), `Henkru/cplay2air-wifi-passphrase-patch` |
| Transport research | `seemoo-lab/owl` (GPLv3 AWDL for Linux/macOS — AirDrop RE, archived), `opendrop` (9964★ AirDrop impl + keychain extractor), `owly`, `proxawdl` (TCP-over-AWDL) |

### 3.2 Android Auto stack

| Artifact | Role | Notes |
|---|---|---|
| `opencardev/aasdk` + `crankshaft` | protocol lib + turnkey RPi→AA headunit (GPLv3, 2703★) | the canonical open AA receiver |
| `andreknieriem/open-headunit` | Android device→AA receiver (AGPLv3, 3469★) | mikereidis lineage revival; WiFi Direct/hotspot/server modes |
| `f1xpl/aasdk` + `openauto` | original AA emulator (GPLv3, 314+2948★) | 2024-12, superseded by opencardev but still referenced |
| `mrmees/open-android-auto` | 248 `.proto` files, AA v16.1–17.3 RE'd from APK + Sony XAV firmware | best protocol reference |
| `mossyhub/openautolink` | AA+CarPlay for GM EV AAOS head units | newest (2026-11), cluster/HUD nav, EV range |
| `mretallack/AndroidAuto` | phone→HU direction | WIP, USB power-cut issue |

### 3.3 Brand-specific CarPlay/AA enablers (the "tricks" frontier)

- **BYD DiLink**: `DiPlay` (CarPlay, xcertplay-based, GPLv3, v0.2.22) + `DiAuto` (AGPLv3) + `CarLink` (unified auto-detect) — wired+wireless on Android 7+, HUD nav on verified firmware. Honestly documents bundled Carlinkit-recovered accessory identity (extractable → not Apple-certified).
- **BMW NBT** (QNX 6.5 x86): `nbt-android-auto` — wired AA+CarPlay, iDrive+cluster nav.
**Open-HMG/hmgapi-wireless-cp-aa** — wireless CP+AA for HMG-API Gen5W head units.
- **Autochips AC8257** Android HUs: `riazosama/headunit-carplay` enablement.
- **Embedded HU**: `mbt28/lehu` (GPLv3 Rust, Allwinner F1C200s 64MB) — existence proof that CP+AA fits in tiny hardware.

**Key insight:** the dongle-hacking era (patch Carlinkit firmware) is being replaced by direct-receiver apps that reuse recovered MFi identities or full protocol stacks — DiPlay/xcertplay prove a $0 software CarPlay works on BYD without dongle hardware.

## 4. Domain B — VAG diagnostics / coding / flashing / keys

### 4.1 Diagnostic protocol eras (verified)

```
pre-2004  K-line KWP1281 (12V KKL cable)     → kw1281test, CerberusCAN head3, NefMoto
2004-2015 CAN KWP2000 / VWTP 1.6            → PyVCDS, CerberusCAN, vag-diag-sim
2015+     UDS / VWTP 2.0 (MQB)               → OpenDiag (wave-1), CerberusCAN TP2.0
newest    DoIP (Ethernet)                    → automotive_diag, uds libs
```

### 4.2 Verified repo catalog

| Repo | License | What it is | Verdict |
|---|---|---|---|
| `dspl1236/CerberusCAN` | MIT | Teensy 4.0/4.1 tri-CAN VAG VCI: head1 active UDS (OBD 6/14 @500k), head2 lossless listen-only logger (256KB ring, captured live ODIS CP session), head3 K-line KWP2000/KW1281; on-device ISO-TP + VW TP2.0; SLCAN mode for SavvyCAN/python-can; EMU responder; CerberusConsole GUI + SAE J2012 DTC DB (1680) + VAG DIDB (4817 fault locs); hardware-validated on A6 C7 | **best new VAG VCI artifact** |
| `baconwaifu/PyVCDS` | MIT-ish | VCDS reimplementation: VWTP2.0+KWP2000, measuring blocks, plaintext Ross-Tech labels only (never CLB) | ARCHIVED — reference, not maintained |
| `JoeeDeveloper/OpenDiag` (wave-1) | ? | Rust VCDS-alt: ISO-TP/UDS/KWP2000/KW1281/TP2.0, read-only-first | best open foundation going forward |
| `michaeldove/vag-diag-sim` | MIT | VWTP2.0 ECU simulator (2017, 12★) | toy — useful only as PyVCDS test fixture |
| `uholeschak/ediabaslib` | ? | .NET BMW+VAG Ediabas job interpreter — the INPA/NCS/Tool32 engine | niche but unique |
| `NefMoto/NefMotoOpenSource` | mixed | classic VAG K-line/KWP1281 toolset (pre-CAN Golf/Bora era) | legacy coverage |
| `gmenounos/kw1281test` | ? | KW1281 K-line test tool via KKL | **still required for Mk4 Immo3 key adaptation** |
| `ConnorHowell/vag-uds-ids` | ? | VAG UDS CAN ID collection | reference data |
| `dspl1236/VAG-CP-Docs` | CC0 | Component Protection system doc: FAZIT/GEKO→GRP migration, TSB 91-18-13TT, affected modules MY2003+, legal basis | canonical CP reference |
| `perkthefox/mqb_contitool` | PolyForm-NC | ContiTool: Continental J533 `3Q0 907 530` gateway tool — bench CAN memory backup/flash, SWaP, RSA-1024 certs, CP/KSCHUTZ, FACI bootloader activation, engineering mode (RH850/F1L, Qt6) | **deepest open flashing artifact** |
| `jilleb/mqb-pm` | ? | VAG-group perf monitor via Android Auto exlap channel | documents MIB2 FW compat matrix; MIB3 lacks exlap |
| `Mr-MIBonk/M.I.B._More-Incredible-Bash` | GPLv2 | MIB/GEM patching for Harman MHIG/MHI2/MHI2Q: ifs-root patches, FEC container, SVM fix, widescreen patches, SD-card install | the MIB hacking bible |
| `MartinHani/HaniCore` | ? | standalone fw for Bosch ME7 (C167) — VAG 1.8T-era ECU fully open | proof ME7 platform is open |
| `michaeldove/vagtuner`, `ElDominio/CANforVAGME75` | ? | VAG CAN flashing PoCs (2016-era) | stale — superseded by bench-tool approach |
| `ronaldocordeiro/MQB_CRC_padding_byte_finder` | ? | MQB message CRC padding research | CAN-injection enabler research |

### 4.3 The "tricks" layer (hidden features / coding / adaptations)

Verified trick sources (docs, not repos):
- **vwcoding.ru** — MQB headunit developer-mode unlock via Block 10/ADP channel `5F` "Developer mode" adaptation → GEM engineering menu; VIM via `nhtsa_properties` adaptations; MirrorLink; CP/AA limit removal.
- **ilovecarmods.com/vw/discover-media-mib2** — MIB2 coding mods with procedure IDs: dev-mode→GEM, FEC/SWaP, GEM green engineering menu, byte/bit coding tables, RVC high/low byte-bit coding.
- **ross-tech.com VCDS tour + wiki.ross-tech.com** — canonical function taxonomy: fault memory (02), measuring blocks (08), adaptations (10), basic settings (09), long coding (07, pre-UDS) / UDS DID recode (MQB+, requires online/ROD), output tests (03), security access, login codes (VIM challenge).
- **untanux.lt** — A6 C7 tricks: hidden menu via adaptation ch6=1, CAR+MENU combo, battery meter, VIM.
- **trick77.com** — Audi MMI VIM serial→personal+alternative login code generation.
- **prestia/fiddly mk4-vw-key-coding.md** — Mk4 VW Immo3 key adaptation via kw1281test+KKL (fully open-source key procedure).

### 4.4 Keys / transponders / immobilizer

| Repo | What | Notes |
|---|---|---|
| `kivijakola/hitager` | Hitag2/2+/Ext, Hitag3, Hitag AES, Hitag Pro, VVDI Super Chip, BMW PCF7944/45/53 read/write via Arduino+PCF7991; AESHitager GUI | most complete open transponder tool (90★) |
| `tusker-tools/PCF79xx_Tool` | STM32 BluePill programmer for PCF79xx (BMW CAS3 5WK49125/26A0700); MIT | reported broken on latest rev; predecessor `w01230/PCF7953` suggested |
| `bad-antics/nullsec-keyfob` | KeeLoq rolling-code + Hitag2 challenge-response cryptanalysis | research-grade |
| `jglim/UnlockECU` | seed-key ECU unlock research | defensive/reference |

## 5. Domain C — ECU tuning / flashing / engine management

### 5.1 Open ECU ecosystem

| Layer | Repos |
|---|---|
| Standalone EMS firmware | `rusefi/rusefi` (GPL), `speeduino/speeduino` (GPL, Arduino), `MartinHani/HaniCore` (ME7/C167), `andreika-git/hellen-one` (rusEFI hw platform — **no OSI license listed**), `Mazduino/Mazduino` |
| Tuning software | **`RallyPat/LibreTune`** (GPLv2, Rust+Tauri — the open TunerStudio alternative: base-map generator, 2D/3D VE/ignition/AFR tables, dashboards, AutoTune w/ AFR targets, datalogging, Lua 5.4 sandbox, WASM plugins, INI format compatible with Speeduino/rusEFI/FOME/epicEFI/MS2/MS3, MCP read-only server, AI assistant, pre-release/nightly), `ClassicMiniDIY/UltraLog` (log viewer), `AKCore/epictuner_public` (INI-compatible tuner tracker) |
| Flasher hardware | commaai `panda` + `opendbc` (wave-1 canonical), CerberusCAN (VAG-specific), `gciucco/Forscan`-adjacent Ford tooling (wave-1), `roffe/gocanflasher` (Saab/GM Trionic), `ecubus/EcuBus-Pro` |
| TCU/locked ECUs | `Forbes-Automotive/OpenHaldex-C6` (open Haldex controller, VAG+Opel), `PNKP237/EHU32` (Opel ESP32 comfort-CAN) |

### 5.2 Locked-bootloader reality

Passenger-car OEM ECUs (MED17/MED19/MG1/Simos/Bosch EDC) stay locked: bootloader signatures + Component Protection + seed-key. Open paths that exist: bench-mode exploits on specific parts (Simos18 chain — wave-1), gateway-level flashing (ContiTool/J533 — deepest current), and full standalone-EMS replacement (rusEFI/Speeduino/HaniCore). **No general open VAG passenger-ECU flasher exists — by design, and the SEO-spam orgs impersonating Unitronic/IE/034 prove the demand.**

## 6. Domain D — Engines / mechanics / simulation

Wrench-level mechanics is not an OSS domain (no repos); the open coverage sits at the simulation + engine-management layer:

| Repo | What | License |
|---|---|---|
| `pablomarcel/vICE` | 0-D ICE cycle sim: slider-crank, Wiebe burn, P-V diagram, BSFC sweeps, Cantera option, turbo mean-value | MIT |
| `Open-Heavy-Machinery/open-crank` | simulated HD diesel answering J1939 over CAN; plant+ECU peer; SIL on vcan | Apache-2.0 |
| `DimitriosVogiatzis/ICE_thermodynamic` | DI diesel thermodynamic cycle (MATLAB) | ? |
| `sandialabs/DieselGen.jl` | FASTSim-derived diesel perf/sizing model, differentiable | MIT |
| LiU Diesel 2 (vehicular.isy.liu.se) | validated turbocharged diesel w/ wastegate+throttle (Simulink, LGPL) | LGPL |
| `jumpstarter-dev/jumpstarter` | HIL framework: UDS/DoIP/CAN | ? |

Engine-type coverage (from wave-1 `tech-stack/automotive-core.md`): all ICE architectures (inline/V/VR/boxer/rotary/Atkinson), diesel common-rail, all EV motor types (PMSM/induction/EESM/SRM/axial-flux), hybrid P0–P4, HV battery/BMS/charging — already internalized.

## 7. Skills written (durable internalization — wave-2)

| Skill | Covers |
|---|---|
| `skills/auto-domain-map.md` | master index: protocol families, tool landscape, resource sites, era-decision tree |
| `skills/auto-mechanics-engines.md` | engine architectures/types, fuel systems, hybrids/EV motors, engine sims, tuning concepts |
| `skills/obd-diagnostics.md` | OBD-II modes/PIDs, UDS/ISO-TP/TP2.0/DoIP/KWP2000/KW1281/J1850, adapters, python-can/cantools/opendbc/caringcaribou/SavvyCAN/cabana/scapy workflow, DTC practice |
| `skills/vag-diagnostics.md` | VAG platform/era map, VCDS/ODIS/OBDeleven/Carista, all VCDS functions, coding/adaptation/long-coding/UDS-DID model, gateway J533, Component Protection, key programming, flashing landscape, tricks sources |
| `skills/carplay-headunits.md` | CarPlay stack layers, all open receivers (3 generations), AA stack, dongle RE/firmware, AWDL, brand enablers, MFi-identity reality |
| `skills/ecu-tuning.md` | open EMS (rusEFI/Speeduino/HaniCore/hellen-one), LibreTune/TunerStudio INI ecosystem, base-map/VE/AFR/autotune concepts, flasher hardware, locked-bootloader reality, engine sims |

Loading guidance: `auto-domain-map` first for any automotive task → then the specialization. Cross-refs declared in each `[COMPAT]` block. Wave-1 `tech-stack/automotive-*.md` files remain the deep domain reference; these skills are the operational/repo layer.

## 8. Highest-value repos (future-work shortlist)

1. **`dspl1236/CerberusCAN`** — newest + most capable open VAG VCI (MIT, hardware-validated incl. live ODIS CP-session capture).
2. **`catplay-labs/catplay`** — only from-scratch full CarPlay protocol implementation + open Carplay2Air firmware.
3. **`perkthefox/mqb_contitool`** — deepest open VAG flashing artifact (J533 gateway, CP/KSCHUTZ/FACI).
4. **`dspl1236/VAG-CP-Docs`** — canonical Component Protection documentation (CC0).
5. **`RallyPat/LibreTune`** — the open TunerStudio-class tuner (pre-release; watch it).
6. **`JoeeDeveloper/OpenDiag`** (wave-1) + **`baconwaifu/PyVCDS`** — open VAG diagnostic app lineage.
7. **`kivijakola/hitager`** — most complete open transponder/key tool.
8. **`f-io/LIVI`** — most complete open CarPlay+AA headunit product (GPLv3, 1212★).
9. **`mrmees/open-android-auto`** — 248-proto AA reference.
10. **`seemoo-lab/owl`** — AWDL implementation (archived but canonical).

## 9. Gaps / future passes

- Passenger-car OEM ECU bootloader exploits beyond Simos18/J533 — locked by design; monitor bri3d/VW_Flash lineage.
- DoIP practical tooling for newest VAG (protocol libs exist, no VAG-specific DoIP scanner found).
- MIB3 coding (post-2020 Harman units) — fewer public tricks than MIB2; exlap channel absent.
- AWDL→wireless-CarPlay on Linux — research exists (owl), no product.
- Wrench-level mechanics — not an OSS domain; covered via engine-sim + tuning layers.
- Non-VAG brand depth (BMW/Mercedes/Ford/Toyota diagnostics) — wave-1 flagged same gap; CarPlay/AA side is brand-agnostic.

## 10. Evidence quality

Repo claims verified at README/metadata level via GitHub API (20 deep-reads). Trick/coding claims verified against Ross-Tech official docs + vwcoding.ru + ilovecarmods + forum guides. Claims ledger C1–C21 with CONFIRMED/STRONG/WEAK grading in `temp/auto-research-2026-11-25/claims-ledger.md`. Known limitation: no source-level audit; star counts point-in-time.
