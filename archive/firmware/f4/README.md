# Archived Vader 4 Pro firmware (`f4`)

## `6.9.3.3/` — full image (2026-10-24)

| | |
|--|--|
| Catalog | `GET …/android/v3/Firmwares/pcNew?type=f4` |
| CDN zip | `…/firmware/F4/F4_Telink87_Gamepad_6933_1025.zip` |
| Kind | **Full** single-bin image (not an incremental patch) |
| SHA256 | see `6.9.3.3/SHA256SUMS` and `manifest.json` |

Evidence it is full: one `.bin` in the zip; embeds `Flydigi VADER4` / `VADER4P`;
catalog uses absolute version URLs; SS3 `ota_write` streams the entire
`source_binchar` buffer in 16-byte cells with per-cell CRC16.

Bin header (SS3 loader): `u32 size @ offset 24`; CRC trailer at `size-4`;
`u32 version @ offset 2`. Payload padded with 16×`0xFF` after `size`.

## Flasher RE (SS3 3.4.9.5)

Decompiled types under `ss3-flasher-decompile/` from
`FlydigiSpaceStation.dll`, `LibCommon.dll`, and
`Service/GameController.ServiceHandler.dll`.

### Device open

- HID `VID 04B4` / `PID 2412`, usage page **`FFEF`** (gamepad; dongle uses
  `FFEE` / HSH `FFB1`).
- Report ID **`5`**; write via `FileStream.Write` of `OutputReportByteLength`.

### Enter path (before OTA)

For non-HSH pads (Vader):

1. If currently XInput → `GamePadModeService.SwitchMode("DInput")` → service
   sends XInput subcmd **`23`** (`CommandDic.SwitchDinput`).
2. Poll until `FindDeviceNew(04B4,2412,FFEF,…)` succeeds.
3. If already DInput, SS3 does **not** send SoftUpgrade — it just opens FFEF.

Related SoftUpgrade / OTA-entry bytes (used for HSH / dongle / Android paths,
not the default Vader path):

| Path | Bytes (report 5…) |
|------|-------------------|
| DInput → OTA | `05 F5 07` (`getSwitchAndroid2OTA`) |
| SoftUpgrade (MCU-dependent) | `05 F5/F6 xx` (`GetSoftUpgradeCmd`) |
| XInput → OTA | XInput `getSendData(48, 15)` (`K1CmdID` + `XinputToOTACmd`) |

### `ota_write` framing (ACK-driven)

Every OUT starts with report ID `5`. Body (after ID):

**Start** (`start_ota_flag` 1→2):

```text
[2, 2, 0, 1, 0xFF, …]
```

**Data** (flag==2): up to 3 cells of 20 bytes each; length byte =
`20 * cells`. Cell layout:

```text
index_lo, index_hi, payload[16], crc16_lo, crc16_hi
```

- `index` is a 16-byte cell index into the image.
- CRC16 over `{index_lo, index_hi, payload[16]}` (poly table `{0, 0xA001}`,
  init `0xFFFF` — see `FirmwareUpgradeUtils.crc16`).
- Next chunk is sent only after an IN report on ID 5 (any response while
  `start_ota_flag != 0` triggers another `ota_write`).

**Finish** (when no more data / length byte would be 0):

```text
[2, 6, 0, 2, 0xFF, last_index_lo, last_index_hi,
 (0x10000 - last_index)_lo, (0x10000 - last_index)_hi, …]
```

**Success IN** (device):

```text
[5, 2, 3, 0, 6, 0xFF, status]
```

`status==0` → OK.

### Live flash (2026-10-24, wired DInput)

| | |
|--|--|
| Scripts | `scripts/ota-dry-run.py` (start only), `scripts/ota-flash.py` (full) |
| Channel | USB **IF3**, usage **`FFEF`**, report **5**, 64 B (daemon stays on IF2) |
| Dry-run | Start OUT → report-5 IN echo |
| Full reflash | Archived `6.9.3.3` same-version; ~36 s; device OTA success status; post `firmware=6.9.3.3` |
| Safety | Flash always does start dry-run first (abort if no ACK). No version allowlist — older pads are the update audience. |
