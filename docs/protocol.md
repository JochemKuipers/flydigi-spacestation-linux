# Flydigi Vader 4 Pro protocol notes (Space Station 4.2.2.3)

Legend: **O** = observed on hardware · **S** = from shipped Space Station 4.2.2.3 · **C** = cross-check (SDL / community) · **I** = inference

## Identities

| Role | VID:PID | Notes |
|------|---------|-------|
| Wired / 2.4G DInput composite | `04b4:2412` | **O** on dongle |
| Device code in Space Station configs | `f4` | **S** `Configs/Controller/f4/` |
| Mapping default files | `default_mapping_{85,91,105}.dat` | **S**; `105` matches flydigictl “device ID 105” (**C**) |

## Input report — IF2, V1 (`04 FE…`)

**O** + **C** (SDL `SDL_hidapi_flydigi.c` V1 handler). Packet length 32 including report ID.

| Offset | Field | Notes |
|--------|-------|-------|
| 0 | Report ID | `0x04` |
| 1 | Magic | `0xFE` |
| 7 | M1–M4, C, Z bits | M1=`0x04`, M2=`0x08`, M3=`0x10`, M4=`0x20`; C=`0x01`, Z=`0x02` (**C**) |
| 8 | Guide / misc | Guide=`0x08` (**C**) |
| 9 | Hat nibble + A/B/Select/X | hat=`&0x0F`; A=`0x10`, B=`0x20`, Back=`0x40`, X=`0x80` (**C**) |
| 10 | Y/Start/LB/RB/LS/RS | Y=`0x01`, Start=`0x02`, LB=`0x04`, RB=`0x08`, LS=`0x40`, RS=`0x80` (**C**) |
| 11–16 | Accel | int16 pairs (**C**) |
| 17,19 | Left stick X,Y | u8, center `0x7F` (**O**/**C**) |
| 21,22 | Right stick X,Y | u8, center `0x7F` (**O**/**C**) |
| 23,24 | LT, RT | u8 0–255 (**C**; idle **O** = 0) |
| 18,20,26–30 | Gyro components | int16 packing per SDL V1 (**C**) |

Output on same interface: report ID `0x05`, 31 payload bytes (**O** descriptor). Rumble V1 command shape in SDL: `{0x05, 0x0F, lo, hi}` (**C**, unverified on this pad).

## Config / feature channel — IF3

Descriptor: usage page `0xFFEE`, report `0x05`, 63-byte in/out/feature (**O**).

Space Station ships `hidapi.dll` and **.NET NativeAOT** PEs (`SpaceStationService.exe`, `FirmwareConsole.exe` — no CLI directory; Ghidra reports NativeAOT metadata). REA Evidence: open_binary Ghidra on `SpaceStationService.exe` SHA-256 `9116d63a…`, overview `ev_1988c46a…` (15207 procedures).

**S** type/method name inventory (from `strings`, not yet byte-verified) includes separate DInput vs XInput factories, among them:

- `DInputProtocol`
- `AcquireControllerCommandFactory` / `AcquireController`
- `EnableRawDataTransportInCommandDInput` / `EnableRawDataInput` / `enableRawData`
- `EnableThirdPartyAppControl` / `CheckThirdPartyAcquiredController`
- `ApplyMappingConfigByCfgIdCommandDInput`
- `EnableJoystickReboundCommandDInput`, `EnableJoystickDebounceCommandDInput`, `EnableJoystickAutoCalibrationCommandDInput`
- `EnableMotionDebounceCommandDInput`
- `CalibrationAdcCommandDInput`
- `DongleInfoControllerCommandDInput`
- `DeviceMaskCommandDInput`

Full filtered dump: `captures/service-protocol-strings.txt`.

Exact wire bytes for Vader 4 command IDs/CRC are **not yet verified** on this pad. Newer `0x37D7` pads (openflydigi) use a framed command set that must not be assumed identical for `04b4:2412` without a live capture or decompilation of the DInput factories.

## Firmware update (**S**, unverified on Linux)

Tree: `firmware/` including `FirmwareConsole.exe`, `jl_firmware_upgrade_x64.dll`, WCH/CH375 ISP DLLs, `firmware/bin/controller/`.  
**Safety:** flash path must be reverse-engineered and prefer wired before enabling in the Linux UI.

## Mode switching

- DInput vs XInput vs Switch change USB identity and which interfaces appear (**C**/**I**).
- Companion app mapping apply has separate DInput / XInput / NewXInput command factories (**S** strings).
