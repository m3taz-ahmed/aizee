---
name: obd-diagnostics
description: OBD-II modes/PIDs, UDS/ISO-TP/TP2.0/DoIP/KWP2000/KW1281/J1850 protocol stack, adapters, python-can/cantools/opendbc/caringcaribou/SavvyCAN/cabana toolchain, DTC practice. Load for diagnostics/scan-tool/adapter questions.
triggers:
  - obd
  - obd2
  - obd-ii
  - diagnostic
  - dtc
  - uds
  - iso-tp
  - isotp
  - kwp2000
  - kwp1281
  - doip
  - j1850
  - elm327
  - python-can
  - cantools
  - dbc
  - savvcan
  - caringcaribou
  - cabana
  - scan tool
  - fault code
personas:
  - AUTO
tech_stack:
  - automotive-diagnostics
  - gmlan-gmw3110

---

[SKILL] obd-diagnostics
[OBJ] Run vehicle diagnostics correctly across protocol eras: pick adapter + protocol + service, interpret DTC/PID data, know the open-source toolchain.
[COMPAT] tech-stack/automotive-diagnostics.md (deep protocol reference), skills/auto-domain-map.md (era router), skills/vag-diagnostics.md (VAG-specific), skills/ecu-tuning.md (flashing side)
[RULES]
1. [REQ] OBD-II service modes: 01 live data, 02 freeze frame, 03 confirmed DTC, 04 clear, 05 O2 monitor, 06-08 on-board monitoring, 09 vehicle info, 0A permanent DTC (cannot be cleared — emissions-legislated). Mode 22/23 = manufacturer-specific UDS extensions.
2. [REQ] DTC structure: 1st char system (P=powertrain/B=body/C=chassis/U=network), 2nd char standard vs manufacturer, 3rd subsystem, last two = specific fault. P0300 = random misfire; U-codes = network comms.
3. [REQ] Protocol eras by vehicle: pre-2004 K-line KWP1281 (5-baud init) → 2004+ CAN KWP2000 (11-bit 500k/11M) → 2015+ UDS/ISO-TP (VWTP2.0) → newest DoIP Ethernet. ELM327 = consumer KWP/CAN only — UDS-capable adapters (e.g. STN-based, CANable, CerberusCAN) needed for modern modules.
4. [REQ] J1850 (PWM/VPW) = Ford/GM pre-2008 legacy — separate adapter, not CAN.
5. [REQ] UDS services: 0x10 DiagnosticSessionControl (default/extended/programming), 0x11 ECUReset, 0x14 ClearDTC, 0x19 ReadDTCInformation, 0x22 ReadDataByIdentifier, 0x2E WriteDataByIdentifier, 0x27 SecurityAccess (seed→key), 0x31 RoutineControl, 0x34-37 download/upload (flash). SecurityAccess unlocks manufacturer functions.
6. [REQ] ISO-TP (ISO 15765) = transport inside CAN: single frame / first frame+consecutive frames / flow control. TP2.0 = VW's older transport variant for comfort/comfort-can modules.
7. [REQ] Adapter landscape: ELM327 (cheap, OBD-II only), STN11xx/STN21xx (UDS-capable), CANable/candleLight (slcan→python-can), CerberusCAN (VAG tri-CAN VCI), EcuBus-Pro (BMW), VCI clones (ODIS/VCI/VAS).
8. [REQ] python-can = the hub library: `can.interface.Bus`, filters, log/replay (.blf/.asc), `cantools` for DBC decode (`db.decode_message`), `canmatrix`/`cabast` for DBC generation/analysis.
9. [REQ] Open analysis tools: `SavvyCAN` (Qt CAN analyzer + graphing + filters), `caringcaribou` (packet-level explorer), `ICSim`+`UDSim` (virtual ECUs for testing), `scapy` automotive contrib (CAN packet crafting), `linux-can/can-utils` (candump/cansend).
10. [REQ] Signal references: commaai/opendbc (production DBCs incl. `vw_pq/mqb/mqbevo/mlb`, `gm_global_a_*`, `opel_omega_2001`) — best free decode tables. Manufacturer DBCs rarely public → reverse-engineer or buy.
11. [REQ] Workflow: connect → identify ECU (VIN/session) → read DTC → freeze frame → live data → targeted tests → clear → verify. Always log raw frames (.blf) before interpreting — replay beats re-driving.
12. [REQ] Safety: never write/flash without backup; SecurityAccess sessions can timeout; clear-DTC erases freeze-frame evidence — read first.
13. [PROHIBIT] No seed-key algorithms, no immobilizer bypass, no mileage tampering — defensive/diagnostic framing only.
14. [VER] For VAG-specific session/DID details load `skills/vag-diagnostics.md`; for wave-1 protocol depth load `tech-stack/automotive-diagnostics.md`.
