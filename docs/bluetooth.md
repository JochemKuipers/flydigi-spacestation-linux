# Bluetooth path

## Live capture — white LED (2026-10-24)

| Field | Value |
|-------|-------|
| Status LED | **White** |
| Mode | **XInput** (firmware) |
| BlueZ name | `Xbox Wireless Controller` |
| HID ID | `0005:045E:02E0` (Bluetooth bus) |
| Modalias | `usb:v045Ep02E0d0903` |
| Kernel driver | `microsoft` (`hid-microsoft`) |
| Input node | `/dev/input/event*` — standard Xbox pad axes/buttons + FF rumble |
| Flydigi VID/PID | **absent** — no `04b4:2412`, no `Flydigi*VADER*` hidraw |
| Raw captures | `captures/bt-xinput-white-20261024/` |

This is the firmware’s intentional Xbox identity on BT XInput. It is **out of scope** for `flydigi-vader4d` (no Xbox spoofing / no relying on `xpad`/`hid-microsoft` as the DInput solution).

## What we need next — blue LED (DInput)

On the pad (rear switch on Bluetooth):

1. Hold **FN ◯ + A** until the status LED turns **blue** (DInput).
2. Re-pair / reconnect if BlueZ drops the link after the mode change.
3. Tell the agent / re-run:

   ```bash
   python3 driver/flydigi_vader4d.py --list
   bluetoothctl devices Connected
   grep -A8 -iE 'Flydigi|Vader|045e|04b4' /proc/bus/input/devices
   ```

Expected (unverified): a non-Xbox HID name and possibly a different VID:PID or a classic HID gamepad collection we can bind like USB IF2.

## USB / dongle reminder

Dongle + wired DInput stays `04b4:2412` IF2 — already supported. BT XInput (white) will keep showing up as Xbox until you switch modes on the pad.
