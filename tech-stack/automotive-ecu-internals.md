[TECH] automotive-ecu-internals
[OBJ] ECU hardware/firmware internals: MCU architectures, flash layouts, bootloaders, checksums, bench vs OBD access, tuning/remapping ecosystem, open-source standalone engine management. For firmware RE and tuning work.
[SRC] Researched 2026-11-25. Core evidence: bri3d/VW_Flash docs, simoswiki, vagpulse, hardwear.io.

## 1. MCU architectures found in ECUs

[RULES]
1. [KNOW] Infineon TriCore TC17xx/TC2xx/TC3xx (AURIX) — the dominant modern automotive MCU: 32-bit RISC-ish hybrid 16/32-bit instructions, no MMU, flat memory, hardware task contexts with per-task permissions, memory-mapped program flash (PMU units) + DFlash EEPROM-emulation, peripherals incl. GTM (timer co-processor that does injector/ignition timing). TC1766/67/91/93/97 in MED/EDC/Simos era; TC2xx/3xx in MG1/MD1 with HSM (hardware security module — real secure boot).
2. [KNOW] C167/ST10 (Infineon/Siemens/STM) — 16-bit segmented (DPP-paged) architecture with EXTERNAL parallel NOR flash (AMD/Spansion 29Fxxx): ME7.x petrol, EDC15 diesel era. External flash = trivially removable/readable with a clip or programmer — why ME7 is the most-open ECU family ever.
3. [KNOW] NXP/Freescale MPC5xxx/S32K (PowerPC e200 cores) — Ford/GM/Chrysler leaning; RH850 Renesas — Asian OEMs; TI TMS570 — safety MCUs; ARM Cortex-M in newer body/zone controllers. XC2000/XC27x in body modules.
4. [KNOW] EEPROM practices: serial SPI/I2C EEPROMs (M95160/95320, 25xxx/24xxx series) hold immobilizer data, odometer, adaptation, keys on many modules — readable with $2 CH341A programmer + SOIC clip, but SOLDER-FREE CLIPS FAIL CONSTANTLY under vibration/temp — bench work means proper desoldering or quality clips.
5. [KNOW] Flash protection reality: password-in-flash protection is weak when software itself must unlock (TC1xxx model evidence). HSM in TC3xx + signed firmware + secure boot is the real wall — modern tuning moved to boot-time exploits, bench unlocking, or piggyback boxes.

## 2. Flash memory layout & boot chain

6. [KNOW] Canonical layout (Simos18 verified, but the pattern generalizes): SBOOT supplier bootloader (immutable, validates next stage) → CBOOT customer/OEM bootloader (handles reprogramming protocol) → ASW application software (the real engine logic, often split ASW1/2/3 across flash units) → CAL calibration (maps/curves — the only part tuners actually want to change).
7. [KNOW] Validity model: each block gets CRC32/MD5-summed; validity flags ("security keys"/OK flags) written AFTER successful verification. Boot halts or falls back when validation fails — this is why checksums must be corrected after ANY binary edit, and why interrupted flashes brick ECUs (though CBOOT often survives → recovery possible).
8. [KNOW] ECM2→ECM3 monitoring checksums: modern Bosch torque-monitoring layer cross-checks calibration integrity separately — VW_Flash fixes these too. Missing this = limp mode/no-start after "successful" flash.
9. [KNOW] Read/write paths ranked by power: (a) OBD session reprogramming (UDS 0x34/36/37 through seed/key) — manufacturer-intended; (b) bench boot mode (BSL — bootstrap loader via UART/CAN with boot pins strapped — C167 BSL over K-line, TriCore CAN/UART BSL) — deep access, immo-independent; (c) BDM/JTAG/debug — full control, needs opening + often password; (d) EEPROM direct — surgical small-data edits.
10. [KNOW] ME7 boot mode reality (evidence vagpulse): dev session 10 86 + read-memory reaches EEPROM/RAM but flash is immo-gated (needs 10 85/matched car/SKC) — bench BSL (ground one boot pin) is the universal immo-immune path. MED9.1: flash read must NOT use session 0x86 (drops into BSL, needs power cycle); recovery = BDM/BSL.

## 3. Tuning ecosystem — tools of the trade

11. [KNOW] Commercial centers of gravity: WinOLS (EVC — the professional binary map-editing environment, DAMOS/A2L-driven), ECM Titanium (Alientech — map-database-driven), TunerPro RT (free-ish, XDF definition files), HP Tuners (GM/Ford/FCA leaning, MPVI), EFILive (GM diesel/Duramax + LS), Cobb Accessport (consumer locked devices), KTuner/Hondata (Honda), EcuTek (Asian + some VAG), cmdflash/Autotuner/bFlash/KESS/K-TAG (Alientech/Dimsport "slave/master" reading tools ecosystem — master tools decrypt, slave tools are locked to a master dealer).
12. [KNOW] Definition ecosystem: XDF (TunerPro), OLS/DAMOS (A2L-derived professional descriptions), community A2L conversions (a2l2xdf). Without a correct map definition you are hex-editing blind: maps found by pattern recognition (axes shapes, monotonic curves) — error-prone.
13. [KNOW] Stage nomenclature folklore: Stage 1 = software only; Stage 2 = downpipe/intake/exhaust bolt-ons; Stage 3 = bigger turbo/hardware. Marketing terms, not engineering units — torque models and component limits are the real currency.
14. [KNOW] What actually changes in a remap: boost target + wastegate duty, torque model limits, lambda/AFR targets, ignition timing, load/rpm limiters, throttle maps, torque monitoring thresholds, sometimes gearbox torque limits (must flash TCU too on DSG — DQ250/DQ381 supported in open tools).
15. [KNOW] Risks: torque-model inconsistency → clutch slip/limp; excessive timing/boost on stock internals → piston/rod death; emissions equipment removal (DPF/EGR/SCR deletes) = illegal on-road in EU/US + inspection failure.
16. [KNOW] Logging is the verification loop: high-speed logging needs XCP-class access or patched firmware loggers (evidence: SimosHighSpeedLogger backends — $23 ReadMemoryByAddress / $2C dynamic identifiers / proprietary $3E patch — all require ASW patches).

## 4. Open-source engine management — the fully-open alternative

17. [USE] rusEFI (`rusefi/rusefi`) — open standalone ECU firmware (C++, STM32F4/F7/H7 boards: Hellen, Proteus, microRusEFI): full engine control — injection, ignition, knock, boost, VVT, CANwide integration, TS (TunerStudio) calibration. The most complete open-source EMS codebase to LEARN engine control theory from real code.
18. [USE] Speeduino (`speeduino/speeduino`) — Arduino Mega 2560-based DIY EMS — simpler, huge community, great teaching codebase; paired with TunerStudio.
19. [USE] `MartinHani/HaniCore` — standalone replacement firmware for Bosch ME7 hardware (C167) — runs OEM hardware with fully open firmware, tuned via LibreTune. A milestone: OEM hardware + open firmware.
20. [USE] FreeEMS (stalled but educational), `emstudio` tuning apps, LibreTuning/LibreTune ecosystem.
21. [USE] EV conversions: openinverter (`jsphuebner` ecosystem — stm32-sine inverter firmware, parameter DB, CAN tool) + `damienmaguire/Stm32-vcu` — open vehicle control unit managing OEM EV parts (leaf/tesla/i3 drive units) — the open answer to EV powertrain hacking. Zombieverter (VCU) is the community-name project to know.
22. [USE] `DNiev/ecu-lab` — engine-management & tuning SIMULATOR (dyno pulls, calibration-table editing with explanations) — learn tuning consequences without a car. New 2026, active.
23. [KNOW] CAN bus in standalone world: aftermarket ECUs publish their state over documented CAN — integration with OEM dashes/ABS is a DBC-reversing exercise (the retro-fit discipline).

## 5. Reverse-engineering workflow for an unknown ECU

24. [REQ] Step 1: identify MCU (read the markings — SAK-TC1791S-384 decodes fully in public Infineon datasheets; flash size/layout from the datasheet, not guesses).
25. [REQ] Step 2: enumerate diagnostic attack surface first — non-invasive: UDS service scan (gallia `gallia scan uds services` style), DID enumeration, security access analysis, session matrix. Document everything before touching memory.
26. [REQ] Step 3: get the firmware read-only first (OBD read if available, else bench). Verify image against multiple reads (checksum across reads; tools sometimes read past chip end — simoswiki warns).
27. [REQ] Step 4: static analysis in Ghidra with the right processor module (tricore ghidra plugins exist — essential for TC17xx; C167 for ME7). Map peripheral addresses from the datasheet. Identify: diag handlers, checksum routines, security access compare, CAN message tables.
28. [REQ] Step 5: understand the boot/trust chain before modifying anything — which block validates what, where validity flags live, what the recovery path is. No blind writes: one valid recovery path must ALWAYS exist.
29. [REQ] Step 6: patch minimally, correct all checksum layers, flash back, verify boot + all functions, log behaviors. Keep the original dump immutable and version everything.
30. [PROHIBIT] Never flash a file whose provenance you don't know (warez "staged" files) — mismatched calibrations brick ECUs or worse, and cracked tuning files are a malware vector (verified: impersonation orgs pattern found 2026-11).
31. [USE] RE tooling for firmware: Ghidra (+TricoreLoader / C167 plugins), rizin/radare2, binwalk for containers; REA firmware tools for region inspection when available. VAG FRF/ODX containers: extract with bri3d's `frf` + `extractodx.py` (AUDI AES 0xA / LZSS decryption) before analysis.

[COMPAT]
- VAG specifics in `automotive-vag.md` (Simos/ME7/MED/EDC maps); Opel in `automotive-opel.md`; legal/safety framing in `automotive-security.md`.
[REFS]
- Simos18 internals: https://github.com/bri3d/VW_Flash/blob/master/docs/docs.md
- hardwear.io secrets-of-simos18.pdf — full exploit chain analysis
- rusEFI: https://github.com/rusefi/rusefi
- Speeduino: https://github.com/speeduino/speeduino
