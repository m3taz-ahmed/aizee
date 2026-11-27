[TECH] automotive-opel
[OBJ] Opel/Vauxhall deep reference: GM-era vs PSA/Stellantis-era split, platforms, engine families, GMLAN networks, diagnostic ecosystem (OP-COM/Tech2/GDS2/SPS/TIS2Web/MDI), security access model, ECU families, verified open-source repos.
[SRC] Researched 2026-11-25. Evidence in `temp/auto-research-2026-11-25/`.

## 1. THE master key: three diagnostic eras (verified evidence — OBDMarket 2026)

[RULES]
1. [KNOW] Era 1 — classic GM (≈1987–2016): Astra F/G/H/J, Corsa B/C/D, Vectra A/B/C, Zafira A/B, Meriva A, Insignia A, Mokka A, Antara, Signum, Omega, Combo C. K-Line (older) + GMLAN early CAN. Diagnostic tool: OP-COM (dedicated hardware, fw 1.67+, Windows).
2. [KNOW] Era 2 — GM Global-A/D2xx (≈2010–2019): Astra K, Corsa E, Insignia B, Mokka X, Zafira C, Meriva B, Adam, Cascada. Dealer toolchain: GDS2 + Tech2Win + SPS2 on Windows with MDI2-class interface (GM Global Diagnostic System). OP-COM degrades to partial coverage here — not an MDI2 substitute.
3. [KNOW] Era 3 — PSA/Stellantis (2017+ acquisition, platforms landing 2019+): Corsa F, Mokka B, Crossland/Grandland X refresh, Astra L, Combo E, Zafira Life, Vivaro C, Movano C. These are PSA cars wearing Opel badges: CMP/eCMP/EMP2 platforms, PureTech/BlueHDi powertrains, PSA diagnostic environment (DiagBox/DiagBoxCloud, CAN FD) — GM-era tools do NOT apply.
4. [REQ] FIRST STEP of any Opel job: identify era by model+generation. Wrong tool assumption wastes hours. Corsa D→E boundary ≠ diagnostic boundary; Corsa F (2019) is pure PSA.

## 2. GM-era platforms and network architecture

5. [KNOW] Platforms: Gamma (Corsa/Meriva small), Delta (Astra H/J, Zafira B — GM2700/Delta I; Astra K=D2xx/Delta II), Epsilon I/II (Vectra C, Signum, Insignia A — "Global Epsilon"), Theta (Antara), Zeta-derived VXR8. opendbc carries `opel_omega_2001.dbc` + `gm_global_a_*.dbc` sets — Global A = D2xx era electronic architecture.
6. [KNOW] GMLAN (verified — GM/Opel doc evidence): HS 500 kbit/s dual-wire (powertrain, twist pair, 120Ω terminators, idle 2.5V recessive) + chassis expansion HS + powertrain expansion + MS 125k + LS single-wire 33.33 kbit/s (83.3k high-voltage programming mode). BCM = gateway HS↔LS + multiple LIN masters. Network management via virtual networks / selective wakeup.
7. [KNOW] Theft-relevant architecture note: ECM (HS) must exchange theft-deterrent data with VTD module through BCM gateway or car won't start (verified in Insignia docs) — immobilizer is distributed across modules.
8. [KNOW] SWCAN single-wire low-speed is where body/comfort modules live on many GM-era cars — cheap ELM327s CANNOT see it; need SWCAN-capable hardware (panda, proper GMLAN interfaces, `garnerm91/SWCAN` module project).
8a. [KNOW] SW-CAN electrical correction [SRC: NI single-wire CAN docs + onsemi AND8169-D — documented]: SAE J2411 normal mode 33.333 kbit/s, diagnostic/high-speed 83.333 kbit/s; **recessive ≈ 0V (receiver threshold < 1.6V), dominant ≈ 4–5V**, high-voltage wakeup near battery voltage. Any source claiming pin-1 SW-CAN idle ≈ 2.5V is wrong — that figure belongs to HS-CAN recessive. Measure the actual pin before assuming population/speed; MS-CAN (pins 3/11, ~95.2 kbit community-reported on Vectra C) may be absent from the socket.
9. [KNOW] Diagnostic addressing: GMLAN uses KWP2000-flavored/GM-enhanced services over CAN pre-UDS; Global-A era moves to UDS. Scapy's automotive layer includes GMLAN support.

## 3. Engine families (verified — Hilprecht/GM wiki evidence 2026)

10. [KNOW] Petrol GM-era small: Family 0 (1.0 X10XE/Z10XEP 3-cyl, 1.2 Z12XE/Z12XEP, 1.4 Z14XEP — TwinPort swirl-flap economy tech, Corsa/Agila/Tigra/Meriva). Family 1 "small block" (1.4/1.6: Z16XEP TwinPort 105hp, Z16XER/A16XER 115hp, turbo Z16LET/A16LET, SIDI turbos A16XHT 170hp/A16SHT 200hp). Family II "large block" (1.8 Z18XE/Z18XER, 2.0 Z20LET turbo, 2.2 Z22SE/Z22YH direct).
11. [KNOW] Performance: A20NHT/A20NFT 2.0 Turbo (Astra J/VXR, Insignia 2.0T 220-280hp), A28NER 2.8 V6 Turbo (Insignia OPC 325hp), LTG-gen GM 2.0T in later. These use GMPT/Bosch MED/Delco ECUs depending on year.
12. [KNOW] Diesel: 1.3 CDTI (Fiat Multijet SDE joint venture — Z13DTJ/DTH/A13DTE/R 75-101hp — Corsa/Meriva/Combo), 1.7 CDTI (Isuzu Circle-L — Z17DTH/A17DTJ/DTR 100-130hp), 1.9 CDTI (Fiat/GM Circle-L — Z19DT/DTH 120-150hp — Astra H/Vectra/Signum, swirl flap + DPF issues), 2.0 CDTI (A20DTH/DTR/DTC 110-195hp — Insignia/Astra J era, GM-designed "whisper diesel"), 2.0 BiTurbo CDTI A20DTR 195hp, 2.2/2.8 V6 earlier. EcoFLEX/EcoFlex variants = efficiency trims.
13. [KNOW] Post-PSA: 1.2 PureTech 3-cyl turbo petrol (EB2/EP6 PSA family — wet timing belt in oil! critical service item), 1.5 BlueHDi diesel (DV5), 1.6/2.0 BlueHDi, e-CMP EVs (Corsa-e/Mokka-e 50kWh era). PSA engines = PSA diagnostic reality.
14. [KNOW] ECU pairings typical: older petrol = Simtec (GM/Delco in-house: Simtec 56/70/71/75 — Multec on ancients), mid = GMPT E-series / Bosch ME7.x on some 1.6/1.8 (shared VAG-style ME7 architecture!), turbo/direct injection = Bosch MED17 / GMPT E39/E78/E92, diesel = Bosch EDC16/EDC17 (or Delphi DCM3.x on 1.3/1.9 Fiat-sourced, Denso on some Isuzu). Verify per engine code — never assume.
14a. [KNOW] Z22SE era split [SRC: scandoc.online report "Z22SE - GMPT E16" (alpha `TF`, system id `DELPH0400`, part 13112784) + z22se.co.uk + ATC Drivetrain + ECUFiles/Alientech GMPT-E15 listings — community strong]: **Vectra C Z22SE = GMPT-E16** (Delphi/Motorola-family, full CAN); **E15 = the earlier Z22SE applications** (Vectra B / Astra G / Zafira A / Speedster-VX220); **Z22YH 2.2 Direct = Siemens-family ECU**, a different world. Do not apply E15/Vectra-B knowledge to a Vectra C or vice versa.
14b. [REQ] Before selecting ECU data/services for a Z22SE Vectra C, verify alpha code + part number on the actual vehicle (e.g. alpha `TF`) — era association is strong evidence, not per-vehicle proof. GM E38/E67 seed-key algorithm (GMLAN algo `0x92`, documented with test vectors in hjtrbo/GM-Security-Tester) is **not verified on GMPT-E16** — treat as candidate-only, never generalize algorithms across ECUs, never brute-force. [SRC: dossier 2026-11-27 §4.4]

## 4. Diagnostic ecosystem deep dive

15. [KNOW] OP-COM (verified capabilities): Windows + dedicated USB interface; DTC read/clear across engine/AT/ABS/airbag/BCM/CIM/cluster/HVAC/infotainment; measuring blocks/live data; output/actuator tests; variant coding/configuration; service procedures + adaptations. Premium adds module replacement/setup + retrofits. Key/immobilizer work possible ONLY with the car's Security Code (Car Pass). OP-COM does NOT read a lost PIN out of thin air and is not an immo-off tool.
16. [KNOW] Car Pass / Security Code: GM-era Opels ship a 4-digit security code card; it gates immobilizer/key learning, radio/infotainment pairing, some module replacement. Recoverable from CIM/cluster/EEPROM dumps by specialists; legitimate path is dealer proof-of-ownership. Treat extraction procedures as security-sensitive.
17. [KNOW] Tech2 handheld + TIS2000: the GM dealer legacy (up to ~2010-2013); Candi module needed for CAN cars. Tech2Win = Tech2 emulator running on Windows via MDI — same coverage, needs security access keys through TIS2Web/Techline.
18. [KNOW] GDS2 (Global Diagnostic System 2): the GM-global diagnostic app for Global-A/D2xx era — vehicle ID, DTC, live data, output controls, service procedures. SPS/SPS2 (Service Programming System): ECU programming/calibration updates — online subscription via ACDelco TDS/Techline Connect. Programming needs stable PSU, correct VIN-matched calibration.
19. [KNOW] TIS2Web: GM/Opel online portal era for software delivery + SPS + service info. SPS programming keyed by VIN — calibration is vehicle-specific.
20. [KNOW] DiagBox (PSA era): the Stellantis dealer tool — diagnosis, telecoding (downloads config), pairing, programming; token/authorization online model similar in spirit to VAG's approach. CAN FD platforms.
21. [KNOW] Immobilizer generations GM-era: immo in CIM (Column Integration Module)/cluster pairing engine ECU + BCM + transponder crypto. "Immo off" = EEPROM/flash patch culture (defensive-research only territory) — legitimate path is proper pairing with security code.
22. [REQ] Programming discipline (SPS/ODIS alike): battery maintainer, exact part/hardware/software match, save coding first, wired connection, no interruption. Interrupted flash on BCM/CIM/engine ECU = tow-truck event.

## 5. Verified open-source Opel/GM repos (2026-11)

23. [USE] commaai/opendbc GM+Opel DBCs: `gm_global_a_lowspeed/high_voltage_management/chassis/object/powertrain_expansion.dbc` + `opel_omega_2001.dbc` — best free GMLAN signal references.
24. [USE] `Afterglow/arduino-gmlan` — listening/talking GMLAN on a Vectra C (2003): pioneer Arduino GMLAN RE evidence; `maxpfeif/GMLAN` + `maxpfeif/gmlan_ret` — GMLAN traffic decoding/analysis toolsets.
25. [USE] `garnerm91/SWCAN` — open single-wire CAN GMLAN hardware module (active 2026-11); `Automotive-9/GMLanDebug` — real-time GMLAN analyzer/decoder.
26. [USE] `xymetox/OpelZafiraB_CanBus_dbc` — reverse-engineered Zafira B DBC file; `isaqurbanov4/opel-astra-h-canbus` — Astra H CAN monitoring; `sergiy-nazarenko/odroid-c1plus` — Vectra C CAN integration project.
27. [USE] `PNKP237/EHU32` — ESP32 Bluetooth-audio integration for Opel/Vauxhall: steering-wheel-button CAN capture, coolant temp/battery voltage on the display — a complete worked example of reverse-engineering Opel comfort-CAN.
28. [USE] `Forbes-Automotive/OpenHaldex-C6` — covers Opel Insignia (GM Gen4 Haldex) too — the AWD controller research.
29. [USE] `roffe/gocanflasher` — Saab Trionic 5/7/8 CAN flasher with J2534: the method reference for flashing GM-family CAN ECUs (Saab shares GM/Opel architecture DNA); SharpWrap2534 + j2534-tcp for J2534 infrastructure.
30. [USE] `ludwig-v/arduino-psa-comfort-can-adapter` — PSA CAN2010/CAN2004 bridging: directly relevant for the Stellantis-era Opels.
31. [KNOW] GM platform info culture: `gm.saturn.team` mirrors full GM service information (Data Link Communications sections = authoritative GMLAN docs).

## 6. Model-specific landmines (mechanic knowledge)

32. [KNOW] Z18XE/Z18XER: oil consumption + timing chain noise; Z16XEP TwinPort: swirl flap wear; 1.4 Turbo A14NET: chain stretch + wastegate rattle + cracked pistons on tuned ones; 2.0 CDTI A20DTH: oil-pickup seal/chain driven balance module service, DPF. 1.9 CDTI: swirl flaps ingest into engine on failure — preventive delete common.
33. [KNOW] Corsa D: electric power steering column failures (EPS torque sensor); Astra H/J: CIM column-module faults (horn/controls dead), ABS pump/module corrosion, rear axle bushings; Insignia A: 2.0T timing chains, infotainment Navi600/900 quirks.
34. [KNOW] Meriva B/Zafira: rear door check straps, climate flap motors. Vivaro/Movano = Renault (era 2) — Renault diagnostic reality inside (DDT4All-compatible!).
35. [KNOW] Combo D = Fiat Doblo (Fiat Multijet engines, Delphi/Marelli electronics — different world from Combo C/E).

[COMPAT]
- GMLAN protocol details in `automotive-diagnostics.md` + `gmlan-gmw3110.md`; firmware/tuning in `automotive-ecu-internals.md`; immobilizer security in `automotive-security.md`; bus electrics in `can-physical-layer.md`; corrected 2026-11-27 per `refs/automotive-embedded-research-2026-11-27.md`.
[REFS]
- Opel CAN paper: https://can-cia.org/fileadmin/cia/documents/proceedings/2012_eisele.pdf
- GMLAN Insignia docs: https://gm.saturn.team/Opel/Insignia_Wagon__Global_Epsilon_/2009/99/60/7658/148101
- Opel diagnostic routes: https://obdmarket.eu/en/opel-diagnostics
- Opel engines: https://www.hilprecht-autoteile.com/motoren/opel-motoren/
