---
name: carplay-headunits
description: CarPlay/Android Auto protocol stack, open-source receivers (3 generations), dongle RE/firmware, AWDL transport, brand-specific headunit enablers, MFi-identity reality. Load for CarPlay/AA/headunit/dongle questions.
triggers:
  - carplay
  - apple carplay
  - android auto
  - head unit
  - headunit
  - hu
  - mib
  - discover media
  - dongle
  - carlinkit
  - autoboy
  - autobox
  - iap2
  - awdl
  - airplay
  - aasdk
  - wireless carplay
  - byd dilink
  - hmg
  - nbt
---

[SKILL] carplay-headunits
[OBJ] Know the CarPlay/Android Auto open-source ecosystem: protocol layers, receiver generations, dongle firmware, transport research, and brand-specific enablers.
[COMPAT] skills/auto-domain-map.md, skills/obd-diagnostics.md (for CAN-side headunit comms), tech-stack/automotive-tricks.md
[RULES]
1. [REQ] CarPlay stack layers: (1) HomeKit pairing (SRP-6a + ed25519) → (2) iAP2 accessory protocol (USB or Wi-Fi) → (3) AirPlay audio/video (H.264, CarPlay Ultra adds H.265 video channel) → (4) wireless transport = AWDL tunnel. Every open repo maps to one layer.
2. [REQ] CarPlay receiver generations: (a) dongle-proxy apps — FastCarPlay (GPLv3 C++, Carlinkit/Autobox client, Pi Zero 2W), react-carplay (MIT Electron, cpc200, canbus camera trigger), pycarplay/carplay-client (AutoBox lineage, original Tesla-HU client); (b) full-protocol reimplementations — catplay (Rust, from-scratch iAP2+HomeKit+MFi), OpenXPlay-Relay (AGPLv3 rust crates carplay-iap2/carplay-airplay), LIVI (Rust+Slint GPLv3, 1212★, wired+wireless, hw decode, ships LIVI OS + Link dongle); (c) MFi-chip Android receivers — xcertplay, DiPlay (reuse Carlinkit-recovered accessory identity).
3. [REQ] Android Auto stack: opencardev/aasdk (protocol lib) + crankshaft (GPLv3, 2703★, turnkey RPi→AA headunit) = canonical; andreknieriem/open-headunit (AGPLv3, 3469★, Android device→AA receiver, WiFi Direct/hotspot/server); f1xpl/aasdk+openauto (original emulator, 2024-12); mrmees/open-android-auto (248 .proto files, AA v16.1–17.3 RE'd from APK + Sony XAV); mossyhub/openautolink (AA+CarPlay for GM EV AAOS, newest); mretallack/AndroidAuto (phone→HU, WIP).
4. [REQ] Dongle RE: ludwig-v/wireless-carplay-dongle-reverse-engineering = full Carlinkit/CPlay2Air doc (i.MX6UL + macronix 16MB, fw structure, root exploits, U2W/U2AW/U2AC segmentation); catplay-labs/catplay ships Carplay2Air open firmware (Ingonic X1600EN, successor to Carlinkit Mini Ultra); Henkru/cplay2air-wifi-passphrase-patch = static-passphrase binary patch.
5. [REQ] AWDL (Apple Wireless Direct Link): seemoo-lab/owl (GPLv3, archived — Linux/macOS AWDL for AirDrop RE), opendrop (9964★ AirDrop impl + keychain extractor), t4t5/owly (airdrop non-apple), seemoo-lab/proxawdl (TCP-over-AWDL via NetService exploit). Wireless CarPlay tunnels USB session over AWDL — no consumer Linux wireless-CP product exists yet.
6. [REQ] Brand enablers (the tricks frontier): BYD DiLink → DiPlay (CarPlay, xcertplay-based, GPLv3, wired+wireless, HUD nav, v0.2.22) + DiAuto (AGPLv3) + CarLink (unified auto-detect); BMW NBT (QNX 6.5 x86) → nbt-android-auto (wired AA+CP, iDrive+cluster nav); HMG-API Gen5W → hmgapi-wireless-cp-aa (wireless CP+AA, cluster/HUD); Autochips AC8257 Android HU → riazosama/headunit-carplay; embedded → mbt28/lehu (GPLv3 Rust, Allwinner F1C200s 64MB, CP+AA wired+wireless).
7. [REQ] MFi-identity reality: non-MFi receivers reuse Carlinkit-recovered accessory identities (bundled private key = extractable → not Apple-certified, ToS/distribution risk). DiPlay docs state this honestly. catplay implements MFi from scratch = cleaner legal position but harder.
8. [REQ] Headunit-side enablement: factory CarPlay/AA on Android HUs often = engineering-mode unlock + app install (DiPlay model: no jailbreak/dongle/Mac needed, APK install, local auth). AC8257/Autochips + BYD DiLink + HMG are the documented families.
9. [REQ] When advising: distinguish dongle-proxy (needs $30 Carlinkit hardware, easiest) vs direct-receiver app (free software, needs compatible HU + identity) vs full-receiver product (LIVI/catplay firmware, most control). Match to user's head unit OS + budget + legality tolerance.
10. [PROHIBIT] No MFi credential theft guidance, no Apple-cert bypass instructions — knowledge of identity reuse is fine, harvesting keys is not.
11. [VER] For VAG/MIB-side headunit coding (MIB2 dev-mode, GEM, exlap) load `skills/vag-diagnostics.md`; generic car-OS context → `skills/auto-domain-map.md`.
