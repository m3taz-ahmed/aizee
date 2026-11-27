---
name: diagnostic-safety-lord
description: Lord skill for engineering tools that write to vehicles — single write-gatekeeper architecture, service allow/deny lists, payload-bound confirm tokens, fail-safe interlocks from live data, pre-write snapshots, guaranteed returnControl/return-to-normal, audit logging, simulator fault injection, ISO 26262 concepts (fail-safe/safe state) without compliance claims, panda-style hardware-layer enforcement. Use when any code path can transmit writes to a vehicle.
triggers:
  - write gatekeeper
  - output test safety
  - actuator test
  - devicecontrol
  - clear dtc safety
  - write to ecu
  - diagnostic write
  - interlock
  - fault injection
  - return control
  - audit log vehicle
  - fail-safe
  - iso 26262 concepts
  - كتابة على السيارة
  - اختبار المشغلات
  - مسح الأعطال أمان
  - حارس الكتابة
personas:
  - AUTO
tech_stack:
  - gmlan-gmw3110
  - automotive-power-protection
lord: true
---

[SKILL] diagnostic-safety-lord
[OBJ] Make vehicle writes structurally safe: one gatekeeper, no bypassable paths, every write justified by live preconditions, every session guaranteed to unwind, every action auditable, every failure mode rehearsed in simulation before the first real vehicle.
[COMPAT] skills/diagnostic-protocols-lord/SKILL.md (service semantics), tech-stack/gmlan-gmw3110.md (0xAE/0x2C details), skills/embedded-firmware-lord/SKILL.md (firmware enforcement), skills/gm-opel-lord/SKILL.md (Opel specifics); architectural reference: commaai/panda safety model (MIT — pattern only)
[SRC] Researched 2026-11-27. Evidence: commaai/panda hardware-safety architecture, prototux/PSA-RE data-driven model, gallia testing methodology, vectra-scanner MASTER-PROMPT write-gatekeeper design, dossier §4.9.

[RULES]
1. [REQ] **Single write-gatekeeper**: exactly one code path may transmit write-class frames to a vehicle. UI, scripts, replay tools, debug consoles all route through it. Any second path = architecture defect. Enforcement as close to hardware/firmware as possible (panda lesson: policy belongs where bypassing requires reflashing, not clicking).
2. [KNOW] Read/write classification: read-only services (read data/DTC/ID/failure records) flow freely after session rules; write-class (clear, writeDataBy*, IO control/DeviceControl, routines, session-state changes affecting actuators) pass the gate; forbidden-in-v1 (programming/download/memory-write family: GMLAN `0x23/0x2D/0x28/0x34/0x36/0x5`, memory ops) never pass. Classification is explicit data, not vibes.
3. [REQ] Pre-write pipeline, no exceptions: read current state/snapshot first → verify interlocks from LIVE data (speed == 0, engine state as required, voltage in range) → explicit user confirmation naming the exact action+target → token bound to the exact payload bytes (not a generic "yes") → execute with timeout → verify post-state → log.
4. [KNOW] Interlock freshness: preconditions must come from live measurements within a validity window — a speed reading from 30 seconds ago is not evidence the vehicle is stationary NOW. Stale data = fail-closed.
5. [REQ] Guaranteed unwind: every output test/device control/session alteration has a finally-equivalent path restoring control (returnControl / ReturnToNormalOperation / stopSending). Timeouts, crashes, disconnects, and user Ctrl-C all still trigger cleanup. Test this by killing the tool mid-test in simulation.
6. [KNOW] Confirm-token design: token binds target ECU + service + payload + nonce/timestamp; replaying a stale token fails; UI never pre-confirms; paste-a-hex-payload paths still require the same token path. [community security design]
7. [REQ] Audit log: append-only, timestamped, hash-chained or at minimum tamper-evident sequence — what was requested, interlock values, user confirmation, frames sent/received, outcome. Diagnostics without logs are unverifiable; safety claims without logs are worthless.
8. [REQ] Simulator-first: no write path exists until demonstrated in simulation — demo ECU backend with fault injection covering: response-pending loops (`0x78`), lockout NRCs, mid-write disconnect, bus-off, power loss during routine, unexpected reset, malformed ISO-TP, replay attempts. vectra-scanner demo backend with fault injection is the local reference model.
9. [KNOW] Fault-injection lessons to encode: replayed captures must never reach a live vehicle (transport separation); reports/exports escape content (CSV-injection neutralization); malicious YAML/data definitions rejected by schema validation (no `eval` in data pipelines). [community — vectra-scanner test design]
10. [REQ] Rate limiting + session hygiene: bounded request rates, TesterPresent scheduling that never floods, stop-conditions on repeated NRCs. On `0x36` exceedNumberOfAttempts or `0x37` requiredTimeDelayNotExpired: hard stop, report lockout risk — continue only with explicit fresh user decision after understanding consequences.
11. [KNOW] ISO 26262 as concepts only [documented existence, no compliance claim]: fail-safe = failure transitions to a safe state; safe state for a diagnostic tool = TX-inhibited, actuators returned, session unwound. We borrow the vocabulary — we never claim compliance.
12. [REQ] Output-test doctrine (GMLAN `0xAE` DeviceControl / KWP `0x2F/0x30` / UDS `0x2F`): verified CPID/identifier for the exact ECU variant → stationary+state preconditions → named-actuator confirmation → timeout-bounded activation → guaranteed return-control → post-verify. Motion-capable actuators demand explicit risk acknowledgment; fans/lights are the learning path.
13. [PROHIBIT] Never: brute-force or loop security access; clear DTCs before reading+saving them (evidence destruction — including freeze frames); run unknown routines "to see what happens"; let UI convenience bypass the gatekeeper; hide write capability behind undocumented debug commands.
14. [REQ] Refusal consistency: odometer manipulation, emissions defeat (EGR/DPF/cat delete), immobilizer bypass, secure-gateway bypass, hiding faults from a buyer = refuse + explain legal/safe alternative (see primary skill refusal map). The gatekeeper's deny-list encodes these at the service level where technically possible.
15. [KNOW] Data-driven enforcement: vehicle/ECU capability data carries provenance + confidence; unverified identifiers are unavailable in write UI — not just warn-labeled. If it isn't verified for THIS unit, it doesn't render as an option. [PSA-RE pattern adapted]
