[TECH] automotive-wiring
[OBJ] Practical vehicle-electrics craft: reading wiring diagrams (VAG current-flow + DIN standards + GM/Opel conventions), terminal designations, wire colors/gauges, connector systems, correct harness repair doctrine, fault-tracing methodology. The hands-on electrical skill layer.
[SRC] Researched 2026-11-25 fourth pass. Verified: DIN 72552 via Motor Magazine euro-wiring guide + vehicleservicepros "Delving into DIN", VW current-flow reading guide (eva2/compu85 SSP mirror), VW SSP 871003 wiring-harness repair manual (canonical VAG repair doctrine), DIN 47002 color codes.

## 1. DIN 72552 terminal designations — the German circuit language (verified)

[RULES]
1. [KNOW] Terminal numbers describe the CIRCUIT TYPE, not the wire — a single wire can connect terminals of different designations at each end. Standardized by law across European manufacturers (DIN 72552): same number = same circuit meaning on every Euro car. Prefix "KL" (Klemme) in formal docs.
2. [KNOW] The core set: **30** = battery positive DIRECT (always live) · **30a** = battery+ protected/second · **15** = switched ignition+ (live in ON/RUN) · **15a** = ignition output protected · **31** = battery negative/ground DIRECT · **31b** = switched ground (via switch/relay) · **50** = starter control (live in CRANK — what hits the starter solenoid S-terminal) · **X** = load-reduction circuit (powered during run/initial key-up only — heavy loads like blower/reheated screens so the starter gets priority during crank).
3. [KNOW] Lighting/signaling: 49/49a flasher in/out, L/R turn outputs, 54 brake lights, 56/56a/56b headlight high/low, 58/58L/58R tail/license-plate, 61 alternator charge-warning lamp circuit. Ignition legacy: 1/4 coil low/high voltage, 17/19 glow-plug start/preglow.
4. [KNOW] Relay pins standard: 85/86 = coil, 30 = common contact input, 87 = NO output, 87a = NC. Same relay numbering worldwide — a relay pinout is readable without a datasheet.
5. [KNOW] Modern ECU reality: modules use manufacturer pin numbers (T80/1 style connector-pin refs), but the DIN designations survive on classic power/ground/starter/lighting circuits and all relay/fuse-box logic — you still diagnose "no terminal-15 feed" the same way on a 2024 car.

## 2. Wire colors — DIN 47002 German abbreviations (verified)

6. [KNOW] German color codes on diagrams: **sw**=black(Schwarz) · **bl**=blue(Blau) · **br**=brown(Braun) · **gn**=green(Grün) · **gr**=gray(Grau) · **or**=orange · **rs**=pink(Rosa) · **vi**=purple(Violett) · **rt/ro**=red(Rot) · **tk**=turquoise(Türkis) · **ws**=white(Weiss) · **ge**=yellow(Gelb).
7. [KNOW] Tracer notation: "ro/ws" = red wire with WHITE tracer stripe (base/stripe order). Every VAG diagram carries its own color key — production changes mean a specific car's colors CAN differ from the printed diagram; trust the connector+pin position over color when they disagree.
8. [KNOW] GM/Opel era convention differs: English abbreviations (BK/BN/WH/GY/RD…) or GM circuit NUMBERS printed on the wire + gauge — GM diagrams are circuit-number-centric (a wire keeps its circuit number through splices/connectors — powerful for tracing). Global-A schematics: component locator + connector views (C-numbers for connectors, S-numbers splices, G-numbers grounds).

## 3. Reading VAG current-flow diagrams (the skill that unlocks ElsaWin/erWin docs)

9. [KNOW] Current flows TOP (positive/fusebox) to BOTTOM (ground) — these are functional current-flow diagrams, NOT harness-routing diagrams. Horizontal lines at top = fusebox buses (terminal 30/15/X feeds). Bottom line = ground bus.
10. [KNOW] Current tracks numbered along the bottom: a wire ending in a numbered square box continues at that track number elsewhere — follow by number, not by page position. The diagram index cross-references components to tracks.
11. [KNOW] Thin black lines aren't always wires: when showing current to ground they can be mechanical connections (a switch threaded into the engine block grounding through the block). Read the ground-point annotations: circled numbers keyed to a ground-point location list in the manual.
12. [KNOW] Component letter codes: **J** = control units + relays (J519 = BCM, J533 gateway, J623 engine), **F** = switches/senders-contacts, **V** = motors/actuators, **G** = sensors, **N** = solenoid valves/injectors (N75 boost, N80 purge), **S** = fuses (SA/SB/SC per fusebox location), **T** = connectors — T10 = 10-pin, T10e = variant e, T2/3 = pin 3 of 2-pin connector, **Z** = heating elements, **E** = manual switches (older), **A** = assembly/cluster.
13. [KNOW] Connector pin notation "T20/15" = 20-pin connector, pin 15. Connector-end views in the manual show pin layout — ALWAYS verify which way the drawing faces the connector (wire-entry side vs contact side — mirrored layouts are a classic misread).
14. [KNOW] Internal fusebox paths count: the feed may go through internal bus bars/bridges — a fuse can be good while the box-internal path is broken (melted fusebox is a real MQB-era fault). Measure at the fuse OUTPUT leg, not just continuity across the fuse.
15. [KNOW] erWin/ElsaWin = official VAG current-flow docs source; Opel-era GM uses TIS/service-info schematics; aftermarket: Haynes/manuals PDFs float around vaglinks-type archives.

## 4. Wire sizing & circuit math

16. [KNOW] Metric cross-sections in mm²: 0.35/0.5/0.75/1.0/1.5/2.5/4/6/10+ (AWG equivalents roughly 22/20/18/17/15/13/11/9/7). Signal/sensor wires are typically 0.35-0.5; loads 0.75-2.5; power distribution 4+.
17. [KNOW] Sizing rule: ampacity by cross-section AND insulation temperature class AND bundling AND run length (voltage drop). Engine-bay wire must be rated 125°C+ class. Quick reality table: 0.5mm²≈8-11A chassis harness short runs, 1.5mm²≈15-20A, 2.5mm²≈25A, 4mm²≈32A, 6mm²≈40A — derate in bundles/heat.
18. [KNOW] Voltage-drop sizing matters more than ampacity for long runs: target <3% drop on power feeds, <0.1V on sensor grounds. A "thick enough not to melt" wire can still be too thin to WORK (classic aftermarket-failure: pump runs slow through undersized wire).
19. [REQ] Fuse sizing protects the WIRE not the device; fuse at the power-source end (within ~30cm for aftermarket adds). A fuse at the far end protects nothing against shorts upstream.

## 5. Diagnostic technique — measuring like a professional

20. [REQ] Voltage-drop testing is THE power-side method: measure ACROSS a wire/connector/ground path with the circuit UNDER LOAD — >0.2V on a power feed or >0.1V on a sensor ground = excessive resistance, regardless of how good continuity looked. Continuity testing passes a single surviving copper strand; voltage drop catches it (verified workshop doctrine).
21. [REQ] Never break insulation to probe unless you repair it properly — back-probe connector rears with correct pin probes, or use breakout boxes. Incandescent test lamps load the circuit (good for power circuits, DANGEROUS on ECU outputs) — use LED test lights/high-impedance DMM on module circuits. Never probe airbag/pyrotechnic circuits with generic meters/lamps.
22. [KNOW] Pin drag test: terminals lose spring tension → intermittent contact with perfect continuity at rest. Feel insertion/withdrawal drag or compare with a known-good terminal of same size. Terminal fretting corrosion = microscopic vibration wear — shows as intermittent sensor dropouts, fixed by terminal replacement not cleaning.
23. [KNOW] Binary-search the break: with the diagram, measure at the electrical MIDPOINT of the suspect run (connector inline) — halves the search space each step. Don't start stripping harness wrap at random.
24. [KNOW] The connector-first rule: ~80% of harness faults live at connectors (tension loss, corrosion, water ingress, backed-out pins, broken wire AT the crimp from flexing). Inspect connectors in the fault path BEFORE the wire runs.
25. [KNOW] Water finds low points: connectors at sill/door bottoms, tailgate boots, under-battery trays corrode first. Green verdigris = copper corrosion wicking UP the wire under insulation — cut back beyond visible damage or it returns.

## 6. Connector systems & correct handling

26. [KNOW] Families to recognize: VAG/TE = Junior Timer/JPT, MCP/MQS contact systems, HPF/ACP variants; GM = Metri-Pack + Weather Pack; sealed Deutsch DT/DTM/DTP in harsh zones; Molex/MX150 body. Each contact system has its own release geometry — the extraction tool is system-specific (VAG kits VAS1978/35 type).
27. [KNOW] Opening order (the universal discipline): (1) unlock the secondary lock FIRST — CPA/TPA terminal-position-assurance slider or the connector's locking lever — terminals will NOT release with secondary lock engaged; (2) release the primary tang with the correct tool inserted from the contact face along the terminal; (3) push the terminal slightly FORWARD first to unload the tang, then insert the release tool, then pull the wire gently. Forcing = bent tangs = scrap connector.
28. [KNOW] Yellow connectors = airbag/pyrotechnic harnesses on German cars — treat with the safety doctrine (battery disconnect + wait). Orange cables/connectors = HIGH VOLTAGE on hybrids/EVs — untrained hands off.
29. [KNOW] Connector servicing: contact cleaner + proper micro-brushes, never abrasive files on plated contacts (gold/tin plating removal accelerates corrosion). Dielectric grease belongs on the SEAL/outer mating surfaces to exclude moisture — packing it between contacts is contested; thin film on pins is accepted practice in moist environments.

## 7. Harness repair doctrine — VAG VAS 1978 canonical rules (verified VW SSP 871003)

30. [REQ] OEM repair method = CRIMP, not solder: the approved repair is the yellow-shaft repair wires with pre-crimped contacts (cross-section matched, part-numbered in the VAS 1978/1978A kit), crimped with the correct pliers+positioner to a gas-tight deformation, sealed with adhesive-lined heat shrink. Solder wicks up strands and vibration-hardens the wire → fatigue break at the joint edge. Crimp is the OEM answer everywhere in moving/ vibrating harnesses.
31. [REQ] Repair placement rules: repairs go in straight, low-flex sections — NEVER in flexing zones (door boots, engine-to-body movement spans, steering column tilt paths). One repair per section — don't stack splices. Stagger multiple-wire repairs so the bulges don't concentrate at one point.
32. [REQ] CAN bus repair rules: twisted pair MUST stay twisted — untwist the minimum needed for the joint (a few cm max), keep both conductors equal length, keep repair points away from connector ends. CAN FD tolerates less sloppiness than classic CAN — treat every bus repair as suspect if comms faults persist.
33. [PROHIBIT] No repairs on shielded coax/video/antenna cables (MOST fiber is non-repairable splice-wise in field) — replace the run. No scotch-locks/T-taps anywhere — corrosion time bombs that also damage the host wire strands. No PVC electrical tape as permanent protection — hardens and unwraps; use cloth harness tape (OEM fleece type) or adhesive-lined shrink.
34. [KNOW] Airbag/pyrotechnic wiring: manufacturer-specific doctrine — many OEMs PERMIT repair only with the approved crimp kit (exact VAG position per SSP), others mandate harness replacement on pyro circuits. VERIFY the specific OEM rule before touching; wrong repairs in restraint systems are a liability nightmare.
35. [KNOW] Replacement connector strategy: OEM repair kits (connector shell + crimp pigtails) beat junkyard cut-offs; when using donor pigtails, match cross-sections, leave working length, and replace any terminal showing corrosion/discoloration rather than reusing it.
36. [KNOW] Rebuild finishing: re-loom with correct conduit/braided sleeve/fleece tape matching the zone (heat/abrasion/moisture), restore grommets and clips in original positions — harnesses fail where they're left rubbing because a clip wasn't refitted. Harness routing geometry IS part of the repair.

## 8. Retrofit/add-on wiring craft (ties into the tricks playbook)

37. [KNOW] Feeding retrofits: pick correct rail by DIN logic — permanent 30 for memory/alarm functions, 15 for ignition-dependent, X for heavy loads. Fuse within 30cm of tap point. Use fuse-taps (add-a-circuit) properly oriented (input side correct) or OEM repair wires into fusebox spare positions — never wrap-around-fuse-leg hacks.
38. [KNOW] Grounding adds: use documented ground points (the circled-number factory points) — sand/paint a fresh point properly with star washer + protectant if adding. Sharing high-current ground points with sensitive sensor grounds invites noise faults.
39. [KNOW] Signal integrity for retrofits: keep added power wires away from sensor runs, cross at 90° where unavoidable; twist any added pair carrying balanced signals; shield+ground one end only for audio/camera runs.
40. [KNOW] The verification loop for any wiring work: circuit function test under full load + voltage-drop measurement across every new joint + wiggle test + thermal check after 10min operation. Intermittents are born in skipped verification.

[COMPAT]
- Electrical system context: `automotive-core.md` §1/§5/§6; module-level retrofits: `automotive-tricks.md` §4; network protocols over these wires: `automotive-diagnostics.md`.
[REFS]
- DIN terminal decoding: https://www.vehicleservicepros.com/service-repair/diagnostics-and-drivability/article/21236478/delving-into-din
- Euro diagram reading: thesamba.com Motor Magazine euro-wiring PDF
- VW current-flow reading: https://eva2.compu85.net/eva2/EE01/ch3.1.html
- VAG harness repair SSP 871003: vaglinks.com/docs/ssp/VWUSA.COM_SSP_871003_Wiring_Harness_Repair.pdf
