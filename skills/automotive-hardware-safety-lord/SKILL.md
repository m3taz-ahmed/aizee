---
name: automotive-hardware-safety-lord
description: Lord skill for safe physical connection to vehicles — measurement before connection, 12V transient reality (ISO 7637-2/16750-2 load dump, cranking), TVS/reverse-polarity/fusing discipline, grounding and ground loops, USB isolation vs vehicle power, bench setup with current-limited supply and two-node test bus, under-dash thermal/mechanical integration. Use when hardware touches a real car.
triggers:
  - connect to car
  - obd wiring
  - pin 16 power
  - load dump
  - tvs diode
  - reverse polarity
  - ground loop
  - usb isolator
  - bench test bus
  - car power supply
  - fuse vehicle
  - obd pigtail
  - measure before connect
  - توصيل بالسيارة
  - كهرباء العربية
  - حماية الدائرة
  - قياس قبل التوصيل
  - فيشة obd توصيل
personas:
  - AUTO
tech_stack:
  - automotive-power-protection
  - can-physical-layer
lord: true
---

[SKILL] automotive-hardware-safety-lord
[OBJ] Keep people, laptops, adapters, and vehicles safe: every hardware instruction starts with measurement, every power path is protected by design, every first contact happens on a bench before a vehicle.
[COMPAT] tech-stack/automotive-power-protection.md (protection design depth), tech-stack/can-physical-layer.md (pins/transceivers), skills/embedded-firmware-lord/SKILL.md (brownout/boot-safe firmware), skills/gm-opel-lord/SKILL.md (vehicle pinout specifics)
[SRC] Researched 2026-11-27. Evidence: TI TIDUC42, Diodes automotive TVS note, ST TA0338, MCC AN5001, NI/onsemi CAN electrical docs, vectra-scanner MASTER-PROMPT hardware notes, dossier §4.8.

[RULES]
1. [REQ] The first rule of automotive hardware: **measure before you connect — every time, even on a car you know.** Pinout verification → voltage scan (key-off/key-on) → resistance scan (key-off) → documented → connect. A misplaced probe costs a board; a wrong assumption can cost a vehicle network.
2. [KNOW] Pin 16 = permanent +12V regardless of ignition. CAN lines operate at transceiver levels (HS ≈2.5V recessive; SW-CAN ≈0V recessive with 4–5V dominant and ~12V wake pulses). 12V must never reach MCU/transceiver logic pins. [documented]
3. [KNOW] The 12V rail is hostile: cranking dips, inductive spikes (ISO 7637-2 pulse families), jump-start abuse, load dump (ISO 16750-2 — clamped typically 30–40V subsystem-facing, OEM-specific). A bare buck module is NOT a protection design. [documented]
4. [REQ] Minimum vehicle-power stack: fuse at the tap → reverse-polarity protection (Schottky/ideal-diode MOSFET) → TVS sized by calculation (standoff above normal max incl. jump-start decision; clamp below downstream rating with margin) → buck input rating above clamp → bulk capacitance → thermal check. No copied part numbers without documented assumptions.
5. [REQ] USB-vs-vehicle power isolation: never feed the adapter from both without designed or-ing/isolation — backfeed kills USB ports. Prefer laptop on battery for car work; USB isolator is the upgrade path; beware ground loops through chargers and bench equipment. [documented practice]
6. [KNOW] Ground discipline: pin 4 chassis vs pin 5 signal ground — know which your interface uses; verify ground quality under load (voltage drop measurement), not visually; never let high currents share the sensitive ground path.
7. [REQ] Bench-first gate: current-limited PSU → two-node test bus with exactly two 120Ω terminators → validate power draw, TX-inhibit default, recovery behavior, fault injection → only then vehicle, listen-only first. No exceptions for "simple" adapters.
8. [KNOW] Battery voltage sensing belongs over diagnostics (OBD PID 0x42 where supported) or a protected divider — never raw pin-16-to-ADC. Any ADC sensing needs divider math, input protection, tolerance analysis. [community project note]
9. [REQ] Disconnect vehicle-powered adapters during jump-start, battery charging, or welding on the vehicle — protection designed for normal transients is not rated for every abuse.
10. [KNOW] Reverse-voltage reality: -14V/60s is the ISO 16750-2-style test for 12V systems — series protection mandatory; compute diode/MOSFET dissipation at max load. [documented]
11. [REQ] Under-dash integration: strain relief everywhere, no solder-only splices in vibration zones, heat-rated insulation, mechanically secured modules, accessible fuse, no loose PCBs. A rattling adapter is a short circuit waiting for a pothole.
12. [REQ] Post-install verification: capture rail minimum during one cranking event at the adapter input — if the MCU browns out, fix capacitance/UVLO before trusting the device; brownout mid-write is a safety event, not a glitch.
13. [PROHIBIT] Never: wire pin 16 through a bare buck straight to an ESP32; use a fuse "upgrade" to stop nuisance blowing (find the fault instead); trust color-coded pigtails without measuring; connect mains-powered laptop + vehicle + bench gear in one ground loop; bench-test at unlimited current.
14. [CMD] Standard pre-connection checklist output format: pinout table with measured voltages/resistances → pass/fail per line → anomalies explained → explicit go/no-go. The user confirms each step before the next.
15. [KNOW] Tools of the trade: multimeter with min/max capture, current-limited bench supply, USB isolator, oscilloscope/logic analyzer for bitrate/signal verification, breakout OBD pigtail with labeled taps. Cheap correct measurement beats expensive guessing.
