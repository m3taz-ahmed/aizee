---
name: vag-diagnostics
description: VAG (VW/Audi/Skoda/Seat) diagnostics, coding, adaptations, long-coding/UDS-DID, gateway J533, Component Protection, key programming, flashing landscape, and hidden-feature tricks. Load for any VAG-group vehicle task.
triggers:
  - vag
  - volkswagen
  - vw
  - audi
  - skoda
  - seat
  - vcds
  - odis
  - obdeleven
  - carista
  - mqb
  - mlb
  - immo
  - component protection
  - long coding
  - adaptation
  - mib2
  - mib3
  - mib unit
  - vcds coding
personas:
  - AUTO
tech_stack:
  - automotive-vag
  - automotive-diagnostics

---

[SKILL] vag-diagnostics
[OBJ] Diagnose, code, adapt, and flash VAG-group vehicles correctly across all eras — and know where the hidden-feature "tricks" live.
[COMPAT] tech-stack/automotive-vag.md (deep platform/engine/ECU genealogy), tech-stack/automotive-tricks.md (verified trick catalog), skills/auto-domain-map.md, skills/obd-diagnostics.md, skills/ecu-tuning.md
[RULES]
1. [REQ] Identify platform first: PQ/PQ35/A5 → MLB Evo → MQB → MQBevo → MLB (Porsche) → MEB/PPE/SSP. Platform determines bus topology + diagnostic era.
2. [REQ] Diagnostic eras: pre-2004 KWP1281 K-line → 2004+ KWP2000 CAN (KW1281 for Immo) → 2015+ UDS/VWTP2.0 (MQB) → DoIP (newest). Match tool to era.
3. [REQ] VCDS function taxonomy (Ross-Tech official): 00 system overview, 01 engine, 02 transmission, 03 ABS/brakes, 08 climate, 09 central electrics, 15 airbag, 17 instruments, 19 CAN gateway, 22 AWD, 37 navigation, 42 doors, 44 steering, 46 comfort/CAN-comfort, 52 door-electrics, 53 parking-assist, 56 radio, 57 TV, 58 phone, 62 door-trunk, 65 tire-pressure. Per-module function map: 02 fault memory, 03 output tests, 07 long coding (pre-UDS), 08 measuring blocks, 09 basic settings, 10 adaptations, 11 ECU identification, 15 long coding (UDS-era variant), 19 CAN gateway coding, 22 freeze frame/all-wheels-drive, 26 local/drive-ready codes, 30 basic settings-2, 32 security access, 33 security access-2, 34 login codes, 36 adaptation-2, 37 special functions, 39 advanced measuring values, 42 assisted functions, 46 advanced measuring values-2, 48 internal settings, 50 basic settings-3, 55 advanced measuring values-3.
4. [REQ] Coding model: pre-UDS = long coding (byte/bit string in module) + adaptations (named channels, min/max/value) + basic settings (actuator tests) + measuring blocks (live grouped data). UDS-era = DID-based recode requires SecurityAccess + often online/ROD (Guided Fault Finding).
5. [REQ] Measuring blocks = grouped live values by channel number (e.g. block 032/033/034 RPM/speed/load). Adaptations = named channels with units+min/max — THE trick surface (e.g. dev-mode enable, units, comfort features).
6. [REQ] Gateway J533 (Continental, `3Q0 907 530`, RH850/F1L): central CAN router on MQB — retrofits require gateway installation + dependent-module coding + long-coding cascade. ContiTool (`perkthefox/mqb_contitool`, PolyForm-NC) = deepest open tool: bench CAN memory backup/flash, SWaP, RSA-1024 certs, CP/KSCHUTZ, FACI bootloader activation, engineering mode.
7. [REQ] Component Protection (CP/KSCHUTZ): protects modules MY2003+; GEKO→GRP migration; TSB 91-18-13TT; mechanism = signed challenge-response binding module to vehicle. Canonical doc = `dspl1236/VAG-CP-Docs` (CC0). Consequence: used modules need CP adaptation or virginizing — no general bypass.
8. [REQ] Immobilizer/key eras: Immo1 (K-line transponder) → Immo2/Immo3 (KWP1281 CAN, Mk4) → Immo4 (UDS, MQB+) → UDS-seed-key. Immo3 key adaptation = fully open via `gmenounos/kw1281test` + KKL cable (see prestia/fiddly guide). Newer = seed-key challenge-response — no public algorithm.
9. [REQ] Key/transponder tools: `kivijakola/hitager` (Hitag2/3/AES/VVDI/PCF79xx via Arduino+PCF7991, AESHitager GUI) — most complete; `tusker-tools/PCF79xx_Tool` (STM32, MIT, reported broken on latest); `bad-antics/nullsec-keyfob` (KeeLoq/Hitag2 cryptanalysis).
10. [REQ] Headunit/MIB tricks (the "tricks" goldmine): MIB2/MIB3 (Harman MHIG/MHI2/MHI2Q) hidden engineering menu via Block 10/ADP channel `5F` "Developer mode" adaptation → GEM green engineering menu → RVC high/low byte-bit coding, FEC/SWaP, widescreen patches. `Mr-MIBonk/M.I.B._More-Incredible-Bash` (GPLv2) = the MIB patching bible (ifs-root patches, FEC container, SVM fix, SD-card install). vwcoding.ru + ilovecarmods.com = procedure source.
11. [REQ] MIB↔phone integration: Android Auto via exlap channel (martoreto/aauto-vex-vag); `jilleb/mqb-pm` documents MIB2 FW compat matrix — MIB3 has NO exlap → no AA channel. CarPlay retrofit = separate (see carplay-headunits skill).
12. [REQ] VIM (Audi MMI hidden menu): login codes derived from serial via personal+alternative code generation (trick77.com); `untanux.lt` A6 C7 tricks: hidden menu via adaptation ch6=1, CAR+MENU combo, battery meter.
13. [REQ] Flashing landscape: passenger OEM ECUs (MED17/MED19/MG1/Simos/Bosch EDC) locked by bootloader signature + CP. Open paths: (a) bench-mode specific exploits (Simos18 chain — bri3d/VW_Flash lineage), (b) gateway-level J533 bench flash (ContiTool — deepest current), (c) standalone EMS swap (rusEFI/Speeduino/HaniCore). No general open VAG passenger-ECU flasher exists.
14. [REQ] Open diagnostic repos: `dspl1236/CerberusCAN` (MIT — Teensy 4.1 tri-CAN VCI, UDS+KWP2000+KW1281 all eras, lossless CP-session logger, on-device ISO-TP+TP2.0, SLCAN for SavvyCAN/python-can, EMU responder, J2012 DTC DB 1680 + VAG DIDB 4817), `JoeeDeveloper/OpenDiag` (Rust VCDS-alt, read-only-first), `baconwaifu/PyVCDS` (archived MIT-ish, plaintext Ross-Tech labels only), `uholeschak/ediabaslib` (.NET Ediabas interpreter), `NefMoto` (legacy K-line), `michaeldove/vag-diag-sim` (VWTP2.0 toy sim), `ConnorHowell/vag-uds-ids` (CAN ID data).
15. [REQ] Coding workflow: backup long-coding/adaptations first → identify module via VIN/part-number → read fault memory → targeted adaptation/channel → verify via measuring blocks → document delta. Never code blind — byte maps are module+model-year specific.
16. [PROHIBIT] No seed-key reproduction, no immobilizer bypass, no mileage fraud, no bricked-ECU procedures — defensive/knowledge framing only.
17. [VER] Deep platform/engine/ECU genealogy → `tech-stack/automotive-vag.md`; verified trick catalog → `tech-stack/automotive-tricks.md`; generic OBD/UDS → `skills/obd-diagnostics.md`.
