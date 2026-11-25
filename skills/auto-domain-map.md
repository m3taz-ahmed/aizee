---
name: auto-domain-map
description: Master index for automotive domain work — protocol families, tool landscape, era-decision tree, resource sites. Load first for any car/vehicle/OBD/VAG/CarPlay/ECU task.
triggers:
  - car
  - vehicle
  - automotive
  - obd
  - carplay
  - android auto
  - vag
  - vw
  - audi
  - skoda
  - seat
  - ecu
  - diagnostic
  - head unit
  - dongle
  - immobilizer
  - key programming
  - tuning
  - engine
  - motor
---

[SKILL] auto-domain-map
[OBJ] Orient any automotive task: pick the era/protocol first, then the right tool family, then the right open-source repo or trick source.
[COMPAT] tech-stack/automotive-core.md, tech-stack/automotive-diagnostics.md, tech-stack/automotive-vag.md, tech-stack/automotive-opel.md, tech-stack/automotive-ecu-internals.md, tech-stack/automotive-security.md, tech-stack/automotive-tricks.md (wave-1 deep domain refs); skills/obd-diagnostics.md, skills/vag-diagnostics.md, skills/carplay-headunits.md, skills/ecu-tuning.md, skills/auto-mechanics-engines.md (wave-2 operational layer)
[RULES]
1. [REQ] ALWAYS start with ERA identification before tool selection — automotive reality is era-segmented, not brand-monolithic.
2. [VAG eras] K-line KWP1281 (pre-2004) → CAN KWP2000/VWTP1.6 (2004–2015) → UDS/VWTP2.0 MQB (2015+) → DoIP (newest). Tool must match era.
3. [VAG SFD split] pre/post-MQB-evo = separate diagnostic worlds; component protection (CP/KSCHUTZ) + GeKo + seed-key gate flashing/coding on newer modules.
4. [Opel eras] GM-classic → Global-A (GMLAN) → PSA (Corsa F = PSA car in Opel clothing; GM tools do NOT apply).
5. [Protocol stack order] physical layer first: K-line 5-baud init / CAN HS+FD / DoIP Ethernet / MOST / FlexRay. Then session layer: KWP1281 → KWP2000 → TP2.0 → ISO-TP → UDS → DoIP.
6. [OBD-II generic] mode 01 live data / 02 freeze frame / 03 DTC / 04 clear / 06-08 monitoring / 09 vehicle info / 0A permanent DTC. ELM327 = consumer adapter; UDS-capable adapters needed for modern modules.
7. [Phone projection stack] CarPlay = HomeKit pair → iAP2 → AirPlay H264/H265 (+CarPlay video) → AWDL for wireless. Android Auto = aasdk projection protocol. Dongles (Carlinkit) proxy the crypto; direct receivers (DiPlay/xcertplay/catplay/LIVI) implement it.
8. [AWDL] Apple Wireless Direct Link = the wireless transport under CarPlay+AirDrop; Linux impl exists (seemoo-lab/owl, archived GPLv3) — research only, no consumer wireless-CP-on-Linux product.
9. [Tuning stack] OEM locked ECU (bootloader sig + CP) vs open EMS (rusEFI/Speeduino/HaniCore) vs bench-flash gateway (J533/ContiTool). Pick by target: stock-tune vs standalone-swap vs gateway-level.
10. [Resource sites] VAG coding: vwcoding.ru, ilovecarmods.com, ross-tech.com wiki/tour, trick77.com (VIM), untanux.lt. Security meta: awesome-canbus, awesome-vehicle-security. Forum depth: OBD Eleven, MHH Auto, VW Vortex.
11. [Safety boundary] defensive knowledge only — no theft playbooks, immobilizer bypass, seed-key algorithms, or odometer fraud. Pirated tuning tools = active malware vector (brand-impersonation orgs on GitHub).
12. [Verification] star counts/activity point-in-time; prefer repos with hardware validation notes (e.g. CerberusCAN A6 C7 + live ODIS capture) over demo-only claims.
13. [Quarantine] UniCON-NECT, IE-Flash-Wizard, 034-SPI GitHub orgs = SEO-spam impersonating Unitronic/IE/034 tuning brands — never fetch binaries, treat as hostile.
14. [Decision tree] ask: what car + year + module? → what bus (K-line/CAN/DoIP)? → what session (OBD/UDS/security-access)? → what goal (read DTC / live data / adaptation / long-code / flash / key)? Map each answer to the matching skill file.
15. [Output] for any automotive answer cite: era → bus → protocol → tool/repo → trick-source. Never recommend a tool without era match.
