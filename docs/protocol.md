# Flydigi Vader 4 Pro protocol notes (Space Station 4.2.2.3)

Legend: **O** = observed on hardware · **S** = from shipped Space Station 4.2.2.3 · **C** = cross-check (SDL / flydigictl) · **I** = inference

## Identities

| Role | VID:PID | Notes |
|------|---------|-------|
| Wired / 2.4G DInput composite | `04b4:2412` | **O** on dongle + wired |
| Device code in Space Station configs | `f4` | **S** `Configs/Controller/f4/` |
| Onboard device ID (cmd 236) | `85` | **O** on this pad; maps to `default_mapping_85.dat` (**S**) |

## Input report — IF2, V1 (`04 FE…`)

**O** + **C** (SDL `SDL_hidapi_flydigi.c` V1). Packet length 32 including report ID.

| Offset | Field | Notes |
|--------|-------|-------|
| 0 | Report ID | `0x04` |
| 1 | Magic | `0xFE` |
| 7 | M1–M4, C, Z | M1=`0x04` … C=`0x01`, Z=`0x02` (**C**) |
| 8 | FN + Guide | FN/◯=`0x01` (gyro-mouse chord; SDL hides it); Guide=`0x08` (**C**) |
| 9 | Hat + A/B/Select/X | hat=`&0x0F`; A=`0x10`, B=`0x20`, Back=`0x40`, X=`0x80` |
| 10 | Y/Start/LB/RB/LS/RS | Y=`0x01`, Start=`0x02`, LB=`0x04`, RB=`0x08`, LS=`0x40`, RS=`0x80` |
| 11–16 | Accel | int16 pairs (**C**) |
| 17,19 | Left stick X,Y | u8, center `0x7F` (**O**) |
| 21,22 | Right stick X,Y | u8, center `0x7F` (**O**) |
| 23,24 | LT, RT | u8 0–255 (**O**) |
| 18,20,26–30 | Gyro | int16 packing per SDL V1 (**C**) |

## Command channel — same IF2, report `0x05`

**O** + **C** (flydigictl `protocol/dinput`). Host writes 12-byte OUT reports: `[5, cmd, args…]`.

Responses are non-`04 FE` packets; many put the echoed command ID in byte `[15]`.

| Cmd | Name | Notes |
|-----|------|-------|
| `0x0F` (15) | Haptic / rumble | OUT report 5, 32 B: `[5, 0x0F, lo, hi, 0…]` (SDL V1 high-bytes). Motors need ~25 ms refresh while active — one-shot feels dead (**O**, live-verified 2026-10-24) |
| 17 | Dongle version | response `[4, 17, FW_L, FW_H]` (**C**) |
| 229 | Read LED config | parcels; byte `[15]==229`, chunk idx in `[3]`, 10 data bytes `[5:15]`; **49** chunks (**C**/**O**) |
| 231 | Write LED start | followed by inner parcels cmd **51** (**C**) |
| 234 | Write gamepad config start | inner parcels cmd **34** (**C**) |
| 235 | Read gamepad config | **52** chunks × 10 → 520 bytes (**O**) |
| 236 | Get device info | **O**: device_id=`[3]`, mac=`[5:9]`, FW_L/H=`[9]/[10]`, battery=`[11]`, cpu=`[12]`, conn=`[13]`, motion=`[14]`, cmd=`[15]` |

### Device info example (**O**)

`device_id=85`, firmware `6.9.3.3` (from FW_L/H nibble packing), battery step 4 → 100%, connection 0 (dongle).

### LED config blob

Header 20 bytes + up to 16×10 RGB units (one group per LED; units = animation
keyframes). `loop_start`/`loop_end` select the active frame range; `loop_time`
is step delay (higher = slower). Modes match SS4 `LED_TYPE_*`: 0 off/unknown,
1 FLOW, 2 BREATH, 3 GRADIENT, 4 FEEDBACK, 5 ON, 6 Close (**SS4** / **C**).
Gradient rainbow uses 7 phase-shifted frames (`loop_end=6`) — same packing as
SS4 cooler `RGB_EFFECT_RAINBOW`. Write via parcelized cmd 231/51.

### Gamepad config blob (V2 offsets, **SS4**/**C**/live **O**)

Same onboard profile blob Space Station 4 reads/writes for F4 (slot `config_id`,
currently 0 in our daemon). UI hotspots: `app/ui/assets/ss4/device_config_f4.json`.

| Range | Field |
|-------|-------|
| 0–1 | Version |
| 2 | Package length (+1 on wire) |
| 3–12 | Legacy LED (10 B) |
| 13–108 | Key map (32×3: map_id, turbo_type, turbo); `255` = native; slot id = SS4 key id |
| 109–122 | Stick curves (2×7: type, zero/deadzone, p0x, p0y, p1x, p1y, end) |
| 123–136 | Trigger curves (2×7) |
| 137–144 | Motion |
| 145–153 | Motors (main_switch, L/R type/min/max/scale) |
| 154+ | Trigger motors / lunpan / macros / padding → 520 B total |

## IF3 (`0xFFEE`)

Descriptor present (**O**). Live DInput companion traffic for this pad uses **IF2** exclusively (flydigictl + our captures). Treat IF3 as unused for the Linux stack unless a future Space Station path requires it.

## Multiplex on Linux

`flydigi-vader4d` owns IF2 hidraw, publishes uinput, and serves `$XDG_RUNTIME_DIR/flydigi-vader4d.sock` (JSON lines). Companion UI/CLI never open hidraw while the daemon runs.

## Firmware update (**S**, gated)

Tree: `firmware/` + `FirmwareConsole.exe` + ISP DLLs (`jl_*`, `WCH55x*`, CH375).
CLI: `--device_id --chip_module --chip_type --url --vendor_id --product_id`.
This Space Station build ships **f5** offline images only — not f4.
Full write-up: [firmware.md](firmware.md). Linux UI stays locked.

## Mode switching

DInput vs XInput vs Switch change USB identity (**C**/**I**). This stack targets **PC/DInput** (`04b4:2412`).

## Bluetooth

See [bluetooth.md](bluetooth.md). Enumerator already accepts `Flydigi*VADER*` hidraw by name; VID:PID lock waits on a live capture.
