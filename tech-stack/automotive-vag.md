[TECH] automotive-vag
[OBJ] Volkswagen Group (VW/Audi/SEAT/Cupra/Škoda/Porsche/Bentley/Lamborghini) deep reference: platforms, engines, ECU families, diagnostic software ecosystem (VCDS/ODIS/OBDeleven), coding/adaptation model, SFD, immobilizer/component protection, flashing ecosystem, verified open-source repos.
[SRC] Researched 2026-11-25. Evidence files in `temp/auto-research-2026-11-25/`.

## 1. Platform architecture generations

[RULES]
1. [KNOW] PQ/PL era (pre-2012): PQ25 (Polo 6R/Ibiza 6J/A1), PQ34 (Golf 4/A3 8L), PQ35 (Golf 5/6, A3 8P, Octavia 1Z, Tiguan 5N), PQ46 (Passat 3C/B6/B7, Superb 3T), PL45/46 longitudinal (A4 B5-B7, Passat B5). Q=Quer transverse, L=Längs longitudinal. Diagnostic reality: mostly KWP2000/TP2.0 + some KWP-1281 modules; first UDS appears late PQ.
2. [KNOW] MQB (2012+ transverse): Golf 7/8, Polo 6C/AW, A3 8V/8Y, Octavia 3/4, Passat B8, Tiguan 2, Karoq/Kodiaq, Leon 3/4. Replaced PQ25/35/46. Full UDS diagnosis. MQB evo (Golf 8, 2020+) adds automotive Ethernet backbone + SFD protection.
3. [KNOW] MLB (longitudinal: A4 B8/B9, A5, A6 C7/C8, Q5, A8 D4/D5) — same electronics generation as MQB but longitudinal drivetrain; MLB evo = A4 B9/A6 C8/Q7 4M generation.
4. [KNOW] MSB (Porsche Panamera, Bentley Continental/Flying Spur), MMB (mid-engine: 718/911-ish), J1 (Taycan/e-tron GT — 800V).
5. [KNOW] MEB (2020+ EVs: ID.3/ID.4/ID.5/ID.Buzz, Q4 e-tron, Enyaq, Born): zone/Ethernet architecture, APP310/APP550 rear PMSM (up to 210kW), optional front induction motor GTX/AWD, 58/77kWh LFP/NMC, CCS2. MEB Entry + MEB+ / SSP (2026+ unified).
6. [KNOW] PPE (Premium Platform Electric: Q6 e-tron, Macan EV) — 800V, new E3 1.2 electronics architecture.
7. [KNOW] Electronics era markers: PQ = KWP/TP2.0 mostly; early MQB/MLB (2012-2019) = UDS over CAN, no SFD; MQB evo/MEB (2021+) = UDS+DoIP, SFD-protected modules; E3 1.2 (PPE/ID.7) = zone controllers, SOVD direction.

## 2. VAG engine families map (the tuner/diagnostic reality)

8. [KNOW] Petrol small: EA111 (1.2/1.4 TSI 2005-2012ish, incl. Twincharger) — chain-driven cam, chain stretch/tensioner issues. EA211 (1.0 MPI/TSI 3-cyl, 1.2/1.4/1.5 TSI) — belt-driven, integrated exhaust manifold, ACT cylinder deactivation on some, 1.5 TSI evo/ev2 Miller cycle.
9. [KNOW] Petrol performance/core: EA113 (2.0 TFSI Golf 5 GTI-era, belt+chain, cam follower HPFP wear!), EA888 Gen1/2 (1.8/2.0 TSI — timing chain tensioner failure pre-2012, oil consumption Gen2 pistons), EA888 Gen3 (2013+, integrated manifold, dual injection on some, the tuner favorite: IS20/IS38 turbo), Gen3B Miller B-cycle, Gen4 (2020+, evo4 — Golf 8 GTI/R).
10. [KNOW] Big petrol: EA824/825 V8s, EA837/839 3.0 V6 TFSI (supercharged 837 → turbo 839 hot-V, also 2.9TT RS), EA855 2.5 R5 TFSI (RS3/TT-RS — iconic 5-cyl), VR6 3.2/3.6 (EA390), W12 (Bentley/Phaeton/Touareg/A8) EA398.
11. [KNOW] Diesel: EA189 1.6/2.0 TDI common rail (Dieselgate engine family), EA288 1.6/2.0 TDI (CRLB/CRMB/DBGA/CUNA… — successor, mostly reliable but watch timing chain on some early), EA288 evo (2020+ Euro 6d), EA896/897 V6 3.0 TDI, EA381 V12 TDI exotic. Older: 1.9 TDI PD (Pumpe-Düse — legendary durable ALH/BKC/BLS but cam wear).
12. [KNOW] Engine codes: 3-letter legacy (BKD, ALH) → 4-letter since ~2012 (CAGA/CZCA…) — same base engine in multiple power states differentiated only by software/ECU (evidence: Audi SSP 626). The engine code is on the block + data sticker + ECU identification.
13. [KNOW] Transmissions: DQ200 7-speed dry DSG (mechatronic/clutch wear sensitive — early ones failed), DQ250 6-speed wet DSG (durable), DQ381/500 7-speed wet, DQ400e PHEV, DL382/501/800 longitudinal S-tronic, ZF 8HP (Audi/Porsche longitudinal), manual MQ200/250/350. DSG mechatronics = Temic units flashable/diagnosable separately (evidence: VW_Flash supports DQ250-MQB + DQ381).

## 3. ECU families — who made what

14. [KNOW] Petrol Motronic: ME7.x (C167/ST10 16-bit era, external NOR flash — Golf4/1.8T era 1999-2005) → MED9.x (TriCore TC1766 — FSI era) → MED17.x (TC1767/TC1791/TC1797 — TSI EA888 Gen1/2) → Simos (Continental/Siemens) 8/10/12/16/18 on EA888 Gen3+ / MQB era (TC1791) → newest MG1 (Bosch, TC3xx AURIX, secure boot) on evo4. Diesel: EDC15/16/17 → MD1 (AURIX).
15. [KNOW] Simos18 layout (verified evidence — simoswiki + bri3d/VW_Flash docs): TC1791S-384 (18.1, 3MB, 200MHz) or -512 (18.10, 4MB, 240MHz). Blocks: SBOOT (supplier boot 0x80000000, 112K) → CBOOT (customer boot, 144K) → ASW1/ASW2 application → CAL calibration (0xA0800000, 512K) → ASW3. Each block carries validity "security keys"/OK flags written at flash end; SBOOT validates CBOOT, CBOOT validates ASW/CAL chain.
16. [KNOW] TriCore protection model: internal flash can't be externally read without CPU permission; password-protected debug/BSL but software itself must compute/apply password at runtime = weak trust anchor. bri3d's exploit chain: SBOOT password recovery → custom bootstrap loader (TC1791_CAN_BSL) full flash R/W; or OBD: RSA-validation bypass patches injected into ASW via a CBOOT "pivot" with signature checking off (Sample Mode) — persistent trust-chain bypass enabling unsigned code/calibration.
17. [KNOW] Checksums: MED17/EDC17/Simos calibrations carry CRC32 descriptor tables per flash block — after editing maps you must recalculate & rewrite the table or the ECU rejects/no-starts. VW_Flash automates: ASW+CAL checksums, ECM2→ECM3 monitoring checksums, encrypt+compress to factory ODX payload format.
18. [KNOW] Map location: A2L-derived XDF (TunerPro), community DAMOS/OLS, or pattern-scanning binaries. ME7 (C167): map packs identified by axis/signature patterns — community tools ME7_eepromtablefinder, ME7.X checksum correctors, HaniCore (full standalone firmware for ME7!). vagpulse.com documents per-family read/write methods.
19. [KNOW] Immobilizer generations: IMMO1 (separate box, pre-2000), IMMO2 (in cluster, K-line), IMMO3 (cluster + crypto transponder), IMMO4 (2006+, component protection-era pairing), IMMO5/MQB (online-only). Key learning requires SKC/PIN (immobilizer PIN) on IMMO2/3 — read from cluster EEPROM (M95160 etc.) or online.

## 4. Component protection & SFD — the anti-theft locks

20. [KNOW] Component Protection (CP, ~2004+): modules (cluster, radio/MIB, BCM, ABS, airbag…) cryptographically bound to the car's identity; a used module from another car functions degraded (radio beeps/limited, module flags CP active DTC). Removal = online dealer process (GeKo server) where module + vehicle are re-paired. No legitimate offline bypass — gray tools exist in the wild; treat as legally sensitive.
21. [KNOW] GeKo (Gebenheim-Komponenten?): VW's online security access for immobilizer/CP/key operations — dealer account + VAS online connection.
22. [KNOW] SFD (Schutz der Fahrzeugdiagnose, verified via VW terms + Ross-Tech + OBDeleven): introduced on MQB evo/MEB (US: 2021+ ID.4, 2022+ GTI/GolfR, 2024+ Atlas; A3/S3, Q4). Write operations (coding/adaptation) on protected modules require a person-bound authenticated token from VW backend; access is logged per-person. Flow: tool requests unlock → backend validates account + vehicle + module → returns digitally signed token → gateway/module verifies and unlocks. Offline variant: vehicle generates challenge → user submits via ODIS online → returns release token.
23. [KNOW] SFD market reality: VCDS sells an SFD subscription (auto token fetch in background), OBDeleven auto-unlock on PRO/ULTIMATE plans. Manual token entry possible if obtained elsewhere. It is a legal access-control system — bypassing it has no legitimate aftermarket purpose; legitimate tools pay Volkswagen for the authorization path.
24. [KNOW] VAG diagnostic session types: ODIS Service (VIN-guided, GFF guided fault finding, test plans) vs ODIS Engineering (direct module access, raw coding/adaptation, manual flash file selection, minimal safety rails). Interfaces: VAS5054A (legacy Bluetooth), VAS6154/6154A (USB/WLAN, DoIP required on MQB evo), cheap clones/VNCI work for CAN but DoIP reliability varies. J2534 passthru usable for basic UDS.
25. [KNOW] erWin = official VW independent-operator portal (service info + ODIS Service licensing + online access fees).

## 5. The coding/adaptation mental model (VCDS-style)

26. [KNOW] Module addressing: VAG modules have hex addresses (01 engine, 02 gearbox, 03 brakes, 09 central electrics/BCM, 15 airbag, 17 cluster, 19 gateway/CAN, 5F infotainment, 42/52 doors, 46 comfort, 4B/76/77 assists…). AutoScan lists everything with part numbers/software/faults — ALWAYS save AutoScan before touching anything.
27. [KNOW] Long coding: module configuration as byte string; each bit = feature toggle (documentation via label files or community spreadsheets). Structure varies per module software version — never copy a coding string across part numbers blindly. VCDS long-coding helper annotates known bits. On UDS modules coding is a DID written with 2E.
28. [KNOW] Adaptation channels: numbered parameters (legacy) / IDE-dataset-named values (UDS/ODX — must use dropdown names in VCDS because channel numbers don't apply, evidence Ross-Tech docs). Examples: throttle adaptation, DPF values, headlight basic settings, service interval reset, battery adaptation (BEM-coded battery management on cars with IBS).
29. [KNOW] Basic settings (04 function): forces module into calibration procedures — throttle alignment (098/060 on K-line cars), steering angle sensor calibration, DPF forced regen (service regen — chain of conditions: park, handbrake, no throttle…), gearbox basic setting for DSG clutches/mechatronic after replacement.
30. [KNOW] Security access/login (legacy): 5-digit numeric logins per module (e.g. common documented ones: cluster, airbag) — community-documented; wrong attempts lock. UDS equivalent = seed/key SA.
31. [KNOW] Measuring blocks: KWP era groups 000-255 vs UDS advanced measuring values. For deep logging use proper tools (XCP-class or patched high-speed loggers) — 0x22 polling caps ~10-30 values/sec.
32. [REQ] Rule of thumb before ANY coding change: AutoScan + record original values (channel/module/value), one change at a time, verify, iterate. "There is no other way to undo" is literally in the vendor docs.

## 6. Open-source VAG repos (verified 2026-11 — clone targets)

33. [USE] `bri3d/VW_Flash` — the canonical MQB flashing toolchain: Simos18.1/6/10 full custom reflash (RSA bypass patches SC8/SCG identifiers), DQ250-MQB + DQ381-MQB DSG, Gen5 Haldex. Includes FRF extractor (any VAG FRF), ODX extractor (AUDI AES/LZSS 0xA decryption), checksum fixers, GUI. Interfaces: Tactrix/J2534, Macchina A0+BridgeLEG, SocketCAN.
34. [USE] `bri3d/Simos18_SBOOT` — SBOOT docs + seed/key bypass + Tricore boot password recovery; `bri3d/TC1791_CAN_BSL` — bench flashing bootstrap loader; `bri3d/sa2_seed_key` — SA2 seed/key algorithm from ODX bytecode; `bri3d/a2l2xdf` — A2L→TunerPro XDF conversion.
35. [USE] `Switchleg1/SimosTools` (logging/flashing app for Simos), `joeFischetti/SimosDefinitions` (tuning defs), `joeFischetti/SimosHighSpeedLogger` ($23/$2C/$3E backends), `dspl1236/simos-suite` (Simos8.5/12/18 suite — active 2026-11), `TheFlashBold/simos12-to-simos18-conversion` (full swap guide incl. bench read via Pi5+ESP32).
36. [USE] `JoeeDeveloper/OpenDiag` — NEW (2026-11): Rust cross-platform VCDS-alternative — ISO-TP, UDS, KWP2000, KW1281 5-baud, TP2.0; scan/DTC/live data/adaptation with backups+typed confirmations; read-only-first design; simulator-tested, needs real-car testers. Best modern foundation for open VAG diagnostics.
37. [USE] `ConnorHowell/vag-uds-ids` — VAG UDS CAN ID collection; `michaeldove/vagtuner` — early VAG CAN diagnostic+flash PoC; `ElDominio/CANforVAGME75` — ME7.5 CANBUS Arduino implementation.
38. [USE] `MartinHani/HaniCore` — standalone open engine-management firmware for Bosch ME7 ECUs (C167) tuned with LibreTune — active 2026-11. Proof the ME7 platform is now fully open.
39. [USE] `ronaldocordeiro/MQB_CRC_padding_byte_finder` — reverse-engineering MQB message CRCs (required to synthesize valid frames on MQB — checksum + counter live in most messages); `ronaldocordeiro/KlemmenStatusCANBusGenerator` — terminal/ignition status frames.
40. [USE] tomaskovacik's pre-CAN era repos: `VAGFISWriter`/`VAGFISReader` (cluster FIS display 3-line protocol), `VAGRadioRemote(Read)` (steering wheel remote + radio control), `vwcdavr/vwcdpic/vwcdstm32` (CD-changer emulation — the classic AUX hack).
41. [USE] `Forbes-Automotive/OpenHaldex-C6` — open Haldex AWD controller (ESP32-C6) covering VAG Gen1/2/4/5 (0CQ/0AY/VAQ) — standalone mode + lock maps. Active 2026-11.
42. [USE] commaai/opendbc VW DBCs: `vw_pq.dbc`, `vw_mqb.dbc`, `vw_mqbevo.dbc`, `vw_mlb.dbc` — production-decoded signal databases used by openpilot. Gold for reverse engineering reference; includes checksum/counter signal definitions (VAG uses CRC8 + 4-bit rolling counter on most safety-relevant messages).
43. [USE] `iotbzh/high-level-viwi-service` — Volkswagen high-level CAN signaling implementation; `autowp` community (Russian VAG deep-tech wiki+forum culture) documents KWP1281/TP2.0 internals extensively.
44. [WARN] Impersonation trap: orgs `UniCON-NECT`, `IE-Flash-Wizard`, `034-SPI` (created 2026-11-22) mimic Unitronic/Integrated Engineering/034Motorsport brands — SEO-spam pattern, probable malware lure. Never download "free" commercial-tuning cracks: warez flash tools are the #1 malware vector in the tuning scene.

## 7. Practical workflows

45. [KNOW] Diagnose a VAG: OBD port → HS-CAN 500k (pins 6/14). UDS engine at 0x7E0/0x7E8 typical; gateway 19 routes other buses (infotainment often separate bus, comfort separate). Newer (MQB evo): DoIP over Ethernet pins — need DoIP-capable interface (VAS6154 or J2534-Ethernet).
46. [KNOW] Retrofit coding pattern: install hardware → add to gateway installation list (19) → code module long coding → adaptations/basic settings → clear faults in dependent modules. Missing gateway list entries = "module not responding" ghost faults.
47. [KNOW] Battery replacement on cars with battery management: must adapt new battery (capacity/technology/serial) in BCM or energy management — skipped adaptation = over/undercharging kills new battery early.
48. [KNOW] DSG service: DSG oil+filter interval 60k km on wet units — non-negotiable; mechatronic basic setting after clutch/mechatronic work.
49. [REQ] Never bench-power VAG modules with random 12V without checking pinout; CAN-capable modules need proper termination or they log comms errors / misbehave. Use proper bench harness schematics from the community.

[COMPAT]
- Diesel deep-details pair with `automotive-ecu-internals.md`; security aspects with `automotive-security.md`.
[REFS]
- bri3d/VW_Flash docs: https://github.com/bri3d/VW_Flash/blob/master/docs/docs.md
- simoswiki: https://simoswiki.com/index.php?title=High_Level_Overview
- hardwear.io secrets of Simos18: https://hardwear.io/wp-content/uploads/2026/03/secrets-of-simos18.pdf
- vagpulse map techniques: https://vagpulse.com/engines/map-location-techniques/
- Ross-Tech VCDS: https://www.ross-tech.com/vcds/tour/sfd.php
- SFD VW terms: https://www.datenschutz.volkswagen.de/download/get-document-content/de-DE/terms-of-use-SFD
