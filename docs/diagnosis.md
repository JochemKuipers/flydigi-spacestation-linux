# Vader 4 Pro DInput on Linux — diagnosis

**Host:** CachyOS, kernel `7.3.0-5-cachyos`  
**Capture date:** 2026-10-24  
**Link under test:** 2.4 GHz dongle presenting as USB `04b4:2412` “Flydigi VADER4”

## Verdict (observed)

DInput mode is **not dead**. The pad enumerates and streams. Linux fails to expose the **full** DInput feature set as one gamepad because:

1. The complete report (buttons including C/Z/M1–M4, analog sticks/triggers, IMU) is on **HID interface 2**, vendor usage page `0xFFA0`, **report ID `0x04`**, magic byte `0xFE` (Flydigi “V1” layout).
2. `hid-generic` binds that interface but **does not map** vendor-page reports into an input device.
3. Interface 0 is a **reduced** standard Game Pad descriptor → incomplete `js0`/`event*`.
4. Interface 1 is a **boot mouse** → extra `mouse*` node that confuses some stacks.

So the root cause is **missing driver binding / presentation of IF2**, not a missing Windows-only USB reset for basic streaming. Streaming on IF2 was observed **without** any Space Station handshake.

## Observed USB layout (`04b4:2412`)

| IF | Class | Endpoints | Report descriptor | Kernel binding | Userspace nodes |
|----|-------|-----------|-------------------|----------------|-----------------|
| 0 | HID Game Pad | IN 0x81 (64 B) | 125 B standard gamepad | `hid-generic` | `js*` / `event*` (incomplete) |
| 1 | HID Boot Mouse | IN 0x82 | 70 B mouse | `hid-generic` | `mouse*` |
| 2 | HID vendor `0xFFA0` | IN 0x83, OUT 0x05 | Report `0x04` IN 31×i8, `0x05` OUT 31×i8 | `hid-generic` | **hidraw only** |
| 3 | HID vendor `0xFFEE` | IN 0x84 | Report `0x05` 63 B in/out/feature | `hid-generic` | hidraw (config/command) |

Report descriptors saved under `captures/report-descriptors/`.

## Live IF2 sample (idle)

hidraw on `…/input2` continuously produced 32-byte reports:

```text
04 fe 66 00 00 00 00 00 00 00 00 00 ff ff ff ff 00 01 7f 00 7f 00 7f 7f 00 00 00 00 00 00 ff ff 00
```

- Byte 0 = `0x04` (report ID)  
- Byte 1 = `0xFE` (V1 magic)  
- Stick centers at offsets 17/19/21/22 = `0x7F`  
- Triggers at 23/24 = `0x00`

This matches SDL’s `HIDAPI_DriverFlydigi_HandlePacketV1` gate (`data[0]==0x04 && data[1]==0xFE`) and axis offsets. **Confirmed on this hardware.**

## Mode switching

| Claim | Status |
|-------|--------|
| PC/DInput = blue LED; chord FN/O + A | **Community / Space Station docs** — LED color not instrumented in our capture |
| Dongle VID/PID in DInput = `04b4:2412` | **Observed** |
| XInput uses Xbox VID (`045e:028e`) | **Community** — not captured here |
| Bluetooth DInput extras incomplete vs dongle | **Community** — BT not captured yet |

## Init / handshake

| Claim | Status |
|-------|--------|
| IF2 streams report `0x04` without userspace init | **Observed** |
| Space Station `AcquireController` / raw-data / third-party flags needed for config or Steam | **Inferred** from app strings (`AcquireControllerCommandFactory`, `EnableRawData…`) — not required for IF2 input stream in our sample |
| IF3 (`0xFFEE`) is the config channel | **Inferred** from descriptor + Space Station shipping `hidapi.dll` |

## What “doesn’t work” means on stock Linux

Apps that open the **joystick** from IF0 miss paddles/C/Z/gyro as a coherent device. Apps that need the Windows DInput extended report must open **hidraw IF2** (or a userspace/kernel driver that republishes it). Steam’s workaround (udev `uaccess` + Steam Input) is deliberately **out of scope** for this project.

## Bluetooth DInput (blue)

BT presents a standard HID Game Pad (`d7d7:0041`) plus Consumer Control extras (Z=`KEY_ENTER`, M-pads as media keys). That path is **input-capable** once remapped; LED / rumble / onboard profiles still need IF2 over **dongle or USB** — same limit as official Space Station. Details: [bluetooth.md](bluetooth.md).

## Evidence files

- `captures/dongle-host-full.txt`, `captures/lsusb-v.txt`
- `captures/hidraw-samples.txt`
- `captures/report-descriptors/iface{0,1,2,3}.*`
- REA: ASAR summary `ev_640629853a19aa75669492283ddbff95a71ff8f790c37839b3bbac5d747c9144`
- Space Station extract: `vendor/spacestation-4.2.2.3/app/` (Electron 36 + `SpaceStationService.exe` NativeAOT-like PE)
