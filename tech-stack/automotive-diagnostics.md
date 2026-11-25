[TECH] automotive-diagnostics
[OBJ] Diagnostic protocols (OBD-II, UDS, KWP2000, KW1281, ISO-TP, TP2.0, DoIP, SOVD), data formats (DBC, ODX, A2L, FRF), DTC structure, J2534/hardware interfaces, and the open-source diagnostic toolchain. Load after `automotive-core`.
[SRC] Researched 2026-11-25 — repo evidence in `temp/auto-research-2026-11-25/candidate-ledger.md`.

## 1. OBD-II (legislated emissions diagnostics — SAE J1979 / ISO 15031)

[RULES]
1. [KNOW] OBD-II is emissions-only, standardized, and shallow: ~10 modes/services. It is NOT the same as manufacturer-specific enhanced diagnostics (UDS/KWP) — a generic ELM327 scan reads a tiny fraction of what the car knows.
2. [KNOW] Services: 01 current data (PIDs: 0C rpm, 0D speed, 04 load, 05 coolant, 0F intake air, 11 throttle, 0106+ fuel trims…), 02 freeze frame, 03 stored DTCs, 04 clear DTCs+reset monitors, 05/06 O2/monitor test results, 07 pending DTCs, 08 evaporative control, 09 vehicle info (VIN mode 0902, CALID, CVN), 0A permanent DTCs.
3. [KNOW] DTC structure: letter (P powertrain, B body, C chassis, U network) + digit 0 (generic/ISO) or 1 (manufacturer) + 3 hex-ish digits. P0301 = generic powertrain cyl-1 misfire. P0xxx generic, P1/P2/P3xxx mixed manufacturer. U0121 = lost comms with ABS.
4. [KNOW] Readiness monitors (mode 01 PID 01/41): continuous (misfire/fuel/comprehensive) + non-continuous (cat, O2, EVAP, EGR, secondary air). After clearing DTCs they reset to incomplete — inspections fail until drive cycles complete.
5. [KNOW] Freeze frame = snapshot of PID values at the moment the DTC set — the first clue in diagnosis, always read before clearing.
6. [KNOW] OBD pinout (J1962): 4 chassis gnd, 5 signal gnd, 6 CAN_H, 14 CAN_L, 7 K-line, 15 L-line, 16 battery+. GM SWCAN single-wire on pin 1 (GMLAN-LS) in some; Ford MS-CAN on 3/11. Never assume — verify per model.
7. [KNOW] ELM327 = the ubiquitous AT-command interpreter chip (almost always clones). `ATZ` reset, `ATE0` echo off, `ATL0` linefeeds off, `ATS0` spaces off, `ATH1` headers on, `ATSP0` auto protocol, then hex service+PID e.g. `010C` → response `41 0C xx xx`. RPM = (256A+B)/4. Clones often lie about version (v1.5+ = usually v1.4 fakes), drop frames, can't do MS-CAN/SWCAN.

## 2. UDS — Unified Diagnostic Services (ISO 14229) — the modern standard

8. [KNOW] UDS is service-oriented request/response over any transport (CAN ISO-TP dominant, DoIP growing, LIN/FlexRay rare). Positive response = service+0x40; negative = 0x7F + orig service + NRC. Example: `22 F1 90` (ReadDataByIdentifier VIN) → `62 F1 90 <VIN bytes>`.
9. [KNOW] Core services: 0x10 DiagnosticSessionControl (01 default, 02 programming, 03 extended — most interesting things need extended), 0x11 ECUReset, 0x27 SecurityAccess (seed/key: odd subfn=request seed, even=send key), 0x28 CommunicationControl, 0x3E TesterPresent (keep session alive, 00 or 80 suppressPosRsp), 0x22 ReadDataByIdentifier (DID 2 bytes, e.g. F190 VIN, F187 label, F189 software version), 0x2E WriteDataByIdentifier, 0x2F InputOutputControlByIdentifier, 0x31 RoutineControl (01 start/02 stop/03 requestResult — erases, adaptations, actuator tests live here), 0x19 ReadDTCInformation (02 reportByStatusMask, 0A all), 0x14 ClearDiagnosticInformation, 0x34 RequestDownload / 0x35 RequestUpload / 0x36 TransferData / 0x37 RequestTransferExit (firmware flashing quartet), 0x85 ControlDTCSetting.
10. [KNOW] NRCs that matter: 0x10 generalReject, 0x11 serviceNotSupported, 0x12 subFunctionNotSupported, 0x21 busyRepeatRequest, 0x22 conditionsNotCorrect, 0x24 requestSequenceError, 0x31 requestOutOfRange, 0x33 securityAccessDenied, 0x35 invalidKey, 0x36 exceedNumberOfAttempts, 0x37 requiredTimeDelayNotExpired, 0x78 responsePending (then real response follows), 0x7E/7F subFn/service not supported in active session.
11. [KNOW] SecurityAccess seed/key: ECU sends random seed (2–16 bytes); tester computes key with OEM-secret algorithm and returns it. Algorithms leak per-family: VAG SA2 scripts are embedded as bytecode in the ODX flash container (evidence: bri3d/sa2_seed_key implements the interpreter); gmlan/GM have simple XOR/rotate schemes; strong modern ECUs use proper crypto/HSM.
12. [KNOW] DIDs are manufacturer-defined except a few legislated (F190 VIN). VAG UDS adaptation/coding data objects use IDE-dataset names (e.g. IDE00001) read/write with 22/2E — what VCDS exposes as "adaptation channels" on UDS cars.
13. [KNOW] Addressing: physical (1:1, specific ECU) vs functional (1:n broadcast, 0x7DF legacy OBD or manufacturer). VAG TP2.0/CAN uses fixed pairs (engine 0x7E0/0x7E8 legacy KWP-style), UDS-on-CAN modules respond on 0x7E8+n or manufacturer-specific. DoIP uses logical 16-bit addresses with routing activation.
14. [KNOW] Diagnostic session timing: S3 timeout (~5s) drops back to default session unless TesterPresent keeps it alive. Programming sessions are dangerous: interrupted flash = bricked ECU; power supply stability is mandatory.

## 3. Legacy VAG protocols (pre-UDS era)

15. [KNOW] KW1281 (VAG proprietary K-line protocol): 5-baud address-keyed init (address byte bit-banged at 5 baud, ECU responds with sync bytes 0x55 + key word), then byte-packet protocol with complement block counters. Still used on many 1996–2005ish VAG modules incl. clusters. Evidence: implemented in rust in `JoeeDeveloper/OpenDiag` + `gallia`'s vendor docs.
16. [KNOW] KWP2000 (ISO 14230): services similar to UDS but different numbering: startDiagnosticSession 0x10, readDataByLocalIdentifier 0x21, readDataByCommonIdentifier 0x1A, readMemoryByAddress 0x23, securityAccess 0x27, writeDataByLocalIdentifier 0x3B, inputOutputControl 0x30, startRoutine 0x31. Fast-init (25ms low/high pattern) or 5-baud slow init. VAG KWP-2000 TP2.0 rides on CAN pre-UDS.
17. [KNOW] VAG TP2.0 (Transport Protocol 2.0 on CAN): proprietary VW transport pre-ISO-TP — channel-based with dynamic connection setup (opcodes 0xA0-0xA3 etc.), broadcast CAN IDs 0x200/0x201 for setup, then per-module IDs. Implemented in OpenDiag; documented in VW community wikis.
18. [KNOW] VAG "measuring blocks" (MVB) on KW1281/KWP cars: group numbers 000–255 with 4 fields each; ECU supplies raw values + type hints (temp/rpm/pressure…) — VCDS scales using label files. Group 000 = 10 unscaled fields. UDS cars replace this with DIDs/IDE datasets ("advanced measuring values").

## 4. Transport layers

19. [KNOW] ISO-TP (ISO 15765-2): segmentation of >8-byte payloads over classic CAN. Frame types: single (SF, PCI nibble 0), first (FF, len ≤4095 or extended), consecutive (CF seq nibble), flow control (FC: CTS/WT/OVFL + block size + STmin). Normal addressing: ID carries the target; extended addressing adds a target byte; 29-bit uses J1939-style priority+PF+PS. Padding usually 0xAA/0x55/0x00 per OEM.
20. [KNOW] Common IDs: legislated OBD 0x7DF functional, 0x7E0→0x7E8 engine physical (11-bit). VAG UDS-on-CAN often uses same scheme; some modules on extended IDs. DoIP edge nodes then route into vehicle networks.
21. [KNOW] DoIP (ISO 13400): UDS payloads over TCP/UDP automotive Ethernet, port 13400. Entity discovery (UDP broadcast vehicle announcement/identification), routing activation (required before diagnostics, carries source logical address + activation type), then diagnostic messages over TCP. Modern VAG/BMW/Mercedes diagnosis path; TLS variant in newest (secure DoIP).
22. [KNOW] SOVD (ISO 17978, 2024+): service-oriented vehicle diagnostics — REST/HTTP+JSON successor model for HPC/software-defined vehicles. Eclipse OpenSOVD (`eclipse-opensovd/classic-diagnostic-adapter`) is the open-source reference implementation bridging classic UDS/DoIP to SOVD APIs — active 2025-2026.
23. [KNOW] J2534 PassThru: Windows DLL API standardizing VCI access (open/read/write/ioctl/filter). VAS 6154, Tactrix OpenPort 2.0, MDI, DrewTech support it. J2534-2 adds SWCAN and pin-switching. Tools like bri3d/VW_Flash use J2534 or SocketCAN or Macchina A0/ESP32 bridges.
24. [KNOW] KWP-on-CAN / GMLAN DPS: GM/Opel pre-UDS diagnostics = KW2000-flavored services over GMLAN with different session logic; scapy's automotive layer supports GMLAN primitives.

## 5. Data formats that describe vehicles

25. [KNOW] DBC: Vector's de-facto CAN signal database — messages (BO_ id name len sender), signals (SG_ name : start|len@endianness sign (factor,offset) [min|max] "unit" receivers), multiplexing (M/m tokens), value tables. Proprietary-ish format but everyone parses it; `eerimoq/cantools` is the reference Python implementation (also KCD/ARXML/CDD). Real OEM DBCs rarely leak complete — most work is reverse engineering with cabana/SavvyCAN.
26. [KNOW] ODX (ISO 22901-1): ASAM XML data model for diagnostics — DIDs, routines, sessions, security, flash containers. OEM diagnostic data (VAG ODX/PDX, used by ODIS and VCDS to know each module). FRF = VAG's zipped flash container wrapping ODX+flash payloads (evidence: bri3d/VW_Flash `frf` extractor works "any and all FRF").
27. [KNOW] A2L (ASAM MCD-2 MC / ASAP2): describes measurement variables + calibration maps with addresses/types/conversions for XCP/CCP — the tuning industry's map definition currency. `bri3d/a2l2xdf` converts A2L subsets into TunerPro XDF definitions.
28. [KNOW] XCP/CCP (ASAM measurement & calibration): read/write RAM/flash live while engine runs — bypass/seedkey protected. XCP rides CAN/Ethernet. This is how professional loggers pull hundreds of channels at high rate vs slow 0x22 polling.
29. [KNOW] MDF/MF4, BLF, ASC, TRC, CSV — log container formats for CAN captures (cantools/canmatrix/asammdf handle them; SavvyCAN imports most).
30. [KNOW] VAG PR codes / production codes: 3-character equipment codes (e.g. 8K0 steering, 1AB suspension) on the vehicle data sticker (boot/door jamb) and in the PR list — determines correct parts/coding/flash datasets. Opel equivalent: RPO codes (Regular Production Option, 3-char alphanum in glovebox/VIN-linked).

## 6. Open-source diagnostic toolchain (verified inventory 2026-11)

31. [USE] python-udsoncan (`pylessard/python-udsoncan`, MIT) — reference Python UDS client; pair with `python-can-isotp` (ISO-TP) + `python-can` (hardware abstraction incl. SocketCAN/PCAN/Kvaser/slcan/J2534). The standard trio for scripting diagnostics.
32. [USE] `driftregion/iso14229` — embedded C UDS server+client (write your own ECU/flash tool firmware); `mdabrowski1990/uds` — newer actively-maintained Python UDS with multi-bus abstraction; `oxibus/automotive_diag` — Rust: UDS+KWP2000+OBD-II+DoIP definitions.
33. [USE] linux-can/can-utils + SocketCAN — the Linux CAN foundation: `candump`, `cansend`, `canplayer`, `cangen`, `isotpsend/recv/dump`, kernel `can_isotp` module (≥5.10). Setup: `ip link set can0 up type can bitrate 500000`.
34. [USE] SavvyCAN (`collin80/SavvyCAN`) — the free cross-platform CAN RE workbench: frame analysis, DBC decode/override, signal graphing, fuzzer, UDS scan window, frame playback, many hardware backends (EVTV/panda/ELM327/SocketCAN/KVaser).
35. [USE] ICSim (`zombieCraig/ICSim`) — SocketCAN instrument-cluster simulator for training attacks safely on vcan0. Pair with UDSim (UDS server simulator) + `caringcaribou`.
36. [USE] ELM327 emulators for testing apps without a car: `Ircama/ELM327-emulator` (multi-ECU), `qadanm/elmulator` (BLE+TCP scriptable), `lbenthins/ecu-simulator` (UDS/ISO-TP).
37. [USE] Hardware: comma.ai panda (3xCAN + 2xLIN + 1xGMLAN/SWCAN + J2534 mode, STM32 — best value), CANable/candleLight clones (cheap slcan — no SWCAN), PCAN/Kvaser (pro-grade), Macchina M2/A0, MCP2515+MCP2551 Arduino/RPi hats, Tactrix OpenPort 2.0 (J2534), ELM327 for simple OBD only.
38. [USE] EcuBus-Pro (Apache) — UDS/CAN-TP/DoIP/LIN toolbox with TypeScript CAPL-like scripting; HIL testing: `jumpstarter-dev/jumpstarter` (UDS/DoIP/CAN drivers).
39. [USE] Rust embedded/no-std can-isotp crate by `oxibus`; `I-CAN-hack/automotive` — Rust crate + Python bindings for CAN+diagnostics.
40. [REQ] For any diagnostic session script: send TesterPresent 0x3E every 2–4s in extended sessions; handle 0x78 responsePending; respect requiredTimeDelay in SecurityAccess retries — hammering locks modules out (0x36 exceedNumberOfAttempts).

[COMPAT]
- Pairs with `automotive-vag.md` (VAG-specific IDs/flows) and `automotive-opel.md` (GMLAN/KWP specifics).
[REFS]
- awesome-canbus: https://github.com/iDoka/awesome-canbus
- awesome-vehicle-security: https://github.com/jaredthecoder/awesome-vehicle-security
- SocketCAN kernel docs: https://docs.kernel.org/networking/can.html
