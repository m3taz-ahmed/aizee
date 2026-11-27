---
name: gm-opel-lord
description: Lord skill for Opel/Vauxhall and GM vehicle specifics — generation eras (K-line → GMLAN → Global A/B → PSA), Vectra C/Astra H/Zafira B bus topology (HS/MS/SW-CAN on pins 6/14, 3/11, 1), ECM families (Simtec, GMPT-E15/E16, Siemens, Bosch EDC16/ME7.6 by engine), common addressing, OP-COM/Tech2/GDS as UX reference not data, Car Pass PIN defensive boundary. Use when the target vehicle is an Opel/Vauxhall/GM product.
triggers:
  - opel
  - vauxhall
  - vectra
  - astra
  - zafira
  - insignia
  - corsa
  - gmpt
  - simtec
  - op-com
  - opcom
  - tech2
  - gmlan opel
  - z22se
  - z22yh
  - car pass
  - اوبل
  - فيكترا
  - أسترا
  - كمبيوتر العربية اوبل
  - فحص اوبل
personas:
  - AUTO
tech_stack:
  - automotive-opel
  - gmlan-gmw3110
  - can-physical-layer
lord: true
---

[SKILL] gm-opel-lord
[OBJ] Navigate Opel/GM reality correctly: identify era and ECU family before touching anything, know which bus lives on which pin, treat tool documentation as UX reference only, keep the defensive boundary around immobilizer/Car Pass absolute.
[COMPAT] tech-stack/automotive-opel.md (deep brand reference — corrected 2026-11-27), tech-stack/gmlan-gmw3110.md (services), skills/diagnostic-protocols-lord/SKILL.md (protocol dialects), skills/can-bus-lord/SKILL.md (bus electrics), tech-stack/automotive-security.md (security boundaries)
[SRC] Researched 2026-11-27. Evidence: scandoc.online GMPT-E16 report, z22se.co.uk, ATC Drivetrain, ECUFiles/Alientech GMPT-E15 listings, opendbc GM/Opel DBCs, hjtrbo/GM-Security-Tester, dossier §4.4.

[RULES]
1. [REQ] Era identification is step zero on any Opel job: classic GM (K-line/early GMLAN, OP-COM coverage) → Global-A/D2xx (GDS2/MDI2 dealer world, OP-COM partial) → PSA/Stellantis (2019+ platforms: DiagBox reality — GM tools do NOT apply). Wrong-era tooling wastes hours and misleads diagnosis. [documented in automotive-opel.md]
2. [KNOW] Vectra C / Astra H / Zafira B socket networks: HS-CAN 500k on pins 6/14; MS-CAN community-reported ~95.2 kbit on pins 3/11 — MAY BE ABSENT from the socket, verify population; SW-CAN/LS-GMLAN single-wire 33.3k on pin 1 (recessive ≈0V — NOT 2.5V); legacy K-line possible on pin 7. Pin 16 permanent +12V. [community — measure per vehicle]
3. [KNOW] **Z22SE era split [community strong]**: Vectra C Z22SE = GMPT-E16 (Delphi/Motorola-family, full CAN — scandoc report alpha `TF`, system `DELPH0400`, part 13112784); E15 = earlier Z22SE applications (Vectra B/Astra G/Zafira A/Speedster); Z22YH 2.2 Direct = Siemens-family. Never carry knowledge across these boundaries.
4. [REQ] Per-vehicle verification: before choosing ECU data/services, verify alpha code + part number on the actual car. Era evidence is strong association, not proof — engine swaps and regional variants exist.
5. [KNOW] ECM family map (verify per engine code): Simtec 56/70/71/75 older petrol; GMPT E-series mid; Bosch ME7.x/MED17 on some engines; Bosch EDC16/EDC17 diesels; Delphi DCM on Fiat-sourced diesels. ECU family determines protocol dialect + service support. [community — automotive-opel.md §3]
6. [KNOW] KWP2000-on-CAN is the engine-ECU diagnostic dialect for Vectra-C-era GMPT units; body modules speak GMLAN-flavored services on their buses; exact supported services per ECU variant = provenance-tagged data, never assumption.
7. [KNOW] GMLAN addressing on these cars: physical request IDs community-observed in `0x241–0x25F` with responses `+0x400`; functional `0x101`. Discover by passive listening — never guess-transmit. [community]
8. [REQ] E38/E67 seed-key algorithm (`0x92`): documented with vectors in hjtrbo/GM-Security-Tester — **NOT verified on GMPT-E16**. Treat as candidate-only reference; algorithms are per-ECU; never generalize; never automate seed/key attempts (lockout risk); stop on NRC 0x35/36/37.
9. [KNOW] OP-COM/Tech2/GDS documentation = UX/capability reference (what functions exist: measuring blocks, output tests, variant coding) — NOT wire-level truth. Do not infer protocol bytes from tool screenshots/manuals. [community]
10. [REQ] Car Pass / 4-digit security code boundary: legitimate paths only — owner's card, dealer proof-of-ownership, licensed locksmith. No EEPROM extraction procedures, no immo-off, no key cloning guidance. Refuse and redirect. [policy — absolute]
11. [KNOW] Output tests on GMLAN Opel modules = DeviceControl `0xAE` with ECU-specific CPIDs — require per-variant verified data, vehicle stationary confirmation, explicit user confirmation, timeout, guaranteed return-control. See diagnostic-safety-lord.
12. [USE] Best free signal references: commaai/opendbc `gm_global_a_*` + `opel_omega_2001` (MIT); `xymetox/OpelZafiraB_CanBus_dbc` (no license — knowledge-only); `PNKP237/EHU32` (MIT) as a complete Opel comfort-CAN RE worked example; `Afterglow/arduino-gmlan` (no license, 2012 — historical pioneer evidence).
13. [KNOW] BCM is the HS↔LS gateway on these platforms; theft-deterrent data flows ECM↔VTD through BCM — immobilizer is distributed, which is exactly why immo tampering is both unsafe and out of scope.
14. [KNOW] Model-specific diagnostic landmines exist (Astra H CIM faults, Corsa D EPS column, 1.9 CDTI swirl flaps) — mechanical context in `tech-stack/automotive-opel.md` §6; use it to interpret DTCs in context rather than parts-darting.
15. [PROHIBIT] Never: apply Vectra B/E15 data to Vectra C; assume MS-CAN exists because pins exist in a diagram; treat OP-COM menu names as protocol identifiers; suggest secure-gateway or immobilizer bypass of any kind; generalize the E38 algorithm beyond documented ECUs.
16. [REQ] When evidence is missing for the exact variant, say "غير موثق لهذه الوحدة" (undocumented for this unit) and propose the verification path: passive capture, alpha/part check, known-good tool comparison — never fill gaps with plausible guesses.
