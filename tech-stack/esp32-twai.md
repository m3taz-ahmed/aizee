[TECH] esp32-twai
[OBJ] ESP32 TWAI (CAN controller) engineering reference: legacy `driver/twai.h` vs new `esp_driver_twai` event-driven driver, the listen-only dominant-bit silicon errata and its workaround, bus-off recovery, version pinning across ESP-IDF 5.x/6.x and Arduino-ESP32 3.x, safe bridge-firmware defaults.
[SRC] Researched 2026-11-27. Evidence: ESP-IDF TWAI docs + migration guides (Context7 `/espressif/esp-idf`), esp-idf issue #9152, commits 72becf3 / 57b6be22a7 / 9245d8e, `refs/automotive-embedded-research-2026-11-27.md` §4.7.

## 1. Version pinning — never teach unpinned APIs

[RULES]
1. [REQ] Pin exact versions before writing any TWAI code: ESP-IDF release (e.g. v5.4.x vs v6.x) AND Arduino-ESP32 core (3.x tracks a specific IDF). The legacy/new driver split lands differently across versions — an example correct for IDF 5.1 can be wrong for 5.5+/6.x. Check Context7 `/espressif/esp-idf` at authoring time.
2. [KNOW] Legacy driver: single-controller-ish API in `driver/twai.h` — `twai_driver_install`/`twai_general_config_t`/`twai_timing_config_t`/`twai_filter_config_t`, blocking `twai_transmit`/`twai_receive`, `twai_read_alerts`. Still present in 5.x/6.x migration guides but deprecated/legacy.
3. [KNOW] New driver (IDF 5.5+): component `esp_driver_twai`, headers `esp_twai.h` + `esp_twai_onchip.h` — event-driven callbacks (`on_rx_done`, `on_state_change`, `on_error`), runtime bitrate/filter reconfiguration, multiple simultaneous controllers, CAN FD on capable chips (ESP32-C5). Blocking receive APIs are NOT provided; `twai_receive` maps to `twai_node_receive_from_isr` inside the rx callback.
4. [KNOW] Migration deltas that break ported code: `twai_read_alerts` → no direct replacement (use callbacks); `twai_clear_transmit_queue`/`twai_clear_receive_queue` → unsupported; receive is event-driven only. [documented — IDF 5.5/6.0 peripherals migration guides]
5. [REQ] When the user has Arduino-ESP32, check the core's bundled IDF version first; `ESP32Can`/`CAN` library APIs in the core are wrappers — confirm against the installed core, not memory.

## 2. The listen-only silicon errata (safety-critical)

6. [KNOW] Errata [documented — esp-idf commit 72becf3]: on ESP32, ESP32-S2, ESP32-S3, ESP32-C3 the TWAI controller in listen-only mode can still transmit dominant bits as part of ACTIVE ERROR FRAMES when it detects bus errors. Listen-only software mode alone does NOT guarantee bus silence.
7. [KNOW] Real-world evidence [community — esp-idf issue #9152]: a user running the listen-only example at the wrong bitrate disturbed a vehicle bus (check-engine light). Wrong bitrate = constant bit errors = constant active error frames.
8. [KNOW] Workaround [documented — commit 72becf3 / Kconfig `TWAI_ERRATA_FIX_LISTEN_ONLY_DOM`, default y]: force the controller into error-passive state at init by setting REC ≥ 128; TEC/REC are frozen in listen-only so the node stays error-passive and emits only recessive (passive) error frames.
9. [KNOW] IDF 6.0 reorganization [documented — commit 9245d8e, 2025-11]: the legacy-driver errata Kconfig options were removed/restructured (`TWAI_ERRATA_FIX_LISTEN_ONLY_DOM` deleted from `Kconfig.twai`, replaced by `TWAI_SKIP_LEGACY_CONFLICT_CHECK` etc.) — do not copy old menuconfig instructions into IDF 6 projects; verify how the workaround is applied in the exact target version.
10. [REQ] Defense-in-depth doctrine for any vehicle-connected ESP32: (a) hardware transmit-inhibit at the transceiver (SN65HVD230 RS high = driver off, receiver on — see `can-physical-layer.md`), (b) software listen-only mode, (c) never transmit at an unverified bitrate, (d) bench-validate with a second known-good node before car connection. Software listen-only alone is insufficient on affected silicon.
11. [PROHIBIT] Never present "listen-only mode" as guaranteed passive on ESP32/ESP32-S2/S3/C3 without the errata context. Never transmit probe frames to "detect" bitrate — use passive observation or oscilloscope/measured timing instead.

## 3. Runtime behavior: errors, bus-off, recovery

12. [KNOW] Legacy `twai_transmit` in listen-only mode returns `ESP_ERR_NOT_SUPPORTED`; it cannot be called there. [documented — driver/twai.h API contract]
13. [KNOW] Bus-off recovery is explicit, not automatic: `twai_initiate_recovery()`/`twai_initiate_recovery_v2()` valid only from `TWAI_STATE_BUS_OFF`; resets TX queue/counters, triggers hardware recovery, completion reported via `TWAI_ALERT_BUS_RECOVERED`. In the new driver, use state-change/error callbacks. [documented]
14. [REQ] Bridge-firmware safety model: boot/reset into listen-only with TX disabled; explicit `ARM` command with timeout; CAN-ID allowlist + SID blocklist for TX; rate limiting; watchdog; on bus-off stop TX and report — no silent auto-retry storm.
15. [REQ] Treat the serial/host link as hostile input: strict line parser, length bounds, reject malformed frames, no `eval`-like dispatch, versioned banner command. Reference architectures: `collin80/ESP32RET` (GVRET/SavvyCAN bridge, MIT), vectra-scanner `vx_bridge` safety model. [community]
16. [KNOW] TWAI alerts worth handling: TX_SUCCESS/TX_FAILED/TX_IDLE, RX data/overrun, error passive, bus error, bus-off, recovery. In legacy mode TEC/REC read as 0 in listen-only (frozen) — do not use them for health there. [documented]

## 4. Hardware/wiring interface notes

17. [KNOW] TWAI controller ≠ transceiver: the ESP32 TWAI peripheral is only the protocol controller; an external transceiver is mandatory (3.3V-native SN65HVD230 preferred; TJA1050 is 5V and needs RX level protection). Transceiver selection/measurement: `can-physical-layer.md`.
18. [KNOW] Common devkit wiring (vectra-scanner verified build): CTX→GPIO5, CRX→GPIO4 on classic ESP32 — but strapping/boot pins vary by chip variant (S3/C3/C6 differ); verify pin choice against the exact devkit schematic, avoid strapping pins and flash/PSRAM pins.
19. [KNOW] Bitrate config in legacy driver uses timing presets (`twai_timing_config_t` — e.g. `TWAI_TIMING_CONFIG_500KBITS`) or custom bit timing; new driver uses a bitrate config struct. Compute sample point from the active driver's documented model — `(1 + TSEG1)/(1 + TSEG1 + TSEG2)` in the common Bosch/CiA bit-time model — never copy raw register values across driver generations. [documented model]
20. [USE] Alternatives when TWAI limits bite: STM32 bxCAN/FDCAN (mature, no listen-only errata of this class, but 5V-transceiver pairing care), RP2040 + `can2040` (software CAN, careful timing validation), MCP2515/MCP2518FD SPI controllers (`sandeepmistry/arduino-CAN` as API baseline). Choose by validated evidence, not familiarity. [community]

## 5. Testing firmware

21. [REQ] Test pyramid for bridge firmware: host-side unit tests of the parser/state machine (Unity/CMock or pytest driving a serial mock) → two-node bench bus with a second transceiver + 120Ω×2 → fault injection (wrong bitrate partner, bus-off, disconnects) → only then vehicle listen-only. Never first-boot untested firmware on a car.
22. [USE] OVMS (`openvehicles/Open-Vehicle-Monitoring-System-3`, license Other/NOASSERTION — architecture reference only) as the production ESP32-in-car lesson set: power management, sleep/wake, brownout, watchdog, SD/modem/CAN interaction, OTA discipline. [community]

[COMPAT]
- Transceivers/termination/bit-timing measurement: `tech-stack/can-physical-layer.md`; vehicle power protection: `tech-stack/automotive-power-protection.md`; diagnostic use of the bus: `tech-stack/gmlan-gmw3110.md`, `skills/obd-diagnostics.md`.
[REFS]
- ESP-IDF TWAI docs: https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/twai.html
- Issue #9152 (listen-only bus interference): https://github.com/espressif/esp-idf/issues/9152
- Errata workaround commit: https://github.com/espressif/esp-idf/commit/72becf31e43b65ce425f0acb65fd69ae18ece209
- IDF 6.0 errata-config cleanup: https://github.com/espressif/esp-idf/commit/9245d8ee46001fd2ae69ba64a4b40f02a99429c3
