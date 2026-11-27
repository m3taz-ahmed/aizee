[TECH] gmlan-gmw3110
[OBJ] GMLAN enhanced diagnostics (GMW3110-2010) reference: USDT vs UUDT message strategy, service table with subfunctions, `0x2C`/`0xAA` dynamic packet data path, DPID scheduling, addressing (physical/functional/extended), dangerous services policy, NRC handling. Use when working on GM/Opel/Vauxhall/Chevrolet/Saab GMLAN-era diagnostics.
[SRC] Researched 2026-11-27. Evidence: GMW3110-2010 unofficial public mirrors (Studylib/DocDroid — NOT official GM distribution; treat content as community-grade), scapy `contrib/automotive/gm/gmlan.py` (GPL-2.0 — facts only), `roffe/gocan` v1+v2 gmlan package docs (MIT), CANExplorer GMLAN notes, `refs/automotive-embedded-research-2026-11-27.md` §4.3.

## 1. Provenance warning

[RULES]
1. [REQ] GMW3110 text available publicly is an unofficial mirror. Every service fact must be cross-checked against implementations (scapy, gocan) or a known-good capture before being taught as certain. Exact timing values and DPID numeric rates stay `[unverified]` unless confirmed per-vehicle.
2. [KNOW] GMLAN = GM's pre-UDS enhanced diagnostic layer over CAN (KWP2000-flavored service layout). Later Global-A/B architectures migrated toward UDS — identify which world the target ECU lives in before choosing service tables. Opel/Vauxhall GM-era cars (Vectra C, Astra H, Zafira B, Insignia A...) are GMLAN-era. [community/documented]

## 2. USDT vs UUDT message strategy

3. [KNOW] USDT = Unacknowledged Segmented Data Transfer — may span multiple CAN frames (ISO-TP-like segmentation). UUDT = Unacknowledged Unsegmented Data Transfer — ALWAYS a single-frame response. [community — GMW3110 mirror §4.1, corroborated by thesis and gocan docs]
4. [KNOW] All diagnostic REQUESTS and all NEGATIVE responses use USDT. Positive responses may be USDT or UUDT depending on the service (GMW3110 Table 6 specifies per service: `0xA9` and `0xAA` positive responses are UUDT). [community — unofficial mirror]
5. [KNOW] Separate USDT/UUDT CAN identifiers let single-frame periodic data interleave with a multi-frame response from the same node — this is why scheduled live data doesn't block big responses. [community]
6. [KNOW] Request-in-process completion rules [community — mirror §4.3]: a request is complete when the ECU sends the last CF of a USDT multi-frame positive response, OR a USDT negative response with a code other than `0x78`, OR a USDT single-frame positive response, OR the first/only UUDT response arrives (for `0xA9`/`0xAA`).

## 3. Addressing

7. [KNOW] 11-bit CAN IDs. Physical request IDs are module-specific (community-observed `0x241`–`0x25F` band for Vectra-C-era modules) with responses at request `+0x400`; functional broadcast request = `0x101`; extended addressing uses 29-bit IDs with extended address byte `0xFE` seen in docs. These are community facts — DISCOVER by listening, never guess-and-transmit. [community]
8. [REQ] Addressing discovery procedure: passive capture → identify periodic vs diagnostic traffic → send tester-present candidates ONLY after bus understanding, on bench first. See `diagnostic-protocols-lord`/`can-bus-lord` doctrine.

## 4. Service table (scapy cross-confirmed)

9. [KNOW] Request services (SID → name → use/risk class):

| SID | Name | Class / downstream use |
|-----|------|------------------------|
| 0x04 | ClearDiagnosticInformation | WRITE — confirm-gated; destroys freeze-frame evidence |
| 0x10 | InitiateDiagnosticOperation | session control (subfunctions incl. disableAllDTCs, enableDTCsDuringDeviceControl, wakeUpLinks) |
| 0x12 | ReadFailureRecordData | READ — failure/freeze-frame records |
| 0x1A | ReadDataByIdentifier | READ — static data; `0x90` = VIN in GM practice |
| 0x20 | ReturnToNormalOperation | session cleanup — mandatory after device control |
| 0x22 | ReadDataByParameterIdentifier | READ — enhanced live data by PID |
| 0x23 | ReadMemoryByAddress | DANGEROUS — memory readout; blocked by default |
| 0x27 | SecurityAccess | SENSITIVE — seed/key; policy-gated, never brute-force |
| 0x28 | DisableNormalCommunication | DANGEROUS — silences module application traffic |
| 0x2C | DynamicallyDefineMessage | WRITE-class — define dynamic packets for `0xAA` |
| 0x2D | DefinePIDByAddress | DANGEROUS — memory-address-based definitions |
| 0x34 | RequestDownload | FORBIDDEN in AUTO v1 — flashing family |
| 0x36 | TransferData | FORBIDDEN in AUTO v1 — flashing family |
| 0x3B | WriteDataByIdentifier | WRITE — strict gatekeeper |
| 0x3E | TesterPresent | session keepalive; keeps periodic DPID scheduler alive |
| 0xA2 | ReportProgrammedState | READ — programming state of nodes (canonical GMW spelling — scapy's request-table says "ReportProgrammingState" but its own positive class + GMW + gocan say ProgrammedState) |
| 0xA5 | ProgrammingMode | FORBIDDEN in AUTO v1 |
| 0xA9 | ReadDiagnosticInformation | READ — enhanced DTC/fault info; positive response is UUDT |
| 0xAA | ReadDataByPacketIdentifier | READ — DPID live-data packets; positive response UUDT |
| 0xAE | DeviceControl | OUTPUT TESTS / actuator control — highest-risk normally-allowed service |

10. [KNOW] Positive responses: SID + 0x40 pattern for the classical services (0x44, 0x50, 0x52, 0x5A, 0x60, 0x62, 0x63, 0x67, 0x68, 0x6C, 0x6D, 0x74, 0x76, 0x7B, 0x7E) and 0xE2/0xE5/0xE9/0xEA/0xEE for the 0xAx family. Negative response = `0x7F <SID> <RC>`. [community — scapy service map]

## 5. The `0x2C`/`0xAA` live-data path and DPID scheduling

11. [KNOW] `0xAA ReadDataByPacketIdentifier` retrieves ECU data changing during operation (sensor inputs, commanded states). Static data (VIN, part numbers) belongs to `0x1A`. Each data packet = 1 DPID byte + 1–7 data bytes. [community — gocan package docs, GMW-corroborated]
12. [KNOW] `0xAA` subfunctions (scapy-exact): `0x00` stopSending, `0x01` sendOneResponse, `0x02` scheduleAtSlowRate, `0x03` scheduleAtMediumRate, `0x04` scheduleAtFastRate. Scheduled DPIDs run on the Periodic DPID Scheduler (PDS) which requires TesterPresent `0x3E` to stay active. [community — scapy source; gocan docs]
13. [KNOW] DPID responses ride UUDT single frames where the DPID number occupies the message-number byte position — the tester identifies content by DPID. Exact numeric slow/medium/fast rates and the `0x5xx` UUDT ID assignments are vehicle/ECU data: `[unverified]` here — capture to confirm. [community/unverified]
14. [REQ] Before using `0x2C` to compose dynamic packets, confirm the ECU supports it on the target variant — log the exact definition bytes sent; dynamic definitions must be torn down / session returned to normal afterwards.

## 6. DeviceControl `0xAE` — output tests

15. [REQ] `0xAE` DeviceControl is the GMLAN output-test service — NOT UDS `0x2F`. Subfunction structure is CPID-based (Control Parameter Identifier) with control options; exact CPIDs are ECU-specific data requiring per-variant documentation or careful verification. [community]
16. [REQ] Output-test mandatory discipline: vehicle stationary + speed == 0 verified from live data, engine/state preconditions per CPID, explicit user confirmation naming the actuator, timeout-bounded activation, guaranteed return-control/return-to-normal in a `finally`-equivalent path, log everything. Never activate motion-capable actuators (fans are lower-risk than e.g. fuel pump/relays feeding actuators that move the car).
17. [PROHIBIT] Never fire `0xAE` with an unverified CPID copied from a forum as a "trial". Treat forum CPIDs/DPIDs as `[unverified]` hints requiring passive corroboration first.

## 7. NRCs and session timing

18. [KNOW] Negative response format `7F <SID> <RC>`. Key response codes in GMLAN/KWP-flavored practice: `0x10` generalReject, `0x11` serviceNotSupported, `0x12` subFunctionNotSupported, `0x22` conditionsNotCorrect, `0x31` requestOutOfRange, `0x33` securityAccessDenied, `0x35` invalidKey, `0x36` exceedNumberOfAttempts, `0x37` requiredTimeDelayNotExpired, `0x78` requestCorrectlyReceived-ResponsePending. Exact RC tables are per-spec/per-ECU — verify against the mirror+implementation before teaching numeric details beyond these core codes. [documented core + community]
19. [REQ] RC `0x78` = response pending: WAIT for the real response within extended timing; never retry-storm the request. RCs `0x35/0x36/0x37` = STOP security attempts, report lockout state — no automated retry ever.
20. [KNOW] Session timing: tester keeps sessions alive with `0x3E` TesterPresent; ECUs drop back to normal operation after inactivity timeout — always expect state loss and re-verify session before assuming it persists. [documented concept]

[COMPAT]
- KWP2000/UDS/ISO-TP base services and NRC practice: `skills/obd-diagnostics.md` + `tech-stack/automotive-diagnostics.md`; Opel network/ECU eras: `tech-stack/automotive-opel.md`; bus electrical layer: `tech-stack/can-physical-layer.md`; write governance: `skills/diagnostic-safety-lord/SKILL.md`.
[REFS]
- GMW3110-2010 mirror: https://studylib.net/doc/26162849/gmw3110-2010 (unofficial)
- scapy GMLAN: https://github.com/secdev/scapy/blob/master/scapy/contrib/automotive/gm/gmlan.py
- roffe/gocan gmlan docs: https://pkg.go.dev/github.com/roffe/gocan/v2/gmlan
- CANExplorer GMLAN notes: https://akj7.github.io/CANExplorer/user-guide/gmlan/
