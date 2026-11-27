---
name: auto-mechanics-engines
description: Engine types, architectures, fuel systems, hybrid/EV motors, engine management concepts, and open-source engine simulators. Load for engine/mechanics/motor/tuning-concept questions.
triggers:
  - engine
  - motor
  - mechanics
  - petrol
  - diesel
  - hybrid
  - electric vehicle
  - ev
  - turbo
  - cylinder
  - combustion
  - fuel system
  - injector
  - ecu tuning concept
personas:
  - AUTO
tech_stack:
  - automotive-core
  - automotive-fault-codes

---

[SKILL] auto-mechanics-engines
[OBJ] Correct engine/mechanics knowledge across all types + know which open-source simulators and engine-management firmware exist.
[COMPAT] tech-stack/automotive-core.md (deep engine-type reference), skills/ecu-tuning.md (tuning layer), skills/obd-diagnostics.md (data acquisition)
[RULES]
1. [REQ] ICE architectures: inline (I3/I4/I5/I6), V (V6/V8/V10/V12), VR/VR6 (shared pins), boxer/horizontally-opposed, rotary/Wankel, Atkinson-cycle variants. State bore/stroke/valve-train (OHV/OHV/SOHC/DOHC) when relevant.
2. [REQ] Fuel systems: petrol port-injection MPI → direct-injection TDI/GDI → common-rail diesel (high-pressure pump + piezo/electromagnetic injectors + rail pressure sensor) → gasoline direct injection. Diesel = compression ignition, no throttle plate (air path via turbo+throttle for EGR control).
3. [REQ] Forced induction: turbo (exhaust-driven, wastegate-controlled, boost pressure = wastegate duty + N75/VNT) vs supercharger (belt-driven). Intercooler placement, blow-off/compressor-bypass valve, overboost protection.
4. [REQ] Engine management = ECU inputs (crank/cam position, MAF/MAP, O2/lambda wideband, knock, temps, throttle) → outputs (injectors, coils, throttle, wastegate, cam phasing VVT). Fuel = injector pulse width ∝ fuel mass / injector flow rate.
5. [REQ] Emissions chain: EGR (exhaust gas recirculation) + PCV/CCV (crankcase ventilation) + DPF (diesel particulate) + SCR/AdBlue (urea NOx) + E-Cat + secondary-air injection. EGR valve failure + PCV freeze = classic cold-climate stalling pattern.
6. [REQ] Hybrid topologies P0–P4: P0 = engine+motor same shaft (mild hybrid belt/ISG), P1/P2 = power-split eCVT (THS/Hybrid Synergy), P3/P4 = series/parallel plug-in. 48V mild-hybrid = belt starter-generator.
7. [REQ] EV motor types: PMSM (permanent magnet synchronous — dominant traction), AC induction (Tesla Model S/X early), EESM (electrically excited — Renault), SRM (switched reluctance — low cost), axial-flux (yasa-class, high power density). Inverter = Si IGBT → SiC MOSFET transition.
8. [REQ] HV battery: NMC/NCA/LFP cells → modules → pack; BMS = cell-voltage/temp monitoring + contactor control + SOC/SOH estimation; charging CCS/CHAdeMO/NACS; regenerative braking blends via inverter.
9. [REQ] Engine sims (open): `pablomarcel/vICE` (MIT — 0-D ICE cycle, slider-crank, Wiebe burn, P-V diagram, BSFC sweeps, Cantera option, turbo mean-value), `Open-Heavy-Machinery/open-crank` (Apache-2.0 — J1939 HD-diesel plant+ECU sim), `DimitriosVogiatzis/ICE_thermodynamic` (MATLAB DI diesel), `sandialabs/DieselGen.jl` (MIT, FASTSim-style Julia), LiU Diesel 2 (Simulink, LGPL — validated turbo+throttle model).
10. [REQ] Open EMS firmware: `rusefi` (GPL standalone), `speeduino` (GPL Arduino), `HaniCore` (Bosch ME7/C167 standalone), `hellen-one` (rusEFI hardware platform — no OSI license), `Mazduino` (rusEFI/Speeduino-compatible + EFI Analytics TunerStudio).
11. [REQ] Common failure knowledge: timing chain stretch (EA888 — stretch sensor block 93), carbon buildup on intake valves (GDI — no fuel wash), high-pressure fuel pump failure (CP4), PCV freeze/stall, EGR cooler soot, swirl-flap actuator, thermostat stuck, coolant intrusion into oil (sleeve leak).
12. [REQ] Mechanical tricks (wrench-level, from automotive-tricks.md): used-module reuse playbook (virginize/clone/adapt + where pairing data lives), retrofit master pattern (gateway → dependent modules → calibration), battery registration after replacement, injector coding for used injectors, EPB service mode.
13. [PROHIBIT] Do NOT reproduce odometer-fraud, hot-wiring, or immobilizer-bypass procedures — defensive framing only.
14. [VER] When claiming engine-specific failure modes verify against wave-1 `tech-stack/automotive-tricks.md` + `automotive-core.md` — those carry the verified per-engine detail.
