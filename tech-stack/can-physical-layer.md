[TECH] can-physical-layer
[OBJ] CAN physical-layer engineering reference: ISO 11898-2 high-speed vs ISO 11898-3 fault-tolerant vs SAE J2411 single-wire, voltage/termination measurement with a multimeter, transceiver selection (SN65HVD230/231/232, TJA1050/1051/1042, MCP2551/2562, NCV7356, AU5790), bit timing/sample point, error states, OBD-II connector pinout measurements.
[SRC] Researched 2026-11-27. Evidence: TI SLOS346O datasheet, onsemi AND8169-D, NI single-wire CAN docs, ISO 11898 previews (ANSI), VW SSP training material, `refs/automotive-embedded-research-2026-11-27.md` §4.5–4.6.

## 1. Three different physical layers — do not conflate

[RULES]
1. [KNOW] HS-CAN ISO 11898-2 (differential, up to 1 Mbit/s): recessive/idle ≈ 2.5V on BOTH CANH and CANL; dominant drives CANH ≈ 3.5V and CANL ≈ 1.5V (differential ≥ ~0.9–2V). Used on OBD pins 6/14 in legislated diagnostics. [documented — ISO 11898-2 / vendor app notes]
2. [KNOW] Fault-tolerant LS-CAN ISO 11898-3 (≤125 kbit/s): NOT the same as GM single-wire. Recessive CANH ≈ 0V / CANL ≈ 5V; dominant CANH ≈ 3.6V / CANL ≈ 1.4V; can degrade to one-wire operation on wire faults. Different transceiver family (TJA1054/1055-class). [documented — onsemi AND8169-D / VW SSP]
3. [KNOW] Single-wire CAN SAE J2411 (GM LS-GMLAN): one signal wire + ground, normal mode 33.333 kbit/s, high-speed/diagnostic mode 83.333 kbit/s; nominal logic levels ≈ 0V/4V in normal modes; HIGH-VOLTAGE WAKEUP drives near battery voltage (~12V) at normal speed to wake sleeping nodes. Receiver thresholds: recessive CAN_Bus < 1.6V, dominant > 3.4V (onsemi figure: ~0.1V recessive / 4V dominant). [documented — NI + onsemi AND8169-D]
4. [REQ] **SW-CAN recessive ≈ 0V, not 2.5V.** The 2.5V idle figure belongs to HS-CAN only. Any doc/AI answer claiming pin-1 idle ≈ 2.5V is wrong or measuring something else — correct it. [documented; conflict resolved in dossier §5]
5. [KNOW] Legislation baseline: US mandated ISO 15765-4 CAN signaling for OBD-II from MY2008; EU EOBD petrol passenger cars 2001 / diesel 2004 (first registration; earlier for new type approvals) with NO early single-CAN-mandate — K-line/ISO 9141/14230 remained legal in EU. Never infer bus presence from year alone; measure. [documented with category caveat]

## 2. Multimeter measurements before connecting anything

6. [REQ] Measurement order on an unknown vehicle connector: identify pinout → voltage scan all pins key-off/key-on → resistance scan key-off → only then connect any interface. Log everything.
7. [KNOW] OBD-II/J1962 pinout core: pin 4 chassis ground, pin 5 signal ground, pin 6 CAN-H, pin 14 CAN-L, pin 16 permanent +12V battery. Manufacturer-optional: GM SW-CAN pin 1, possible MS-CAN pins 3/11, legacy K-line pin 7 — verify population per vehicle, never assume. [documented core + community manufacturer pins]
8. [KNOW] HS-CAN termination check: ~60Ω between pins 6↔14 key-off = two 120Ω end terminators in parallel. ~120Ω suggests one missing/one end of bus tapped; ~40Ω or lower suggests an extra terminator installed (often a carelessly added scan tool/module with built-in 120Ω). [documented engineering practice]
9. [KNOW] Caveats: ECU sleep state, measurement polarity, and transceiver leakage affect the reading — it is a screening check, not proof of bus health. If the reading is odd, power the bus key-on and re-check voltage symmetry. [documented engineering caveat]
10. [KNOW] HS-CAN voltage sanity key-on: each line ≈ 2.5V to ground at rest; CANH should be marginally above CANL. A line stuck at 0V or battery = wiring/short fault. SW-CAN pin 1 recessive ≈ 0V with dominant pulses toward 4–5V (and ~12V during wake events). Pin 16 = permanent +12V regardless of key. [documented]
11. [PROHIBIT] Never connect a node with a permanent 120Ω termination onto an already-terminated vehicle bus — a third terminator overloads the drivers (≈40Ω bus) and can disturb the vehicle network. Bench bus = exactly two 120Ω ends.

## 3. Transceivers

12. [KNOW] SN65HVD230/231/232 (3.3V, TI SLOS346O) [documented]: pin 8 `Rs` low = high-speed mode; resistor to ground = slope control; **Rs high on the 230 = low-current standby LISTEN-ONLY — driver off, receiver active**. On the 231, Rs high = full sleep — driver AND receiver off. The 232 has no Rs mode pin.
13. [REQ] Part-number discipline: 230 ≠ 231 ≠ 232. A 231 substituted for a 230 silently kills receive in "standby"; a 232 removes hardware listen-only control entirely. Read the top marking / order exact parts.
14. [KNOW] Built-in termination trap [community/unverified per module]: many cheap SN65HVD230 breakout modules ship with a 120Ω resistor (marked `121`) populated across CANH/CANL. This is a MODULE-VENDOR choice, not a TI chip property. The only safe rule: inspect + measure the actual module across CANH-CANL; remove the resistor before vehicle connection if present (fine to keep on a bench node that IS the bus end, switchable preferred).
15. [KNOW] TJA1050/TJA1051/TJA1042, MCP2551/MCP2562 = 5V/3.3V HS-CAN-class parts — NONE of them can do single-wire SW-CAN or ISO 11898-3 fault-tolerant. TJA1050 is 5V-only: its RXD high can overdrive 3.3V ESP32 GPIO — use series resistor/level shifting or prefer 3.3V-native parts. [documented]
16. [KNOW] SW-CAN requires a J2411-capable transceiver: NCV7356 or AU5790-class, with correct mode control (normal/high-speed/wakeup). `garnerm91/SWCAN` is an open module project reference (no license detected — knowledge-only). [documented silicon + community module]
17. [REQ] Every custom adapter design lands transceiver datasheet parameters: supply, dominant current limit, thermal behavior, ESD rating, common-mode range. Cite the exact datasheet revision in design notes.

## 4. Bit timing, sample point, error states

18. [KNOW] Bit time = sync + TSEG1 + TSEG2 in time quanta; sample point = `(1 + TSEG1)/(1 + TSEG1 + TSEG2)` in the common Bosch/CiA model. SJW limits resynchronization jumps. Exact API fields differ per driver (ESP32 TWAI presets vs custom bit timing vs SocketCAN `bit-timing`) — compute from the ACTIVE driver's documented model, never copy register constants across platforms. [documented model]
19. [KNOW] Wrong bitrate/sample-point on a shared bus = your node generates error frames continuously (bit errors at every sample). On errata-affected ESP32 TWAI silicon this can disturb the bus even in listen-only — see `esp32-twai.md` §2.
20. [KNOW] Error confinement: TEC/REC counters → error-active (can send active error frames) → error-passive (recessive-only error signaling) → bus-off (TEC > 255, controller detached). Recovery requires explicit initiation (legacy TWAI) or driver recovery flow; never auto-retry storm after bus-off — stop TX, log, report. [documented]
21. [KNOW] 11-bit vs 29-bit IDs are different address spaces; CAN FD adds flexible data rate + up to 64-byte payloads and needs FD-capable controller+transceiver. Classic-CAN-only hardware cannot parse FD frames correctly (error floods) — check before connecting to 2020s vehicles. [documented]

## 5. Reverse engineering / sniffing practice

22. [REQ] Sniff doctrine: hardware listen-only (transceiver) + software listen-only + confirmed bitrate before any RX trust. Unknown bitrate → measure with scope/logic analyzer or passive auto-detect hardware; NEVER transmit trial frames.
23. [USE] python-can backends for analysis (socketcan/slcan/pcan/vector/virtual; filters, timestamps, BLF/ASC logging, `--passive` flag on can.logger); SavvyCAN for graphical RE + DBC overlay; cantools for decode; commaai/opendbc for production DBC references. [documented library — LGPL-3.0/MIT]
24. [KNOW] CAN FD note for modern bench: if the vehicle uses FD, classic adapters see garbage/errors — identify frame format early (DLC > 8 or EDL bit) before trusting captures. [documented]

[COMPAT]
- ESP32 controller specifics + errata: `tech-stack/esp32-twai.md`; power/grounding protection: `tech-stack/automotive-power-protection.md`; GMLAN network speeds/roles: `tech-stack/gmlan-gmw3110.md` + `tech-stack/automotive-opel.md`; connector-level vehicle notes: `tech-stack/automotive-wiring.md`.
[REFS]
- TI SN65HVD23x datasheet SLOS346O: https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf
- onsemi CAN physical layers AND8169-D: https://www.onsemi.com/download/application-notes/pdf/and8169-d.pdf
- NI single-wire CAN: https://www.ni.com/docs/en-US/bundle/ecan-labview-api-ref/page/single-wire-can.html
- ANSI ISO 11898 package scope: https://webstore.ansi.org/industry/transportation/controller-area-network
