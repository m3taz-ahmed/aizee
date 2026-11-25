[TECH] automotive-security
[OBJ] Vehicle security research knowledge: attack surfaces, published attack classes, regulatory framework (ISO/SAE 21434, UN R155/R156), pentest methodology + tooling, defensive countermeasures. DEFENSIVE framing — analysis, detection, and hardening only. Never produce theft playbooks, immobilizer-bypass procedures, odometer fraud, or key-cloning instructions.
[SRC] Researched 2026-11-25. Evidence: Ken Tindell CAN-injection investigation, awesome-vehicle-security list, Fraunhofer gallia.

## 1. Threat landscape — published attack classes (what defenders must know)

[RULES]
1. [KNOW] CAN injection theft (CVE-2023-29389, verified — Ken Tindell/Canis Labs + CAN in Automation paper): thieves reach a CAN segment through body panels (headlight wiring!), inject frames spoofing keyless-entry/immobilizer validation messages, unlock+start car in <2 min. Root cause: perimeter-defense architecture — interior bus trusts any frame, no authentication. JBL-speaker-cased theft devices sold on dark web for many brands. Defense direction: message authentication (MAC/counter+CRC hardening), zone isolation, intrusion detection on physical-layer anomalies, encrypted diagnostics.
2. [KNOW] Relay attack on passive keyless entry (PKE): two attackers relay the key fob's LF/RF challenge-response over distance — car thinks key is present. Defenses that work: UWB with secure distance bounding (new gen keys), motion-sensor key sleep, faraday storage; aftermarket: disable PKE or add PIN-to-drive.
3. [KNOW] Rolling-code attacks (Samy Kamkar RollJam class): jam+capture two sequential codes, replay first — broken on old KeeLoq-style systems; modern systems use encrypted challenge-response immobilizers making replay ineffective. Lesson for defenders: fixed/rolling codes are not authentication.
4. [KNOW] Remote-compromise chain (Miller/Valasek Jeep 2015 — the canonical research): cellular → infotainment (Uconnect) exploit → CAN rewrite through head unit → powertrain control. Result: 1.4M vehicle recall, mandatory lessons: infotainment-CAN gateway isolation, signed firmware, carrier-level blocking.
5. [KNOW] Tesla/Keen Security 2016-17: malicious hotspot → webkit exploit in MCU → CAN bus access ("free-fall" wireless-to-CAN). Tencent/Keen BMW + Tesla follow-ups. Pattern: the infotainment/TCU is the beachhead; the internal bus is the prize.
6. [KNOW] OBD dongle abuse: insurance/fleet dongles = remote CAN injection endpoints (compromised telematics = compromised fleet). Bluetooth OBD dongles with default PINs were historically hijackable.
7. [KNOW] Diagnostic-protocol attacks: seed/key brute-force (short keys, no rate limit on old ECUs), 0x36 lockout bypass via power cycling, routine-control abuse (erase/reflash), programming-session hijack, extraction of seed/key algorithm binaries from flash then offline keygen. Defenses: proper crypto SA, attempt counters persistent across power cycles, rate-limiting, session timeout.
8. [KNOW] Sensor spoofing: ABS wheel-speed injection, tire-pressure RKE manipulation, ADAS camera/radar deception (projected lanes, GPS spoofing on nav-dependent logic), LiDAR echo fabrication — research-demonstrated; ADAS trust in raw sensor data is the weakness.
9. [KNOW] Key cloning/immobilizer systems: transponder crypto generations — fixed-code (cloneable trivially) → crypto KeeLoq/Hitag2 (broken published) → AES-class modern (Megamos AES, Toyota G/H chips). Hitag2/VW IMMO weaknesses academically documented — do not operationalize; the defensive takeaway is inventory and upgrade paths.
10. [KNOW] Odometer fraud: mileage stored redundantly (cluster EEPROM + ABS/BCM/engine modules on many cars) — single-module rollback detection via mismatched copies + service records + wear. Fraud is a crime; the knowledge matters for buyers/inspectors.
11. [KNOW] Supply-chain/aftermarket: cracked tuning software and warez flash files = active malware vector (verified: brand-impersonation GitHub orgs Nov 2026 — UniCON-NECT/IE-Flash-Wizard/034-SPI). Never install pirated tuning suites on a machine that touches real cars or customer data.

## 2. Regulatory & standards framework

12. [KNOW] ISO/SAE 21434:2021 — cybersecurity engineering lifecycle: TARA (threat analysis & risk assessment) → cybersecurity concept → secure design/dev/integration/validation → operations/incident response → decommissioning. Risk = impact × attack feasibility (elapsed time/expertise/knowledge/equipment/opportunity). Evidence: UL/SIS TARA practice + spilma guide.
13. [KNOW] UN R155 (CSMS — cybersecurity management system) + R156 (SUMS — software update management): type-approval legal requirement in EU+Japan+Korea etc. for new types since 2022/2024. R155 doesn't mandate ISO 21434 by force but it's the de-facto evidence framework. ISO 24089 software-update engineering completes the trio.
14. [KNOW] AUTOSAR crypto stack: SecOC (secured onboard communication — MAC-truncated freshness-authenticated frames), TLS/dTLS for DoIP/Ethernet, HSM anchoring on AURIX TC3xx. This is the OEM defensive answer to CAN-injection class attacks.
15. [KNOW] ISO 26262 (functional safety) interacts: security mechanisms must not break safety (e.g., authentication latency on brake frames) — safety/security co-engineering is the current frontier.

## 3. Pentest methodology & tooling (professional practice)

16. [USE] Methodology order: recon (OBD scan, module inventory, bus topology) → passive capture (baseline traffic model) → active enumeration (UDS service scan, DID discovery, session matrix, security-access analysis) → protocol fuzzing (malformed ISO-TP, boundary payloads) → routine/control audit → firmware extraction for static analysis → report with reproducible artifacts. Everything reproducible = everything logged.
17. [USE] `Fraunhofer-AISEC/gallia` — the reference open automotive pentest framework (Apache, actively maintained, SecForCARs/ATLAS-L4 funded): UDS scanners (services/DIDs/sessions/seed-key analysis), dump/fuzz primitives, transport URIs (isotp://can0?src_addr&dst_addr&padding), reproducible logging artifacts. Rated "most robust and dependable" UDS implementation in SAE 2024-01-2799 comparative fuzz study.
18. [USE] CaringCaribou — the classic "nmap for cars": UDS discovery, fuzz, dump modules; CANToolz — modular black-box CAN analysis framework; CANalyzat0r — proprietary protocol security analysis kit. All SocketCAN-based.
19. [USE] ICSim + UDSim (OpenGarages/zombieCraig) — safe training environments on vcan; `can-utils` (cangen/cansend/cansniffer/canplayer) for traffic work; Scapy automotive layers (CAN/ISOTP/UDS/GMLAN/DoIP) for custom protocol scripting; TruckDevil for J1939/heavy vehicles.
20. [USE] Analysis benches: SavvyCAN (live RE), cabana (comma — DBC authoring/diffing against drives), PlotJuggler (+CAN plugin) for time-series RE. can-explorer/canarchy for visualization/automation.
21. [USE] Hardware note: panda (comma) does CAN/GMLAN/SWCAN + has a hardware safety model (openpilot controls-authorization) — it's itself a lesson in defensive design. Macchina, CANable for cheaper paths; Vector/PCAN/Kvaser in professional labs.
22. [REQ] Engagement discipline: written authorization (vehicle owner), isolated bench preferenced over live vehicle, never test safety-critical injection on public roads, document power/network state before destructive tests, responsible disclosure to OEM PSIRT (most now run coordinated-disclosure or bug-bounty: GM/Tesla/etc.).
23. [PROHIBIT] Producing step-by-step theft enablement (immo bypass procedures, key cloning, CAN-injection frame recipes for stealing specific models, odometer rollback procedures, CP/SFD circumvention). Frame everything as: how it works conceptually → how to detect it → how to defend.

## 4. Defensive countermeasures knowledge

24. [KNOW] Frame authentication: VAG MQB CRC8+rolling counter is message INTEGRITY not authentication (no secret — defeated by RE of the algorithm, evidence ronaldocordeiro's MQB CRC finder exists publicly). Real defense = MAC with secret keys (SecOC) — additive trailing MAC bytes on FD frames or dedicated auth frames.
25. [KNOW] Network segmentation: central gateway with filtering/IDS, separating infotainment from powertrain domains, firewall rules on diagnostic routing. Post-2015 OEM redesigns implemented exactly this.
26. [KNOW] IDS approaches: frequency/timing analysis (frames arrive on schedule — injected extras break periodicity), payload-plausibility cross-checks, physical-layer fingerprinting (voltage-level transmitter fingerprinting research), entropy monitoring.
27. [KNOW] SFD/secure-diagnostic trend: OEMs closing open-write diagnostics behind account-bound tokens (VAG SFD, FCA SGW, Mercedes seed-key hardening) — the industry-wide answer to unauthorized modification AND theft-enabling diagnostics. Aftermarket access flows through authorized paid channels (legitimate by design).
28. [KNOW] Owner-level defense checklist: PKE key in faraday pouch / motion-sleep keys, garage+lighting, OBD port lock/relocators in theft-hotspot regions, steering locks as visible deterrent, tracker (independent power), immobilizer aftermarket with no-OG-keyhole wiring, firmware updates applied (OEM security campaigns), PIN-to-drive where offered.
29. [KNOW] Fleet/workshop defense: dongle inventory + firmware management, J2534/tooling access control, no pirated software anywhere near the workshop network (verified malware vector), customer-data hygiene (diagnostic reports contain VINs).

[COMPAT]
- Protocol detail in `automotive-diagnostics.md`; firmware internals in `automotive-ecu-internals.md`.
[REFS]
- Ken Tindell CAN injection: https://kentindell.github.io/2023/04/03/can-injection/
- CAN-injection CiA paper: https://can-cia.org/fileadmin/cia/documents/publications/cnlm/june_2023/cnlm_23-2_p20_the_can_injection_attack_ken_tindel_canis_automotive_labs.pdf
- awesome-vehicle-security: https://github.com/jaredthecoder/awesome-vehicle-security
- gallia: https://github.com/Fraunhofer-AISEC/gallia
- ISO 21434/R155 guide: https://www.spilma.com/en/guides/iso-21434-unece-r155-r156-automotive-cyber
