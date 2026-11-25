[TECH] automotive-fault-codes
[OBJ] Diagnostic trouble code intelligence: how to reason with DTCs correctly, the high-frequency VAG + Opel codes with their REAL-world causes and verified fixes, live-data verification values. The code-to-fix map — the "كل الأكواد" knowledge layer.
[SRC] Researched 2026-11-25 third pass. Verified against vagpulse.com/guides/common-vag-fault-codes, asfmotors.es VW code tables, enginefinder VW analysis, obdoktor.com Opel code guides, obdllm Opel/CDTI data.

## 0. How to reason with codes (the discipline most people skip)

[RULES]
1. [KNOW] A code names the SYMPTOM the ECU measured, not the part that failed. "System too lean" = mixture wrong — says nothing about whether it's a split hose, tired sensor, or dying pump. The code picks the SYSTEM to test; freeze-frame data (rpm/load/temp at trigger moment) narrows the cause. Never buy parts from the code text alone.
2. [KNOW] VAG dual numbering (verified): older/KWP-era modules store VW's own 5-digit number alongside the SAE P-code — e.g. 18447 = P2015, 16684 = P0300. Two labels, one fault. VCDS/OBDeleven show both.
3. [KNOW] Code structure: P0xxx = generic powertrain (SAE J2012, same meaning everywhere), P1xxx = manufacturer-specific, B/C/U = body/chassis/network. U-codes (module communication) on modern cars are VERY often low-voltage/ground/terminal cascades — check battery+charging+grounds before believing module-death.
4. [KNOW] DTC status bits matter: pending → confirmed → intermittent flag. Intermittent + long-ago mileage stamp = possibly stale history, not the current problem. Read occurrence mileage/age counters, not just the code list.
5. [REQ] The cascade rule: multiple simultaneous codes usually share one root — fix the earliest/lowest-level fault first (typically power/ground/voltage or the first-occurring sensor), clear, re-scan. Chasing each code separately = parts cannon.
6. [KNOW] Clearing discipline: clearing a code does nothing mechanical — the fault returns if the cause lives. Clear AFTER repair to verify the fix holds through drive cycles. Readiness monitors (I/M status) reset on clear — emissions inspection needs them complete again.
7. [KNOW] Fuel-trim interpretation is the master key for mixture codes: STFT+LTFT combined >±10% = real deviation. Lean correction HIGH AT IDLE but normal at 2500rpm = vacuum leak (unmetered air dominates at idle). Lean at ALL loads/rpm = fuel delivery (pump/filter/injectors) or MAF under-reading. Rich negative trims = leaking injectors/saturated canister/MAF over-reading.

## 1. VAG high-frequency codes — verified real-world causes & fixes

8. [KNOW] **P2015** (VAG 18447) intake manifold flap position implausible — the most-searched VAG diesel code. 2.0 TDI CR: plastic flap linkage/actuator position sensor wears or snaps. Usually manifold/actuator hardware, NOT wiring. Confirm with live flap-position value vs commanded; clearing never holds with snapped linkage. Fix: linkage repair kit or manifold/actuator.
9. [KNOW] **P0299** turbo underboost (limp-mode coupling, often capped ~40km/h). Cause hierarchy VERIFIED: (1) boost leak first — split silicone couplers, popped clamps, cracked plastic charge pipes (EA888 pipes crack in cold); (2) torn diverter valve on TSI petrols; (3) N75 boost solenoid or VGT actuator sticking on TDI (DPF backpressure also contributes); (4) wastegate actuator wear. Procedure: pressure-test intake BEFORE condemning the turbo. Verify with requested-vs-actual boost live data at WOT.
10. [KNOW] **P0234** overboost — mirror twin: wastegate stuck closed, blocked/deformed control hose, failed boost-control solenoid. Power cut/limp, engine-damage risk under load. Inspect wastegate+hoses+valve.
11. [KNOW] **P0016/P0017** crank-cam correlation — on 1.2/1.4 TSI (2008-2014) this is the STRETCHED TIMING CHAIN alarm: act immediately, do not wait (interference engine — jumped tooth = bent valves). On 1.8/2.0 TSI more often the cam phaser/adjuster. Cross-ref: chain stretch measurable via measuring block 93 (see `automotive-tricks.md` rule 56).
12. [KNOW] **P0401** EGR flow insufficient — carbon-fouled EGR valve/cooler on PD and CR diesels, worst in stop-start urban use. Cleaning sometimes works, cooler replacement often the real fix. Neglected → cascades into DPF stress.
13. [KNOW] **P2002 / P2463** DPF efficiency/soot accumulation — urban-cycle saturation, failed regens, substrate damage after repeated forced regens, or post-dieselgate-software behavior changes. Cost spread £220 (clean) to £2400 (replace). Diagnose root (thermostat stuck open blocking regen temps is a classic hidden cause!) before blaming the filter.
14. [KNOW] **P17xx DSG family** — mechatronics/adaptation codes. VERIFIED workshop wisdom: fresh DSG oil + adaptation basic-settings resolve many before any hardware. Mechatronic condemnation is the expensive LAST step, not the first.
15. [KNOW] **P0300-P0304** misfires — TSI/FSI coil-pack failure is the classic (heat-cycled coils, infamous red-tops); swap coils between cylinders to see if the misfire follows before buying parts. Then plugs, then injectors/compression. Catalyst-damaging misfire flashes the MIL — stop driving hard immediately.
16. [KNOW] **P2187** lean at idle specifically = vacuum leak — PCV diaphragm (the EA888 valve-cover unit — the same cascade that kills rear main seals), intake gaskets, cracked vacuum lines. Contrast with lean-at-all-loads.
17. [KNOW] **P0101/P0100** MAF range/performance — verify with live MAF g/s at idle+load vs spec before replacing; dirty sensor vs real air leak vs failing pump all mimic.
18. [KNOW] **P0420** cat efficiency below threshold — often the downstream-O2-reading consequence of upstream problems (misfires, oil burning) killing the cat. Fix the cause, not just the cat.

## 2. Opel/GM-era high-frequency codes — verified causes & fixes

19. [KNOW] **P0011/P0014** camshaft timing over-advanced (Z16XER/Z18XER/A16XER 1.6/1.8 Ecotec + A14XER/A14NET) — PRO TIP VERIFIED: very often the cam-adjuster SOLENOID valves on the head or their fine oil filter screens, NOT the adjusters themselves. Diagnosis trick: swap intake/exhaust solenoids — if the fault code moves side, it's the solenoid. If adjusters rattle every cold start, they're worn (replace with chain kit). Sludge from stretched oil intervals is the root killer.
20. [KNOW] **P0171** lean on 1.4 Turbo (A14NET/A14NEL/B14NET) — the known crankcase-ventilation/PCV failure (integrated in valve cover, same disease family as VAG) plus intake gasket leaks. Verify fuel trims idle-vs-2500rpm split before buying.
21. [KNOW] **P0299** on 1.6T A16LET/A16LES (Astra J OPC/Insignia) — verified: intercooler hose splits after heat cycles, diverter valve failure common at 60-80k miles, boost control solenoid. Live-data verification values: boost target vs actual at 3500rpm WOT expect 175-200kPa; DV position should snap closed (0%) on lift-off.
22. [KNOW] **P0087/P0191** rail pressure on CDTI diesels — real causes: injector leak-off excess (worn injectors returning too much fuel — leak-off test is THE discriminator), weak pump, rail sensor drift, fuel-filter starvation. Never condemn the pump before a leak-off measurement.
23. [KNOW] **P0670-P0674** glow plugs on 1.7 CDTI (B13DTE/A17DTR): VERIFIED fleet pattern — all 4 fail within the same mileage window, replace all at once, not one at a time.
24. [KNOW] **P2002** on 1.7 CDTI — DPF particularly sensitive to short-trip use; forced regen + driving-pattern correction before hardware.
25. [KNOW] **P0100/P0101** MAF on 1.7 CDTI — fouled by crankcase-ventilation oil mist. VERIFIED numbers: idle MAF should read roughly 20-24 g/s; under 15 = dirty or dead sensor. Symptoms: flat spot + black smoke under acceleration.
26. [KNOW] **P0597** thermostat heater control circuit (open) — common on A14NET/GM small blocks; the electronically-heated thermostat fails open, engine runs cold, fuel economy drops, regen temperatures never reached on diesels. Cheap part, big cascade.
27. [KNOW] Corsa-D EPS warning: VERIFIED trap — heavy steering + lamp is frequently LOW SUPPLY VOLTAGE, not the column motor. Load-test battery/charging before condemning the expensive column.
28. [KNOW] **P0016** on Ecotec timing chains: cold-start rattle 1-2s = chain warning; interference engine — skipped tooth bends valves. Oil condition+interval determines chain life; oil viscosity/approvals matter.
29. [KNOW] PSA-era alert (Corsa F/Crossland/Grandland/Astra L — verified): the 1.2 PureTech WET BELT degrades and sheds material that BLOCKS THE OIL PICKUP STRAINER — belt problem becomes engine-death problem. First question on any post-2017 PSA-era Opel: belt service history. Early warning: oil-pressure light flicker at idle. P0011 on PureTech = critical, not casual.
30. [KNOW] EP6/EB2 PSA engines inherit Peugeot/Citroen code behavior — treat PSA-era Opels with PSA references, not GM ones (era rule again).

## 3. Cross-cutting verification techniques (the "read it right" layer)

31. [KNOW] Requested-vs-actual is the universal verification pattern: boost (requested vs actual pressure), rail pressure, EGR position, flap position, cam phase angle. Every actuation code has a live-data pair — compare them under the conditions in the freeze frame.
32. [KNOW] Actuator/output tests isolate electrical-vs-mechanical: command the diverter valve/EGR/flap motor/N75 directly and watch/hear the response + position feedback. Dead command response + good wiring = mechanical seizure.
33. [KNOW] Smoke/pressure testing beats guessing on boost/vacuum leaks: pressure-test the charge system at ~1 bar with soapy water or smoke machine — the leak you can't hear is the one that costs a turbo misdiagnosis.
34. [KNOW] Intermittent electrical faults: wiggle-test under live-data watch; voltage-drop test connectors under load (not just continuity — continuity passes a single surviving strand of wire, voltage-drop catches it).
35. [KNOW] After-repair verification: full drive cycle matching the freeze-frame conditions + re-scan + readiness check. "Code didn't return after the same drive that triggered it" is the only real proof of fix.
36. [REQ] Never erase codes before recording freeze frame + occurrence counters — that's diagnostic evidence you're destroying.

## 4. Quick-reference pairing table (highest-value hits)

37. [KNOW] VAG: P2015=linkage kit · P0299=leak test first · P0016@1.2/1.4TSI=chain NOW · P0401=EGR cooler carbon · P2002=regen root-cause (thermostat!) · P17xx=oil+adaptations first · P0300=swap coils · P2187=PCV vacuum leak.
38. [KNOW] Opel: P0011=swap solenoids trick · P0171@1.4T=PCV valve cover · P0299@1.6T=DV+hoses, verify 175-200kPa · P0087=leak-off test before pump · P067x=replace all 4 glow plugs · MAF@1.7CDTI=20-24g/s idle spec · Corsa EPS=battery first · PureTech belt=oil pickup death watch.

[COMPAT]
- Platform/era gating: `automotive-vag.md` / `automotive-opel.md`; the tricks/service procedures: `automotive-tricks.md`; protocol layer: `automotive-diagnostics.md`.
[REFS]
- VAG code analysis: https://vagpulse.com/guides/common-vag-fault-codes
- VW tables: https://www.asfmotors.es/en/obd2-fault-codes/volkswagen/ + https://www.enginefinder.co.za/blog/problems/vw-error-codes-problems/
- Opel guides: https://www.obdoktor.com/en/brand/opel/ + https://obdllm.com/en/blog/opel-vauxhall-common-dtc-codes/
