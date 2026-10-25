# Firmware update — RE status (gated)

**Status:** research only. The Linux companion **does not flash**. Do not run
`FirmwareConsole` or ISP helpers against a live pad until abort paths and
image→chip mapping for **f4 / device_id 85** are verified.

Evidence: Space Station **4.2.2.3** (`vendor/spacestation-4.2.2.3/`, gitignored).

## High-level flow (**S**)

```
Electron main  --spawn-->  firmware/FirmwareConsole.exe
        │                         │
        │  SwitchUsb /            ├── WCH55xISPDLL.dll     (WCH MCU ISP)
        │  SwitchToFirmwareUpgradeMode   ├── jl_firmware_upgrade_x64.dll  (Jieli .ufw)
        │  (SpaceStationService)  ├── CH375 / CH343 DLLs   (USB ISP helpers)
        │                         └── hidapi / STDFU.dll
        │
        └── offline assets: firmware/bin/controller/<device>/<line>/*
```

Electron IPC `firmware_upgrade_command` builds:

```text
FirmwareConsole.exe
  --device_id <code>          # e.g. f5
  --chip_module <int>
  --chip_type <int>
  --url <local path or URL>   # image file
  --vendor_id <hex4>          # Xbox 045e→04b4 for main/dongle
  --product_id <hex4>         # Xbox 028e→2412 for main/dongle
  [--pic_* --upgrade_type …]  # screen picture path only
```

Stdout progress: `Progress: N%`, success/failed keywords. (**S**, `main.js`)

## Chip modules (**S**, F5 migration table)

| Name | `chip_module` | `chip_type` (F5 table) | Asset prefix | Tooling |
|------|---------------|------------------------|--------------|---------|
| main | 0 | 5 | `main_chip_V*.bin` | WCH ISP / CH375 path |
| rf | 1 | 2 | `rf_chip_V*.bin` | (HID / CH path) |
| si | 2 | 9 | `si_chip_V*.ufw` | `JL_upgradeDevice` |
| screen | 4 | (device) | `screen_chip_*` | optional |
| dongle | 6 | (device) | `dongle_chip_V*.bin` | same family as RF (`KNLT` header) |

F5 offline bundles shipped under `firmware/bin/controller/f5/{4.0,5.0}/`.
**No `f4` offline images** are in this installer — Vader 4 Pro updates are
expected to use a downloaded `--url` (CDN), not a local tree.

## Online depot (**O**, 2026-10-24)

| Role | URL |
|------|-----|
| Firmware check API | `POST https://api.flydigi.com/pc/Update/firmware` |
| Device image CDN | `https://api-web.cdn.flydigi.com/devicefirmwares/YYYY/MM/DD/<file>.bin` |
| Space Station installers | `https://tencent-android.cdn.flydigi.com/PC/…` |

Check body (from Space Station renderer): JSON
`{device_code, device_id, app_version, main_chip, led_chip}` plus header
`appversion`. Success returns `data.chip_list.<chip>.{version,url,info,…}`.

Example (live): `device_code=f5` →
`http://api-web.cdn.flydigi.com/devicefirmwares/2026/09/20/F5P_MH2113_Refactor_V7226.bin`
(HTTPS works; COS has **no directory listing**).

**Vader 4 (`f4`) is absent from the SS4 `/pc/Update/firmware` catalog** (returns
“No firmware information found”). NSS index only lists `k5, f5, f5p, f5pro, fp4`.

### Space Station 3 catalog (works for f4) (**O**)

Installer:  
`https://tencent-android.cdn.flydigi.com/PC/Space%20Station3.0/FlydigiSpaceStation_setup_3.4.9.5_Release.exe`  
(extracted locally under `vendor/spacestation-3.4.9.5/`, gitignored).

Firmware metadata:

```http
GET https://api.flydigi.com/android/v3/Firmwares/pcNew?type=f4
```

Live response (2026-10-24):

| Field | Value |
|-------|--------|
| version | `6.9.3.3` (same as this pad’s current fw) |
| name | `VADER4_6.9.3.3` |
| package | `https://tencent-android.cdn.flydigi.com/firmware/F4/F4_Telink87_Gamepad_6933_1025.zip` |

Unpacked image: single `F4_Telink87_Gamepad_6933_1025.bin` (158 244 B), lead
bytes `… KNLT …` (Telink-family container — same magic as F5 RF/dongle bins).

**Update kind: full image** (not incremental). Archived in-repo at
[`archive/firmware/f4/6.9.3.3/`](../archive/firmware/f4/6.9.3.3/) with
`manifest.json` + SHA256.

### SS3 flasher wire (RE’d, 2026-10-24)

Source: decompiled `FmUpgradeSwViewModel.ota_write` + `DongleCommand` /
`CommandDic` / `GamePadModeService` under
`archive/firmware/f4/ss3-flasher-decompile/` — summary in
[`archive/firmware/f4/README.md`](../archive/firmware/f4/README.md).

| Step | Behaviour |
|------|-----------|
| Image | Full Telink `KNLT` bin; size `@+24`, CRC `@size-4` |
| Enter (Vader) | Ensure **DInput**; open USB **IF3** (`04b4:2412` usage **`FFEF`**, report **`5`**, 64 B). Daemon uses IF2 (`FFA0`) — different node. SoftUpgrade `05 F5 07` is HSH/dongle path, not default Vader. |
| Transfer | Chunked OUT: start `[2,2,0,1,FF…]`, then ≤3×`{index_le16, 16 B, crc16}`, finish with last-index + ones’-complement; ACK-driven on IN report 5 |
| CRC16 | init `FFFF`, bit-wise with table `{0, 0xA001}` over `{index, payload}` |

**Live flash (wired, 2026-10-24):** `scripts/ota-flash.py` same-version reflash of
archived `6.9.3.3` on IF3 succeeded (~36 s, device success status, still
`firmware=6.9.3.3`).

**Pre-flash checks (default):**
1. USB IF3 present; image size/CRC trailer sane
2. **Start+finish dry-run** (open → start OUT → require report-5 IN → **finish** OUT → close, **no data**)
3. Only then full write

OTA **start** alone puts the pad in firmware-update mode. Closing without
**finish** leaves it stuck there (Space Station then prompts to switch back to
standard mode). Preflight always finishes; a failed mid-flash also sends finish.
Recovery: `python3 scripts/ota-abort.py`.

No version allowlist — older pads are the ones that need updates; the dry-run
ACK is the gate. Full write was live-proven on `6.9.3.3`. `--no-preflight`
skips step 2 (not recommended).

## Native helpers (**O** PE exports)

`jl_firmware_upgrade_x64.dll`:

- `JL_loadUfwData`, `JL_getUfwCrc`, `JL_getUfwDataCrc`, `JL_getUfwPidVid`
- `JL_queryDevicePidVid`, `JL_upgradeDevice`

`WCH55xISPDLL.dll`:

- `WCH55x_SetIspOption`, `WCH55x_EnumDevices`, `WCH55x_FlashProgramB`,
  `WCH55x_FlashVerifyB`, `WCH55x_IspEnd`, …

`FirmwareConsole.exe` is a **71 MiB native AOT single-file** host
(`singlefilehost.pdb`), not a CLI-managed assembly. It dynamically loads the
DLLs above (`jl_firmware_upgrade_x64.dll`, `WCH55xISPDLL.dll`, `Libraries\x64\STDFU.dll`, …).

Updater class names inside the binary (**S** strings): `CH375Updater`,
`WCH59XUpdater`, `HidUpdater`, `IFirmwareUpdater`.

## Entering upgrade mode

**F4 (this pad):** already-DInput + open IF3 (`FFEF`) is enough — live-proven.
SoftUpgrade / XInput→OTA bytes exist for other products (see archive README).

**F5 / SS4:** `SwitchToFirmwareUpgradeMode` + `FirmwareConsole` / WCH / JL paths
are a separate stack; not used for Vader 4 Pro’s Telink HID OTA.

## Image notes (**O**)

Sample headers from F5 `5.0` (for format triage only — **not** Vader 4 images):

| File | Size | Lead bytes |
|------|------|------------|
| `main_chip_V7221.bin` | 208 172 | ARM-ish vector table (`30 a9 00 20…`) |
| `rf_chip_V1043.bin` / `dongle_chip_V0483.bin` | ~27 k | `KNLT` magic |
| `si_chip_V3605.ufw` | 355 104 | opaque UFW (JL CRC APIs) |

## Gate checklist

1. ~~Obtain authentic f4 image~~ — archived `6.9.3.3`.
2. ~~SS3 HID OTA framing~~ — IF3 / FFEF / report 5.
3. ~~Live same-version reflash~~ — `scripts/ota-flash.py` OK on this pad.
4. ~~UI~~ — Firmware tab: catalog check + flash local archive (wired IF3, confirm).
