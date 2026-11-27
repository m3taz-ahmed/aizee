---
name: diagnostic-protocols-lord
description: Lord skill for vehicle diagnostic protocol stacks — ISO-TP (ISO 15765-2 SF/FF/CF/FC, BS/STmin, padding, N_As/N_Bs/N_Cr), OBD-II (SAE J1979/ISO 15765-4 modes 01–0A, PIDs, J2012 DTC format), KWP2000 (ISO 14230-3 on K-line and CAN), GMLAN (GMW3110), UDS (ISO 14229-1), VW TP2.0, DoIP basics, NRC tables, P2/P2*/S3 timing, security-access policy. Use when parsing, building, or debugging diagnostic communication.
triggers:
  - iso-tp
  - isotp
  - iso 15765
  - kwp2000
  - iso 14230
  - uds protocol
  - iso 14229
  - gmlan
  - gmw3110
  - obd modes
  - negative response code
  - nrc 0x78
  - flow control frame
  - tester present
  - security access
  - seed key
  - doip
  - tp2.0
  - عطل كمبيوتر
  - بروتوكول التشخيص
  - قراءة الأعطال
  - سكانر
personas:
  - AUTO
tech_stack:
  - gmlan-gmw3110
  - can-physical-layer
lord: true
---

[SKILL] diagnostic-protocols-lord
[OBJ] Speak diagnostic protocols exactly: correct framing, correct service IDs per protocol family, correct negative-response handling, correct timing — and never confuse KWP/UDS/GMLAN dialects that share numeric IDs with different meanings.
[COMPAT] tech-stack/gmlan-gmw3110.md (GM service depth), skills/obd-diagnostics.md (existing operational layer — modes/adapters), skills/gm-opel-lord/SKILL.md (Opel dialects), skills/diagnostic-safety-lord/SKILL.md (write governance), tech-stack/automotive-diagnostics.md (wave-1 depth)
[SRC] Researched 2026-11-27. Evidence: ISO 14229-1 preview, KWP2000 DaimlerChrysler 2002 PDF + Tracetronic docs, python-can-isotp/udsoncan (MIT), scapy automotive layers, GMW3110 mirror, dossier §4.1–4.3.

[RULES]
1. [REQ] Protocol-dialect discipline: the same numeric SID means different things across KWP2000/UDS/GMLAN (e.g. `0x2E` = writeDataByCommonIdentifier in KWP but writeDataByIdentifier in UDS; output tests = KWP `0x2F/0x30` or GMLAN `0xAE` or UDS `0x2F`). ALWAYS name the protocol family before quoting a service table.
2. [KNOW] ISO-TP framing [documented]: SF (single frame, PCI nibble len 0–7 classic), FF (first frame, 12-bit total length), CF (consecutive, rolling sequence nibble), FC (flow control: status 0x30 CTS/0x31 wait/0x32 overflow + BS block size + STmin separation). Receiver controls pacing — honor BS/STmin exactly.
3. [KNOW] Layer separation: `0x78` is a DIAGNOSTIC-layer negative response (responsePending) — not an ISO-TP error. Transport timeouts (N_As/N_Bs/N_Cr) are distinct from application timings (P2/P2*/S3). Both must be configurable per ECU, never hardcoded globally.
4. [REQ] Response-pending handling: on NRC `0x78` wait for the real response within extended P2* — do not retry, do not treat as failure. Retry storms during flash-adjacent or security operations are how ECUs get bricked or locked.
5. [KNOW] OBD-II modes [documented]: 01 live data, 02 freeze frame, 03 confirmed DTCs, 04 clear, 05/06/07/08 monitoring, 09 vehicle info (VIN/calibration), 0A permanent DTCs (not clearable — emissions-legislated). Mode 04 erases freeze-frame evidence — read everything first.
6. [KNOW] J2012 DTC format: letter system (P/B/C/U) + first digit standard-vs-manufacturer + subsystem + fault bytes; P0xxx = legislated generic, P1xxx = manufacturer-specific — meaning requires the OEM table, not guessing.
7. [KNOW] KWP2000 service map [documented — Tracetronic + DaimlerChrysler impl + TesterPresent refs]: `0x10` startDiagnosticSession, `0x11` ECUReset, `0x14` clearDiagnosticInformation, `0x18` readDTCByStatus, `0x1A` readECUIdentification, `0x20` stopDiagnosticSession, `0x21` readDataByLocalIdentifier, `0x22` readDataByCommonIdentifier, `0x23` readMemoryByAddress, `0x27` securityAccess, `0x2C` dynamicallyDefineLocalIdentifier, **`0x2E` writeDataByCommonIdentifier, `0x3B` writeDataByLocalIdentifier**, `0x2F` IOControlByCommonIdentifier, `0x30` IOControlByLocalIdentifier, `0x31/32/33` routines, `0x34–0x37` transfer family, `0x3D` writeMemoryByAddress, `0x3E` testerPresent. Positive = SID+0x40, negative = `7F SID NRC`.
8. [REQ] **KWP write correction (high-value fact): local-identifier writes use `0x3B`; common-identifier writes use `0x2E` — inverted tables exist in the wild (including a private reference project's notes, since corrected); one public ACTIA table even mislabels common-write as `0x3E` (that code is TesterPresent). Trust the cross-confirmed assignment, flag bad sources.**
9. [KNOW] KWP on K-line vs on CAN: same application services, different framing — K-line adds header (fmt/tgt/src/len) + checksum and init sequence (5-baud or fast init); on CAN it rides ISO-TP. Opel/Vectra-C-era engine diagnostics = KWP2000-on-CAN.
10. [KNOW] UDS core services [documented]: `0x10` session, `0x11` reset, `0x14` clearDTC, `0x19` readDTC, `0x22` readDataByIdentifier, `0x27` securityAccess, `0x28` communicationControl, `0x2E` writeDataByIdentifier, `0x2F` inputOutputControlByIdentifier, `0x31` routineControl, `0x34–0x37` transfer, `0x3E` testerPresent, `0x85` controlDTCSetting.
11. [KNOW] NRC core table [documented]: `0x10` generalReject, `0x11` serviceNotSupported, `0x12` subFunctionNotSupported, `0x22` conditionsNotCorrect, `0x31` requestOutOfRange, `0x33` securityAccessDenied, `0x35` invalidKey, `0x36` exceedNumberOfAttempts, `0x37` requiredTimeDelayNotExpired, `0x78` responsePending. Correct actions: 0x22 → check preconditions/session; 0x31 → identifier invalid for this ECU; 0x33/35/36/37 → STOP security workflow, report — never automated retry.
12. [KNOW] GMLAN (GMW3110) essentials — full table in `tech-stack/gmlan-gmw3110.md`: `0x10` init, `0x1A` RDBI (0x90=VIN), `0x22` readByParameter, `0xA9` readDiagnosticInformation, `0x12` readFailureRecord, `0x04` clear, `0x27` security, `0x2C`+`0xAA` dynamic packet live data (UUDT slow/medium/fast), **`0xAE` DeviceControl = output tests**, `0x3B` write, `0x20` returnToNormal, `0xA2` reportProgrammedState. Functional addressing `0x101`, ext `0xFE`. Dangerous/forbidden default: `0x23/0x2D/0x28/0x34/0x36/0xA5`.
13. [KNOW] USDT vs UUDT [community — GMW mirror]: USDT segmented multi-frame possible; UUDT always single frame. Requests/negative responses = USDT; `0xA9`/`0xAA` positives = UUDT. `0xAA` subfunctions: 0x00 stop, 0x01 oneResponse, 0x02 slow, 0x03 medium, 0x04 fast; periodic scheduling needs TesterPresent kept alive.
14. [KNOW] Security access as concept: seed request (odd subfunction) → ECU seed → key compute (algorithm per-ECU/per-family) → key response (even subfunction) → unlock level. Algorithms are NEVER universal — the documented GM E38/E67 `0x92` algorithm is a candidate-only on anything else (e.g. GMPT-E16). Policy: no brute-force, no lockout-risk automation, stop on 0x35/36/37.
15. [KNOW] DoIP (ISO 13400) basics: UDS payload over IP/Ethernet, vehicle announcement/discovery, routing activation — the modern high-bandwidth path; treat as emerging scope — verify before promising support.
16. [KNOW] VW TP2.0 = VAG-specific transport for comfort/CAN modules pre-UDS (dynamic timing/channel params) — relevant only in VAG workflows; details in `vag-diagnostics`/`automotive-vag`.
17. [REQ] Session management discipline: know which session you are in; send TesterPresent on schedule when a session must persist; expect ECU timeout back to default after inactivity; re-verify session state after any interruption rather than assuming.
18. [REQ] Multi-frame integrity: validate CF sequence numbers, total-length agreement with FF, no buffer writes beyond declared length, padding tolerance per implementation but strict length semantics. Malformed frames → reject+log, never coerce.
19. [PROHIBIT] Never: send security-access keys in automated loops; treat `0x78` as error; confuse UDS `0x2F` with GMLAN `0xAE`; use flash-family services (`0x34/0x36/0xA5` GMLAN, UDS download chain) in AUTO v1; assume IDs/services across ECU variants without provenance.
20. [USE] Python implementation references: `pylessard/python-can-isotp` (MIT — transport params/timeouts), `pylessard/python-udsoncan` (MIT — service clients/NRC), scapy automotive contrib (GPL-2.0 — protocol-shape facts only). Validate behavior in simulation (ELM327-emulator/custom demo ECU) before any vehicle.
