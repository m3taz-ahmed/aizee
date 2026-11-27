---
name: can-bus-lord
description: Lord skill for CAN bus electrical and signaling mastery — ISO 11898-2 high-speed vs 11898-3 fault-tolerant vs SAE J2411 single-wire, bit timing/sample point/SJW, termination measurement, transceiver selection (SN65HVD230/231/232, TJA105x, MCP255x/256x, NCV7356, AU5790), error states and bus-off, listen-only discipline, 11/29-bit and CAN FD basics, defensive signal reverse engineering with DBC tooling. Use when connecting anything to a vehicle network or analyzing bus traffic.
triggers:
  - can bus
  - canbus
  - can transceiver
  - sn65hvd230
  - tja1050
  - termination resistor
  - 120 ohm
  - bit timing
  - sample point
  - bus-off
  - error passive
  - sw-can
  - single wire can
  - gmlan bus
  - sniff can
  - reverse engineer can
  - dbc file
  - cantools
  - opendbc
  - كان باص
  - فيشة obd
  - توصيل كان
  - ترانسيفر
  - مقاومة الترمينيشن
personas:
  - AUTO
tech_stack:
  - can-physical-layer
  - esp32-twai
lord: true
---

[SKILL] can-bus-lord
[OBJ] Get the physical layer right before anything else: measure before connecting, choose the correct transceiver for the actual bus type, compute bit timing from the active driver, interpret error states correctly, reverse-engineer signals defensively with documented confidence.
[COMPAT] tech-stack/can-physical-layer.md (measurements/transceivers), tech-stack/esp32-twai.md (ESP32 errata), skills/embedded-firmware-lord/SKILL.md (firmware), skills/gm-opel-lord/SKILL.md (GM bus layout), reverse-engineering-lord (general RE method)
[SRC] Researched 2026-11-27. Evidence: ISO 11898 previews, TI SLOS346O, NI J2411 docs, onsemi AND8169-D, python-can Context7 docs, cantools/opendbc/SavvyCAN repos; dossier §4.5–4.6.

[RULES]
1. [REQ] First question on any CAN task: WHICH physical layer? HS-CAN ISO 11898-2 (differential, ~2.5V recessive both lines) ≠ fault-tolerant ISO 11898-3 (recessive CANH≈0V/CANL≈5V) ≠ SW-CAN SAE J2411 (single wire, recessive ≈0V, dominant ≈4–5V, HV wakeup near battery). Wrong assumption = wrong hardware = potential bus disturbance.
2. [KNOW] SW-CAN correction [documented]: pin-1 LS-GMLAN recessive ≈ 0V, NOT 2.5V. Normal 33.333 kbit/s, diagnostic 83.333 kbit/s, wakeup pulses near 12V. The 2.5V figure is HS-CAN only.
3. [REQ] Measurement-before-connection protocol: pinout verification → voltage scan key-off/key-on → resistance scan key-off → document → connect. ~60Ω across pins 6/14 key-off = healthy dual termination; ~120Ω = one end missing; ≤40Ω = extra terminator present (often a module with built-in 120Ω — find and remove it).
4. [KNOW] OBD pinout core [documented]: 4 chassis GND, 5 signal GND, 6 CAN-H, 14 CAN-L, 16 permanent +12V. GM-optional: pin 1 SW-CAN, pins 3/11 MS-CAN (may be absent), pin 7 legacy K-line. Verify population per vehicle — never assume.
5. [KNOW] SN65HVD230/231/232 discipline [documented — TI SLOS346O]: Rs high on 230 = listen-only standby (driver off, receiver ON); on 231 = full sleep (receiver OFF too); 232 has no Rs. Substitution is a silent failure mode — read the top marking.
6. [REQ] Built-in termination trap: cheap 230 modules often carry a populated 120Ω (`121`) resistor — module-vendor choice, not chip property. Inspect and measure every module across CANH-CANL; remove before vehicle connection; never put a third terminator on a terminated vehicle bus.
7. [KNOW] TJA1050/1051/1042/MCP2551/2562 = HS-CAN parts only — none can do SW-CAN or fault-tolerant. TJA1050 is 5V: RXD can overdrive 3.3V MCU inputs; prefer 3.3V-native or level-protect. SW-CAN needs NCV7356/AU5790-class with correct mode control. [documented]
8. [REQ] Bit timing: compute sample point `(1+TSEG1)/(1+TSEG1+TSEG2)` per the active driver's documented model; SJW per driver limits; never copy register constants across driver generations or platforms. Validate on bench at the exact target bitrate before vehicle.
9. [PROHIBIT] NEVER transmit to probe an unknown bitrate — passive measurement (scope/logic analyzer/auto-detect hardware in listen-only) only. Wrong-bitrate transmission floods the bus with error frames; on errata-affected ESP32 silicon even listen-only misconfigured nodes can disturb the bus.
10. [KNOW] Error confinement [documented]: error-active → error-passive (TEC/REC thresholds) → bus-off (TEC>255). Error-passive nodes emit recessive-only error signaling. After bus-off: stop TX, log, report — no auto-retry storms.
11. [KNOW] 11-bit vs 29-bit = separate address spaces; functional vs physical addressing changes meaning of the same numeric ID. CAN FD: EDL bit, up to 64-byte payload, needs FD controller+transceiver — classic hardware sees errors/garbage on FD traffic.
12. [REQ] Defensive signal RE methodology: listen-only baseline capture (time-correlated with vehicle actions) → identify periodic IDs + rates → change ONE variable (press one button, turn one knob) → diff the traffic → hypothesize signal with scaling → validate against repetition → document with confidence level. Never document forum scaling as fact.
13. [USE] Toolchain: python-can (LGPL-3.0) filters/timestamps/BLF-ASC logging/`--passive`; SavvyCAN (MIT) graphical analysis + DBC overlay + playback; cantools (MIT) DBC compile/decode; commaai/opendbc (MIT) production DBCs incl. gm_global_a_* and opel_omega_2001 — best free decode references; ICSim/UDSim (GPL — knowledge/training only) for safe practice targets.
14. [REQ] Capture discipline: always log raw frames to file before interpreting (.blf/.asc with timestamps); replay beats re-driving; note bus load and error frames in the capture metadata.
15. [KNOW] Termination physics: 120Ω ends match cable impedance; the bus needs exactly two ends. Backbone taps should be short; long stubs reflect. On bench builds, twisted pair even for short runs keeps edges clean.
16. [KNOW] Ground loops/measurement reference: CAN is differential but transceivers share ground reference ranges — a floating or noisy ground corrupts everything. Ground discipline lives in automotive-power-protection; this lord owns verifying signal integrity impact.
17. [REQ] Every documented signal carries provenance: source (capture date/vehicle/tool), confidence (documented/community/unverified), scaling validation state. Unverified forum IDs = hints, never operational data.
