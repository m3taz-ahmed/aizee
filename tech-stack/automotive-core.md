[TECH] automotive-core
[OBJ] Vehicle mechanics, engine types (ICE + electric), electrical/electronic architecture fundamentals. Foundation layer for all automotive work — load before `automotive-diagnostics`, `automotive-vag`, `automotive-opel`, `automotive-ecu-internals`, `automotive-security`.
[SRC] Researched 2026-11-25 — see `docs/studies/study-automotive-ecu-vag-opel-2026-11-25.md` + `temp/auto-research-2026-11-25/claims-ledger.md`.

## 1. Vehicle system decomposition

[RULES]
1. [KNOW] A modern vehicle is ~30–150 ECUs networked over multiple bus segments. Major domains: powertrain (ECM/TCM), chassis (ABS/ESP/EPS), body (BCM, doors, seats, HVAC, lighting), infotainment (MIB/HMI), ADAS (cameras, radar, fusion), high-voltage (BMS, inverter, charger) on EV/hybrid.
2. [KNOW] ECU = MCU + power supply + input conditioning (ADC, filtering) + output drivers (high-side/low-side, H-bridge, PWM) + bus transceivers. Output drivers are the usual failure point; inputs fail by corrosion/shorts.
3. [KNOW] Mechanical powertrain chain: engine → clutch/torque-converter → transmission (MT/AT/DCT/CVT) → differential → half-shafts. AWD adds transfer case or a demand coupling (Haldex-type for transverse platforms).
4. [KNOW] Braking: hydraulic dual-circuit diagonal split, vacuum/electro-hydraulic booster, ABS modulator (valves+ pump, per-wheel pressure control), ESC adds yaw-rate/lateral-accel sensors and active braking. EPB (electronic parking brake) = motorized calipers or cable-puller.
5. [KNOW] Steering: hydraulic (engine-driven pump) → electro-hydraulic → EPS (column/rack/belt-drive motor). EPS is torque-input-based assist with a torque sensor on the torsion bar; steer-by-wire (rare) removes the mechanical link.
6. [KNOW] Suspension types: MacPherson strut, double wishbone, multi-link, torsion beam. Damping: passive → adaptive (CDC/DCC in VAG) → air suspension. Wheel-speed sensors are shared between ABS/ESC/TPMS-indirect.
7. [KNOW] 12V electrical: alternator (LIN-controlled on modern cars, 13.5–14.7V charging), starter, AGM/EFB/li-ion battery, battery monitor (IBS on negative post), power distribution (fuses/relays/eFuses). Voltage drop below ~9V during crank = weak battery or high resistance in cables/grounds.
8. [KNOW] Grounding faults are the #1 undiagnosed electrical issue: measure voltage drop across ground paths under load (>0.2V = suspect). Corrosion at chassis ground points causes ghost CAN/electrical faults.

## 2. Internal combustion engine fundamentals

9. [KNOW] Otto cycle 4 strokes: intake, compression, power, exhaust. Diesel: same strokes, compression-ignition (no spark, CR 14–23:1 vs petrol 9–14:1 direct injection). 2-stroke: power every revolution, used in small tools, extinct in cars (emissions).
10. [KNOW] Key parameters: displacement (swept volume), bore/stroke (undersquare=torque, oversquare=revs), compression ratio, volumetric efficiency, brake mean effective pressure (BMEP — the real efficiency/torque-density measure), specific output (kW/L).
11. [KNOW] Valve trains: OHV (pushrod, GM LS) → SOHC → DOHC. Variable timing: cam-phasing (VVT, VW's vvt, BMW VANOS), variable lift (Honda VTEC, VW/ Audi use cam-phasing + in some valvelift). VW EA888 Gen3+: integrated exhaust manifold in head, dual injection (MPI+GDI) in some markets.
12. [KNOW] Induction: naturally aspirated → turbocharged (exhaust-driven, wastegate or VTG/VNT) → supercharged (belt-driven) → twin-charged (VW 1.4 TSI Twincharger = supercharger+turbo, EA111). Turbo sizing trade: response vs peak power. Intercooling mandatory on boosted engines (charge cooling).
13. [KNOW] Fuel systems petrol: carburetor → single-point → multi-point port injection (PFI/MPI) → gasoline direct injection (GDI/FSI/TSI). GDI: HPFP driven off camshaft, 100–250 bar rail (up to 350 bar in newest), piezo or solenoid injectors. GDI carbon buildup on intake valves (no fuel washing) — walnut blasting is the service.
14. [KNOW] Diesel fuel systems: unit injector (VW PD "Pumpe-Düse" 1.9/2.0 TDI pre-2008, cam-driven per-cylinder pumps) → common rail (CP1/CP3/CP4 pump, 1600–2500 bar, piezo/solenoid injectors with multiple injection events: pilot/main/post). CP4 pump failures (metal shavings cascade) are a known fleet issue.
15. [KNOW] Engine management inputs: crank position (inductive/Hall 60-2 or 36-1 tooth wheel — THE reference), cam position (phase), MAF or MAP (load), throttle position, lambda O2 (narrowband switching or wideband LSU linear), knock (piezo resonance), ECT/IAT/oil temp/pressure, pedal position.
16. [KNOW] Torque-based control (Bosch ME/MED philosophy): driver pedal → torque request → coordinators (cruise, ESP, gearbox) arbitrate → air path (throttle/wastegate) + fuel (lambda) + ignition timing. Understanding this model is required for tuning — it's not "more fuel = more power".
17. [KNOW] Knock control is the power limiter on boosted petrol: timing retarded per-cylinder adaptively; tuner headroom = octane margin. EGT (exhaust gas temp) protection enriches mixture at high load — racing tolerance in stock cal.
18. [KNOW] Emission aftertreatment petrol: 3-way cat (needs lambda 1.0 ± narrow window). Diesel: oxidation cat + DPF (soot filter, active/passive regen, ash loading) + EGR (low/high pressure) + SCR AdBlue/DEF (urea 32.5% injection, NOx conversion) + LNT on older. Dieselgate-era calibrations key on these.
19. [KNOW] Misfire detection: crankshaft speed fluctuation analysis per firing interval. Misfire DTCs P0300–P0312; catalyst-damaging misfire flashes the MIL/CEL.
20. [KNOW] Timing drives: belt (scheduled replacement 60k–180k km, failure = valve-piston contact on interference engines) vs chain ("lifetime" but stretch on many — VAG EA888 Gen1/2 tensioner failures, Opel 1.4 turbo chains). Verify engine-specific weak points before purchase/inspection.

## 3. Engine configurations (all types)

21. [KNOW] Inline (straight): cylinders in one row. I3 (1.0 TSI VW, EcoBoost), I4 (dominant worldwide), I5 (VW/Audi 2.5 TFSI EA855 — Audi RS3/TT-RS, distinctive firing order 1-2-4-5-3), I6 (BMW hallmark, inherently balanced primary/secondary).
22. [KNOW] V-configuration: two banks at an angle sharing crank. V6 (common 60°/90°, VW/Audi 3.0 TFSI EA839 is 90° with hot-V turbo inside), V8, V10 (Audi 5.2 R8/Lambo), V12. Hot-V = turbos in the valley for response/thermal packaging.
23. [KNOW] VR6 (VAG-specific): narrow-angle (15°) staggered single-head 6-cylinder — fits transverse engine bays of a 4-cyl car while giving 6-cyl smoothness/displacement. 2.8/3.2/3.6 VR6 in Golf R32, Passat, Touareg-era. W8/W12/W16 = two VR banks mated (Passat W8, Phaeton/Continental W12, Veyron/Chiron W16 quad-turbo).
24. [KNOW] Boxer/flat: horizontally opposed pistons (Porsche, Subaru) — low CG, inherent balance. Rotary/Wankel (Mazda RX series): epitrochoidal housing, apex seals the wear point — compact, smooth, thirsty; extinct post-RX-8, returns as range-extender (MX-30 R-EV).
25. [KNOW] Atkinson/Miller cycle: late intake valve closing reduces effective compression for efficiency while keeping high geometric CR — standard in hybrids (Toyota) and Miller-cycle VAG EA211/EA888 Gen3B/Gen4 efficiency variants (B-cycle).
26. [KNOW] Variable compression (Infiniti VC-T) and cylinder deactivation (VAG ACT = cylinders 2-3 off on EA211/EA888; GM AFM/DFM; FCA MDS) — solenoid-deactivated lifters or cam-slider systems.
27. [KNOW] Homogeneous charge compression ignition (HCCI) research; Mazda SkyActiv-X = spark-controlled compression ignition (SPCCI) — the production bridge between petrol and diesel combustion.
28. [KNOW] Opposed-piston engines (Achates) and free-piston linear generators = research/exotic. Hydrogen ICE (BMW legacy, Toyota racing) keeps cylinder architecture, needs direct injection + crankcase ventilation rework.

## 4. Electric & hybrid propulsion motors

29. [KNOW] EV traction motor types (evidence: MDPI Machines review 2020 + MDPI Vehicles 2022): (a) PMSM permanent-magnet synchronous — dominant (Tesla Model 3 rear, VW ID family APP310/APP550, most OEMs): highest efficiency/power density, rare-earth NdFeB cost & demagnetization risk, field weakening needed at high rpm. (b) Induction/asynchronous (Tesla Model S front historically, Audi e-tron GT front): robust, no magnets, cheap, slightly less efficient, no drag losses when unpowered. (c) EESM wound-field synchronous (BMW iX3/iX, Renault) — no rare earths, field current controls excitation, needs slip rings/brushes. (d) SRM switched reluctance — cheapest/robust but torque ripple/NVH blocks mainstream use. (e) Axial-flux PMSM — pancake shape, ~5 kW/kg class power density (YASA — Mercedes-AMG, Koenigsegg), in-wheel capable.
30. [KNOW] Inverter = DC-link + IGBT/SiC-MOSFET half-bridges switching battery DC to 3-phase variable-frequency AC. SiC (800V architectures — Porsche Taycan/Audi e-tron GT, Hyundai E-GMP) cuts switching losses, enables higher voltage/rpm. FOC (field-oriented control) = the standard torque control algorithm (clarke/park transforms, current vector in rotor frame).
31. [KNOW] Hybrid architectures: (a) micro/mild hybrid 48V (BISG belt integrated starter-generator — VAG eTSI, Opel/PSA 48V): torque assist + regen, no EV-only mode. (b) Full hybrid (Toyota HSD power-split planetary, VW legacy): series-parallel blending. (c) Plug-in hybrid PHEV: 10–100km EV range. (d) Range-extender EREV (BMW i3 Rex): ICE drives generator only. Topologies: P0 (belt), P1 (crank), P2 (between engine/gearbox clutch — VW GTE), P3 (post-gearbox), P4 (rear axle electric — PSA/Volvo).
32. [KNOW] HV battery: pouch/prismatic/cylindrical cells, NMC/NCA/LFP chemistries (LFP: cheaper, durable, less dense, less thermal runaway risk; NMC high-nickel: density). 400V vs 800V systems. BMS: cell voltages/temps balancing, SOC/SOH estimation, contactor control, isolation monitoring — safety-critical.
33. [KNOW] Regenerative braking blending: motor regen torque + friction brakes coordinated by brake-by-wire (Bosch iBooster, VW uses eBKV). Thermal limits and SOC cap regen — pedal feel must stay constant.
34. [KNOW] Charging: AC onboard charger (3.6–22kW) vs DC fast charging CCS2 (Europe), NACS/J3400, GB/T, CHAdeMO (legacy). Communication: IEC 61851 PWM pilot + ISO 15118 PLC high-level (plug&charge) / DIN 70121. VAG MEB = CCS2, up to 125–200kW.
35. [KNOW] Fuel cell EV (Toyota Mirai, Hyundai Nexo): PEM stack, 700bar H2 tanks, small buffer battery — the motor/inverter/gear train is standard EV; the fuel cell replaces the battery as energy source.

## 5. Vehicle networks (physical/data-link layer)

36. [KNOW] CAN (ISO 11898-1/2): differential pair CAN_H/CAN_L, recessive=1 (~2.5V both), dominant=0 (CAN_H +1V, CAN_L −1V). 120Ω termination at each bus end (60Ω measured across pins 6/14 on OBD). Arbitration: lowest 11-bit/29-bit ID wins — inherent priority. No addressing: broadcast bus, receivers filter IDs. Bitwise dominant/recessive enables error frames — any node can kill a frame.
37. [KNOW] CAN speeds: powertrain/HS 500kbit/s (some 250k), body/MS 100–125kbit/s, fault-tolerant low-speed CAN (ISO 11898-3) 33.3–125k tolerates single-wire degradation. CAN FD (ISO 11898-1:2015): same arbitration, data phase up to 2–8Mbit, payloads up to 64 bytes (classic=8). CAN XL next-gen. Check FD vs classic before connecting tools — mismatch = error frames storm.
38. [KNOW] GMLAN (GM/Opel): HS 500k dual-wire powertrain + chassis expansion, MS 125k mid-speed, LS single-wire (SWCAN/GMLAN-LS) 33.3k normal / 83.3k high-voltage-wake programming mode. SWCAN is single-wire — needs hardware supporting it (panda does; cheap ELM327 clones do NOT).
39. [KNOW] LIN: single-wire master-slave, ≤20kbit/s, cheap — seats, windows, HVAC flaps, rain sensor, steering-wheel buttons, alternator control. Master polls slaves by schedule table; slaves only speak when addressed.
40. [KNOW] FlexRay: dual-channel 10Mbit/s deterministic TDMA — used in BMW/high-end chassis/ADAS era (Audi A8 D4, Simos 18.4 ECU variant). Being displaced by automotive Ethernet.
41. [KNOW] MOST: optical/coax ring for infotainment media (25/50/150 Mbit) — MIB systems in VAG use MOST150 ring; break the ring = dead infotainment (fiber jumper loops used for module-delete diagnosis).
42. [KNOW] Automotive Ethernet: 100BASE-T1 / 1000BASE-T1 single twisted pair (OPEN Alliance). Used for DoIP diagnosis, cameras, ADAS backbones, OTA. Protocols above: DoIP (ISO 13400), SOME/IP + SOME/IP-SD (service discovery, AUTOSAR adaptive), AVB/TSN for media. VAG MQB evo/MEB backbone.
43. [KNOW] K-Line (ISO 9141-2) / L-Line: pre-CAN single-wire UART-ish 10.4kbit/s diagnosis. 5-baud slow init (address 0x33 bit-banged at 5 baud!) then fast comms, or fast-init pattern. VAG pre-2004ish, Opel/GM era engines, motorcycles. KKL/VAG-KKL cables = FTDI + transistor level shifter.
44. [KNOW] SENT (SAE J2716): single-edge nibble transmission — cheap unidirectional sensor protocol (throttle, pedal, pressure). PSI5 similar for airbag sensors.
45. [KNOW] Gateways: central BCM/gateway routes between buses (diagnostic gateway = firewall in modern cars). VAG: J533 data bus diagnostic interface. GM/Opel: BCM is HS↔LS gateway. Many retrofits fail because gateway must be coded to know the new module exists (VAG installation list/gateway list).

## 6. Working discipline for mechanics/electrics

46. [REQ] Measure before replace: sensor sig with scope/DMM against spec, reference voltages (5V ref), grounds under load. Parts-cannon diagnosis wastes money.
47. [REQ] Never probe airbag/pyrotechnic circuits with generic multimeter, never power them during disassembly — battery disconnect + wait time first.
48. [REQ] Flash/programming operations: stable PSU/charger (13.5V+ maintained), no interruptions — voltage drop mid-flash bricks ECUs (evidence: ODIS workshop guidance).
49. [REQ] HV work (orange cables): only with training (isolation gloves CAT-rated, vehicle HV disable + verify absence of voltage). EV/hybrid systems kill.
50. [KNOW] Torque specs + angle torque (torque-to-yield bolts one-time use — head bolts, stretch bolts). Assembly lube on bearings; sealant types matter (anaerobic vs RTV).

[COMPAT]
- Load next: `automotive-diagnostics.md` for protocols/tools, `automotive-vag.md` / `automotive-opel.md` for brand specifics, `automotive-ecu-internals.md` for firmware/tuning, `automotive-security.md` for security research.
[REFS]
- Opel CAN evolution paper: https://can-cia.org/fileadmin/cia/documents/proceedings/2012_eisele.pdf
- EV motor survey: https://mdpi-res.com/d_attachment/machines/machines-08-00020/article_deploy/machines-08-00020-v2.pdf
- EV motor multi-criteria: https://www.mdpi.com/2032-6653/13/4/65
- VAG platforms: https://en.wikipedia.org/wiki/List_of_Volkswagen_Group_platforms
