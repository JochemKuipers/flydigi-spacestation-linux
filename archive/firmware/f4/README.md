# Archived Vader 4 Pro firmware (`f4`)

## `6.9.3.3/` — full image (2026-10-24)

| | |
|--|--|
| Catalog | `GET …/android/v3/Firmwares/pcNew?type=f4` |
| CDN zip | `…/firmware/F4/F4_Telink87_Gamepad_6933_1025.zip` |
| Kind | **Full** single-bin image (not an incremental patch) |
| SHA256 | see `6.9.3.3/SHA256SUMS` and `manifest.json` |

Evidence it is full: one `.bin` in the zip; embeds product strings
(`Flydigi VADER4` / `VADER4P`); catalog uses absolute version URLs; SS3
`ota_write` streams the entire `source_binchar` buffer in 16-byte cells.

## Flasher notes (SS3 `FmUpgradeSwViewModel`)

Decompiled snippets under `ss3-flasher-decompile/` (from
`FlydigiSpaceStation.dll` 3.4.9.5).

- Opens HID `04b4:2412` on usage page **`FFEF`** (default), or `FFB1` /
  `FFEE` for other products.
- Report ID **`5`** OUT; OTA framing:
  - start: `[2, 2, 0, 1, 0xFF, …]`
  - data: up to 3× `{index_lo, index_hi, 16 payload, crc16_lo, crc16_hi}`
  - end: `[2, 6, 0, 2, 0xFF, last_index_le, (0x10000-last)_le, …]`
- Image size/CRC taken from header/`size-4` trailer after load.

Enter-ISP / mode-switch command path still TBD before any Linux flash UI.
