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
Saved under `vendor/firmware-f4/` (gitignored).

Flash still gated until enter-ISP IF2 framing is recovered; fetching the image
does **not** enable the Linux updater UI.

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

## Entering upgrade mode (**S**, incomplete wire)

`SpaceStationService` exposes `SwitchToFirmwareUpgradeModeCommandDInput` (and
XInput variants). Electron issues `IpcCommandEnum_SwitchUsb` with
`chipModule`/`chipType` before each F5 migration phase, waits for reconnect,
then spawns FirmwareConsole.

Exact IF2 OUT bytes for DInput enter-ISP are **not** recovered yet — required
before any Linux flash attempt. Cooler SDK also has
`SwitchToFirmwareUpgradeMode` (separate product path).

## Image notes (**O**)

Sample headers from F5 `5.0` (for format triage only — **not** Vader 4 images):

| File | Size | Lead bytes |
|------|------|------------|
| `main_chip_V7221.bin` | 208 172 | ARM-ish vector table (`30 a9 00 20…`) |
| `rf_chip_V1043.bin` / `dongle_chip_V0483.bin` | ~27 k | `KNLT` magic |
| `si_chip_V3605.ufw` | 355 104 | opaque UFW (JL CRC APIs) |

## Gate checklist (must all clear before enabling UI)

1. Recover DInput `SwitchToFirmwareUpgradeMode` / `SwitchUsb` IF2 framing on **this** pad (device_id 85).
2. Obtain authentic **f4** image set (or prove which F5 assets apply — they likely do not).
3. Map each chip_module → updater class → USB VID/PID in ISP mode.
4. Document abort / power-loss behaviour; prefer wired; never BT.
5. Dry-run FirmwareConsole against a disposable unit or with ISP enumerate-only.

Until then the companion Firmware tab stays disabled.
