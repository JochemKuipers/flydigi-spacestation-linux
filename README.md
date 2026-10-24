# Flydigi Vader 4 Pro — Linux DInput + Space Station port

Native Linux support for the Flydigi Vader 4 Pro **without** Xbox/XInput spoofing, `xpad`, or Steam Input.

**Private repo:** [jochem-kuipers/flydigi-spacestation-linux](https://origin.cursor.com/jochem-kuipers/flydigi-spacestation-linux) on Cursor Origin.

## Status

| Component | Status |
|-----------|--------|
| Diagnosis (dongle DInput) | Done — [docs/diagnosis.md](docs/diagnosis.md) |
| Protocol (IF2 cmds + config) | Live-verified — [docs/protocol.md](docs/protocol.md) |
| `flydigi-vader4d` (uinput + socket) | Implemented |
| Space Station Linux GUI | Profiles / sticks / lighting / rumble (firmware gated) |
| Firmware updater | Locked until DFU RE completes |
| Bluetooth DInput (blue) | Input working — calibrated map ([docs/bluetooth.md](docs/bluetooth.md)) |
| Bluetooth XInput (white) | Xbox `045e:02e0` spoof — out of scope |

**Feature matrix:** full LED / rumble / onboard config = **dongle or USB**. BT DInput is input-only (same limit as official Space Station).

## Requirements

- Linux with `hidraw` + `uinput`
- Python 3.11+ with `python-evdev` (`pacman -S python-evdev`)
- GUI: `pacman -S pyside6`
- Controller in **PC/DInput** mode (blue LED)
- Dongle or wired USB `04b4:2412` (for config/LED/rumble), and/or BT `d7d7:0041`

## Quick start

```bash
# udev + user systemd unit (once)
./scripts/install-driver.sh

# Or foreground daemon
python3 driver/flydigi_vader4d.py

# CLI against the daemon socket
python3 app/flydigi_ctl.py info
python3 app/flydigi_ctl.py rumble 255 255 --ms 1500
python3 app/flydigi_ctl.py led-set --r 0 --g 255 --b 0 --brightness 80

# Companion UI
python3 app/spacestation_linux.py
```

The daemon creates a uinput device named **Flydigi Vader 4 Pro** and listens on `$XDG_RUNTIME_DIR/flydigi-vader4d.sock` (USB keeps `04b4:2412`; BT publishes `d7d7:0041`).

## Architecture

```
USB IF2 hidraw  ─┐
                 ├──► flydigi-vader4d ──► uinput (games)
BT VADER4P evdev─┘         │
                           └── Unix socket ──► spacestation_linux / flydigi_ctl
```

USB IF2 is exclusive to the daemon. On BT the daemon grabs `Flydigi VADER4P` so `KEY_ENTER` (Z) does not type into the desktop.

## Docs

- [docs/diagnosis.md](docs/diagnosis.md) — why stock Linux DInput looks broken
- [docs/protocol.md](docs/protocol.md) — V1 report + IF2 command/config map
- [docs/bluetooth.md](docs/bluetooth.md) — BT pairing / capture checklist

## Space Station extract

Installer is Inno Setup **7**. Extracted via Wine into `vendor/spacestation-4.2.2.3/app/` (gitignored). Stack: Electron 36 + NativeAOT `SpaceStationService.exe`.
