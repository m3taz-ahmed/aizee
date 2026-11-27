---
name: embedded-firmware-lord
description: Lord skill for automotive-grade embedded firmware on ESP32 (ESP-IDF 5.x/6, Arduino-ESP32 3.x) — TWAI legacy/new drivers and listen-only errata, FreeRTOS discipline, strapping pins, brownout, watchdog, safe serial line protocols, signed OTA, toolchain version pinning, firmware testing (Unity/HIL over serial), with STM32 bxCAN/FDCAN and RP2040 can2040 as alternatives. Use when building/reviewing microcontroller firmware that touches vehicle buses.
triggers:
  - embedded firmware
  - esp32 firmware
  - esp-idf
  - twai driver
  - freertos automotive
  - can bridge firmware
  - vx_bridge
  - serial protocol firmware
  - ota update esp32
  - brownout watchdog
  - stm32 can
  - rp2040 can
  - فريم وير
  - برمجة esp32
  - برمجة المتحكم
  - فيرموير العربية
  - توصيل esp32 بالعربية
personas:
  - AUTO
tech_stack:
  - esp32-twai
  - can-physical-layer
  - automotive-power-protection
lord: true
---

[SKILL] embedded-firmware-lord
[OBJ] Design, write, and review microcontroller firmware that survives automotive reality: boot-safe defaults, transmit-inhibited until explicitly armed, hostile-input parsing, version-accurate TWAI usage, tested on bench before vehicle.
[COMPAT] tech-stack/esp32-twai.md (versioned API/errata facts), tech-stack/can-physical-layer.md (transceivers), tech-stack/automotive-power-protection.md (power), skills/can-bus-lord/SKILL.md (bus behavior), skills/diagnostic-safety-lord/SKILL.md (write governance), reverse-engineering-lord (RE method)
[SRC] Researched 2026-11-27. Evidence: ESP-IDF docs/migration guides, esp-idf issue #9152, commits 72becf3/9245d8e, collin80/ESP32RET (MIT), OVMS-3 architecture, vectra-scanner MASTER-PROMPT safety model; dossier §4.7.

[RULES]
1. [REQ] Version-pin everything before writing code: exact ESP-IDF release AND Arduino-ESP32 core. Legacy `driver/twai.h` vs new `esp_driver_twai` differ fundamentally (blocking vs event-driven); IDF 6 removed/reorganized legacy errata Kconfig. Check Context7 `/espressif/esp-idf` at authoring time — never write TWAI code from memory.
2. [KNOW] New-driver reality (IDF 5.5+): no blocking receive — RX inside `on_rx_done` callback via `twai_node_receive_from_isr`; alerts replaced by `on_state_change`/`on_error` callbacks; runtime bitrate/filter reconfiguration possible; multi-controller support. Porting legacy code requires redesign, not renaming.
3. [REQ] **Boot/reset default = listen-only with TX disabled at both layers**: transceiver hardware inhibit (SN65HVD230 Rs high) AND TWAI listen-only mode. Transmitting requires an explicit ARM command with timeout, and disarm on timeout/host-disconnect/bus-off.
4. [KNOW] Errata doctrine (ESP32/S2/S3/C3): software listen-only alone does NOT guarantee bus silence — active error frames can still drive dominant bits; workaround forces error-passive (REC≥128) at init. Hardware inhibit is the authoritative layer. Never transmit at unverified bitrate.
5. [REQ] Serial/host protocol hardening: fixed grammar, length-bounded fields, reject unknown commands, no partial-frame execution, CRC or strict framing for binary payloads, versioned banner (`H` hello), rate limiting on commands that can generate bus traffic. Treat every host byte as hostile.
6. [REQ] State machine explicitness: states DISARMED → ARMED → TX_ACTIVE with transitions logged; every state defines which CAN IDs/SIDs may pass (allowlist) and which are always blocked (SID blocklist: programming/download/memory-write family). No implicit pass-through mode.
7. [KNOW] FreeRTOS discipline: CAN ISR/callbacks must be minimal (copy + queue); never block in callback; queue overflow policy defined (drop-with-counter, never silently overwrite); priority inversion awareness when sharing bus state across tasks.
8. [REQ] Watchdog + brownout: enable TWDT with a real recovery path, subscribe the comms task; on brownout detection log once and re-enter DISARMED — never resume armed after power events. Brownout mid-write on a vehicle is a reportable safety event.
9. [KNOW] Strapping/boot pins vary across ESP32 variants (classic vs S3/C3/C6); GPIO5/4 for CTX/CRX is the classic-devkit vectra-scanner choice — verify per exact board schematic, avoid strapping pins, flash/PSRAM pins, and USB-serial-owned pins.
10. [REQ] Bus-off handling in firmware: detect (alert/callback), stop TX immediately, report to host, require explicit re-arm — NO automatic recovery loops. Recovery initiation exists (`twai_initiate_recovery`) but policy forbids unattended retries.
11. [USE] Test pyramid: host-side parser/state-machine unit tests (pytest driving serial mock or Unity on target) → two-node bench bus → fault injection (wrong-bitrate partner, noise, disconnect mid-frame, bus-off) → vehicle listen-only. HIL over pytest-serial is the cheap effective tier.
12. [USE] Reference architectures: `collin80/ESP32RET` (MIT) for GVRET bridge/SavvyCAN interop; OVMS-3 for production in-car ESP32 lessons (power/sleep/modem interactions — license Other, architecture-only). vectra-scanner `vx_bridge` as the local minimal safe-bridge model.
13. [KNOW] OTA for vehicle devices: signed images, rollback-safe partitions, never OTA while connected to a live vehicle, verify boot-after-update on bench. An unsigned OTA path on a CAN-connected device is a vehicle network attack surface.
14. [USE] Alternatives when TWAI constrains: STM32 bxCAN/FDCAN (mature hardware CAN, FD on newer parts), RP2040+can2040 (validate timing carefully), external MCP2515/MCP2518FD SPI controllers. Selection must cite validated evidence for the target use, not familiarity.
15. [PROHIBIT] Never: transmit to probe bitrate; auto-reconnect armed after reset; hardcode bitrate/IDs without provenance comments; use `delay()`-style blocking in comms tasks; trust DLC/payload lengths from the wire without bounds checks.
16. [REQ] Code-review checklist for any firmware PR: buffer bounds on every wire-derived length; timeouts on every blocking call; retry counts bounded; endianness explicit; scaling factors traced to DBC/provenance; no heap corruption paths in ISR context; gatekeeper cannot be bypassed by any command path.
