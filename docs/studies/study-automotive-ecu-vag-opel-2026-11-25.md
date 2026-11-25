# Automotive Domain Knowledge Acquisition — 2026-11-25

**Scope:** deep-research mission (deep-research-prompt v2.0 adapted for domain-expertise acquisition): automotive mechanics, electrics/electronics, engine types (all), ECU internals, diagnostics — with maximum focus on **Volkswagen Group (VAG)** and **Opel/Vauxhall**, plus vehicle-security research ("hacks" — defensive framing only)
**Run date:** 2026-11-25 · **Personas:** SEC primary (`security-auditor` + `security-lord` + `reverse-engineering-lord`) + ARCH secondary (order override: GROWTH → SEC — keyword false-positive)
**Runtime gate:** `aizee check deep-research` — all 6 gates allow
**Run workspace:** `temp/auto-research-2026-11-25/` (coverage map, claims ledger, decoded curated lists)
**Output:** 6 knowledge files internalized into `tech-stack/` (see §2) — the user's explicit objective ("internalize the knowledge") authorized this propagation target

---

## 1. Executive summary

GitHub discovery (30+ searches) + two decoded curated awesome-lists (~87KB of ecosystem inventory) + deep README extraction of the four most important repos + broad web research produced a verified evidence base covering: the full CAN/diagnostics tooling ecosystem, VAG platform/engine/ECU genealogy with firmware-level internals (Simos18 exploit chain, ME7 openness), Opel's three diagnostic eras (classic GM → Global-A → PSA), the tuning/flashing toolchain landscape, vehicle-security attack classes with defenses, and the regulatory layer (ISO/SAE 21434, UN R155/R156).

**Key structural finding:** automotive diagnostic reality is *era-segmented*, not brand-monolithic. VAG splits pre/post-MQB-evo (SFD); Opel splits three ways (GM classic / Global-A / PSA — where Corsa F is a PSA car in Opel clothing and GM-era tools simply do not apply). Any future automotive work must start from era identification before tool selection.

**Safety position (SEC persona enforced):** security knowledge is internalized defensively — attack classes, detection, hardening. No theft playbooks, immobilizer-bypass procedures, key-cloning instructions, or odometer-fraud methods were internalized or will be produced. Pirated/cracked tuning software identified as an active malware vector (brand-impersonation orgs found live on GitHub: `UniCON-NECT`, `IE-Flash-Wizard`, `034-SPI` — all created 2026-11-22).

## 2. Knowledge files written (durable internalization)

| File | Size | Contents |
|------|------|----------|
| `tech-stack/automotive-core.md` | 14.8 KB | Vehicle systems, ICE fundamentals, ALL engine types (inline/V/VR/boxer/rotary/Atkinson), diesel/petrol fuel systems, ALL EV motor types (PMSM/induction/EESM/SRM/axial-flux), hybrid topologies P0–P4, HV battery/BMS/charging, vehicle networks (CAN/FD/LIN/FlexRay/MOST/Ethernet/K-Line), working discipline |
| `tech-stack/automotive-diagnostics.md` | 12.5 KB | OBD-II/DTC structure, diagnostic protocol stack (KWP1281/KWP2000/TP2.0/ISO-TP/UDS/DoIP), scan-tool landscape, python-can/Scapy/DBC toolchain, ELM327 reality, professional workflows |
| `tech-stack/automotive-vag.md` | 15.3 KB | Platforms PQ→MQB/MLB/MEB/PPE/SSP, engine families EA111/211/888/855/839/189/288 + code system, ECU genealogy ME7→MED9→MED17→Simos→MG1, TriCore internals, SFD/component-protection/GeKo/immo generations, VCDS/ODIS/OBDeleven ecosystem, coding/adaptation mental model, 12 verified OSS repos incl. bri3d/VW_Flash toolchain |
| `tech-stack/automotive-opel.md` | 10.1 KB | THE three diagnostic eras, GMLAN bus architecture (HS/MS/LS-SWCAN), engine families (Family 0/I/II, CDTI lineage incl. Fiat/Isuzu sources, PSA transition), CarPass/security-code model, OP-COM/Tech2/GDS2/SPS/TIS2Web/DiagBox tooling, verified OSS repos incl. GMLAN RE projects |
| `tech-stack/automotive-ecu-internals.md` | 9.5 KB | MCU architectures (TriCore/C167/MPC5xxx), flash layouts + boot chains (SBOOT/CBOOT/ASW/CAL), checksum layers, BSL/bench/OBD access paths ranked, tuning ecosystem (WinOLS/XDF/DAMOS/slave-master tools), open-source engine management (rusEFI/Speeduino/HaniCore/openinverter), 6-step RE workflow |
| `tech-stack/automotive-security.md` | 10.2 KB | CAN-injection theft class (CVE-2023-29389), relay/RollJam/remote-compromise chains, sensor spoofing, ISO/SAE 21434 TARA + R155/R156, pentest methodology + gallia/CaringCaribou/ICSim tooling, countermeasures (SecOC, segmentation, IDS), owner/fleet defense checklists — all defensive |
| `tech-stack/automotive-tricks.md` | 23.5 KB | **Second-pass (user-requested)**: hidden-features/tweaks/mods knowledge — verified VAG coding tweaks (module/byte/bit level: needle sweep, start-stop voltage trick, Soundaktor kill, comfort blinkers, dev-mode S12345 matrix), MIB2 green menu, retrofit master pattern (gateway installation list → dependent modules → calibration; verified RVC + ACC chains), Opel variant-config tricks (cruise control 3-module coordination, DIS code-index, CarPass ops), used-module reuse playbook (virginize/clone/adapt + where pairing data lives), tuning tweak features (launch control, NLS, pops/bangs mechanism + costs, TCU remaps), mechanical workshop tricks (EA888 chain-stretch via block 93, PCV→rear-main cascade, Haldex pre-filter), electrical/service tricks (EPB mode, battery registration, injector coding, CAN 60Ω test) |

## 3. Highest-value verified repos (for future work)

- **bri3d/VW_Flash** — canonical MQB flashing: Simos18.x + DQ250/DQ381 + Haldex Gen5; FRF/ODX extractors with AUDI AES+LZSS decryption; checksum fixers. Companion: TC1791_CAN_BSL, Simos18_SBOOT, sa2_seed_key, a2l2xdf.
- **JoeeDeveloper/OpenDiag** — new (2026-11) Rust VCDS-alternative: ISO-TP/UDS/KWP2000/KW1281/TP2.0, read-only-first design, simulator-tested; best open foundation for VAG diagnostics.
- **Fraunhofer-AISEC/gallia** — reference UDS pentest framework, reproducible artifact logging.
- **commaai/opendbc** — production-grade DBCs incl. `vw_pq/mqb/mqbevo/mlb` + `gm_global_a_*` + `opel_omega_2001` — best free signal references for both target brands.
- **MartinHani/HaniCore** — open standalone firmware for ME7 hardware (C167) — proof the platform is fully open.
- **Forbes-Automotive/OpenHaldex-C6**, **PNKP237/EHU32** (Opel ESP32 comfort-CAN worked example), **maxpfeif/GMLAN+garnerm91/SWCAN** (GM/Opel bus hardware+decode), **roffe/gocanflasher** (GM-family CAN flashing method reference).
- Ecosystem inventory: awesome-canbus + awesome-vehicle-security lists decoded to `temp/auto-research-2026-11-25/` (cantools, canmatrix, cabana, CaringCaribou, CANToolz, ICSim/UDSim, python-can, python-OBD, python-udsoncan, iso14229, SavvyCAN, ELM327-emulator…).

## 4. Coverage notes and gaps

**Covered at depth:** VAG (platforms, engines, ECUs, firmware internals, diagnostic software, SFD/CP, tuning), Opel (eras, GMLAN, engines, tooling), generic mechanics/electrics/networks, security research, regulations, tuning ecosystem, open-source EMS.

**Known gaps (future passes if user wants):**
1. Mercedes/BMW/Ford/Toyota brand-depth (out of requested scope; only security-relevant facts included).
2. Heavy-duty/J1939 (TruckDevil noted, not expanded).
3. Motorcycle diagnostics (KW1281-adjacent, not expanded).
4. Live-harness practical pinouts per model year (documented where verified; per-model specifics belong in case-by-case work, not durable knowledge).
5. Renault/PSA pre-Stellantis depth (DiagBox covered for Opel-era relevance only).

**Evidence quality:** firmware-level claims (Simos18 layout, exploit chain, checksum layers, ME7 bench methods) rest on hardwear.io published research + bri3d documentation + simoswiki + vagpulse — consistent across independent sources. Tooling-era claims (Opel three eras, VAG SFD rollout) verified against vendor documentation (Ross-Tech, OBDMarket, VW terms-of-use). Claims ledger: `temp/auto-research-2026-11-25/claims-ledger.md`.

## 5. Loading guidance

Lazy-load pattern: `automotive-core` is the foundation layer — load it first for any automotive task, then the relevant specialization (`automotive-vag` / `automotive-opel` / `automotive-diagnostics` / `automotive-ecu-internals` / `automotive-security`). Cross-references are declared in each file's `[COMPAT]` block. These are versionless domain files (no lockfile dependency), following the `react-ecosystem.md` precedent rather than `{pkg}-{ver}` naming.
