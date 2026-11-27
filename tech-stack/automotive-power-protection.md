[TECH] automotive-power-protection
[OBJ] 12V vehicle power protection for connected electronics: ISO 7637-2 / ISO 16750-2 transient reality (load dump, cranking, inductive spikes, reverse polarity), TVS/reverse-polarity/fusing design discipline, grounding and ground-loop control, USB-vs-vehicle power isolation, bench setup rules, under-dash mechanical/thermal integration.
[SRC] Researched 2026-11-27. Evidence: TI TIDUC42 reverse-polarity reference design, Diodes Inc automotive TVS app note, ST TA0338 rail-protection article, MCC AN5001 load-dump guide, `refs/automotive-embedded-research-2026-11-27.md` §4.8.

## 1. The 12V rail is hostile

[RULES]
1. [KNOW] The vehicle "12V" rail is not a clean supply: cranking causes deep dips (single-digit volts), inductive loads (motors, injectors, ignition) generate positive/negative spikes, jump-start can apply 24V-class abuse on some vehicles, load dump is a high-energy overvoltage event. [documented — Diodes/TI/ST app notes]
2. [KNOW] Load dump: battery disconnects while alternator charges → sustained overvoltage up to ~400ms (12V systems). Historically ISO 7637-2 pulse 5a/5b; moved to ISO 16750-2 (Test A unsuppressed / Test B suppressed). OEM alternator clamping typically limits subsystem-facing voltage to ~30–40V — exact clamp is OEM-specific. [documented — TI TIDUC42 §2.1.4, MCC AN5001]
3. [KNOW] ISO 16750-2 reverse-voltage test for 12V systems: -14V for 60s in published design guidance — series reverse-polarity protection is mandatory for any vehicle-powered device. [documented — ST TA0338 / TI TIDUC42]
4. [KNOW] ISO 7637-2 pulse classes (still the industry vocabulary): pulse 1 (negative, inductive disconnect), 2a/2b, 3a/3b (fast switching spikes up to ±150V class), 4 (cranking dip). Exact test levels are severity-class dependent — treat any single number as class-specific, not universal. [documented concept]
5. [REQ] Design rule: never power custom electronics from the vehicle with just a bare buck module. Minimum concept stack: fuse at the source tap → reverse-polarity protection → TVS/clamp → buck converter with input rating comfortably above clamp voltage → local bulk capacitance → thermal verification.

## 2. Protection components — design, don't copy

6. [REQ] TVS selection is a calculation, not a copied part number: standoff voltage must be ABOVE normal maximum (charging ≈14.7V, jump-start up to 24V-class on some vehicles) so it doesn't clamp normal operation; clamping voltage must be BELOW downstream max-input with margin; peak pulse power must absorb the expected pulse energy. Verify against the actual waveform class you design for. [documented engineering practice]
7. [KNOW] Example sizing logic [community project note]: SMBJ18A standoff 18V > 14.7V charging — but marginal if jump-start 24V is in scope; then choose higher standoff + ensure buck max-input margin above the resulting clamp voltage. There is no universal correct TVS — document the assumptions.
8. [KNOW] Reverse-polarity options: series diode (simple, costs 0.3–0.7V drop + heat), Schottky (less drop), ideal-diode/P-MOSFET (near-zero drop, more parts). For USB-intermittent low-power tools a Schottky or ideal-diode is typical; compute dissipation at max load. [documented engineering practice]
9. [REQ] Fuse at the tap point, not inside the gadget only: a short in the adapter wiring must not depend on vehicle wiring for protection. Match fuse to wire gauge and expected load; never upsize a fuse "because it keeps blowing" — find the fault.
10. [KNOW] Disconnect during external events: unplug vehicle-powered adapters during jump-start/battery charging/welding on the vehicle — protection sized for normal transients is not rated for every abuse. [documented practice]

## 3. Grounding and ground loops

11. [REQ] Ground is part of the signal path. OBD pin 4 = chassis ground, pin 5 = signal ground — know which one your interface uses and never leave ground to chance. A floating ground makes CAN measurement meaningless and can damage inputs.
12. [KNOW] Ground-loop hazard: laptop on mains charger + vehicle ground + bench equipment can create loops through USB/serial cables. Prefer laptop on battery during vehicle work; use a USB isolator as the upgrade path; never create multiple ground paths through thin USB cable shields. [community/engineering practice]
13. [REQ] Verify ground quality under load, not visually: measure voltage drop across the ground path while the device draws operating current; a corroded ground point drops volts exactly when the bus is busiest.
14. [PROHIBIT] Never power the adapter simultaneously from USB and vehicle VIN without designed isolation/or-ing: backfeed can damage the laptop USB port or the vehicle electronics. Choose ONE source, or implement ideal-diode or-ing, or documented power-path switching. [documented practice]

## 4. Bench setup before vehicle

15. [REQ] Bench-first doctrine: current-limited bench PSU (limit a few hundred mA for adapter tests) → two-node test bus (two 120Ω terminators, second node = known-good transceiver) → validate power draw, idle behavior, TX-inhibit default, and recovery behavior → only then vehicle listen-only.
16. [KNOW] Battery voltage measurement belongs over the diagnostic interface (OBD PID 0x42 where supported, or a fused sense line through a proper divider) — NOT an ADC pin strapped to pin 16 raw. Any ADC sensing needs divider scaling, input protection, and tolerance analysis. [community project note — vectra-scanner]
17. [REQ] In-car integration under the dash: strain relief on all wires, no solder-only splices in vibration zones, heat-rated insulation, secure module mounting (no rattling loose PCBs), fuse accessible, conformal/housed assembly if permanent. A loose adapter under the dash is a short-circuit and a driver-distraction hazard.

## 5. Verification measurements

18. [CMD] Pre-connection checklist (document each): pinout verified → pin 16 ≈ battery voltage to pin 4/5 → no unexpected voltages on CAN pins beyond transceiver-level ranges → adapter current draw in range on bench → TX-inhibit verified with a meter/scope at the transceiver → only then connect.
19. [REQ] After installation: measure rail voltage at the adapter input during cranking once (min voltage captured) and confirm the buck/MCU never browns out — if it does, fix capacitance/UVLO design before relying on the device diagnostically. Brownout mid-write on a vehicle bus is a safety event.

[COMPAT]
- Transceiver electrical details: `tech-stack/can-physical-layer.md`; ESP32 power/brownout/boot behavior: `tech-stack/esp32-twai.md`; vehicle connector pinout: `tech-stack/automotive-wiring.md`.
[REFS]
- TI reverse-polarity reference design: https://www.ti.com/lit/ug/tiduc42/tiduc42.pdf
- Diodes Inc TVS in automotive: https://www.diodes.com/assets/App-Note-Files/TVS-in-Automotive-Applications.pdf
- ST automotive rail protection: https://www.st.com/resource/en/technical_article/ta0338-designing-robust-protection-of-automotive-power-rails-against-overvoltage-and-reverse-polarity-battery-hazards-stmicroelectronics.pdf
- MCC load dump guide: https://solutions.mccsemi.com/hubfs/AN5001%20Quick%20Guide%20on%20Automotive%20Load%20Dump%20Protection.pdf
