# Flydigi Vader 4 Pro — Linux DInput + Space Station port

Native Linux support for the Flydigi Vader 4 Pro **without** Xbox/XInput spoofing, `xpad`, or Steam Input.

## Status

| Component | Status |
|-----------|--------|
| Diagnosis (dongle DInput) | Done — [docs/diagnosis.md](docs/diagnosis.md) |
| Protocol (IF2 cmds + config) | Live-verified — [docs/protocol.md](docs/protocol.md) |
| `flydigi-vader4d` (uinput + socket) | Implemented |
| Space Station Linux GUI | Themed companion (`app/ui/`) — profiles / sticks / lighting / rumble / firmware |
| Firmware updater | Working — USB IF3 HID OTA ([docs/firmware.md](docs/firmware.md)); wired only |
| Bluetooth DInput (blue) | Input working — calibrated map ([docs/bluetooth.md](docs/bluetooth.md)) |
| Bluetooth XInput (white) | Xbox `045e:02e0` spoof — out of scope |

**Feature matrix:** full LED / rumble / onboard config = **dongle or USB**. BT DInput is input-only (same limit as official Space Station).

## Requirements

- Linux with `hidraw` + `uinput`
- Python 3.11+ with `python-evdev` (`pacman -S python-evdev`)
- GUI: `pacman -S pyside6`
- Controller in **PC/DInput** mode (blue LED)
- Dongle or wired USB `04b4:2412` (for config/LED/rumble), and/or BT `d7d7:0041`

## Packages

Separate packages (AUR / `.deb` / `.rpm`, plus AppImage for the UI):

| Package | Role |
|---------|------|
| `flydigi-vader4d` | Driver, `flydigi-ctl`, udev, user systemd unit |
| `vader-companion` | Qt companion app |

See [packaging/README.md](packaging/README.md) for build recipes.

## Quick start (from source)

```bash
# udev + user systemd unit (once)
./scripts/install-driver.sh

# Or foreground daemon
python3 driver/flydigi_vader4d.py   # or: flydigi-vader4d

# CLI against the daemon socket
python3 app/flydigi_ctl.py info
python3 app/flydigi_ctl.py rumble 255 255 --ms 1500
python3 app/flydigi_ctl.py led-set --r 0 --g 255 --b 0 --brightness 80

# Companion UI
python3 app/vader_companion.py      # or: vader-companion

# Firmware (wired DInput; IF3) — or use the Firmware tab
python3 scripts/ota-flash.py          # prompts YES
python3 scripts/ota-dry-run.py        # start frame only
```

The daemon creates a uinput device named **Flydigi Vader 4 Pro** and listens on `$XDG_RUNTIME_DIR/flydigi-vader4d.sock` (USB keeps `04b4:2412`; BT publishes `d7d7:0041`).

## Architecture

```
USB IF2 hidraw  ─┐
                 ├──► flydigi-vader4d ──► uinput (games)
BT VADER4P evdev─┘         │
                           └── Unix socket ──► vader_companion / flydigi_ctl
```

USB IF2 is exclusive to the daemon. On BT the daemon grabs `Flydigi VADER4P` so `KEY_ENTER` (Z) does not type into the desktop.

## Docs

- [docs/diagnosis.md](docs/diagnosis.md) — why stock Linux DInput looks broken
- [docs/protocol.md](docs/protocol.md) — V1 report + IF2 command/config map
- [docs/bluetooth.md](docs/bluetooth.md) — BT pairing / capture checklist
- [docs/firmware.md](docs/firmware.md) — F4 HID OTA (IF3) + archived image
- [docs/windows-vm.md](docs/windows-vm.md) — Windows VM oracle + host usbmon capture

## Space Station extract

Installer is Inno Setup **7**. Extracted via Wine into `vendor/spacestation-4.2.2.3/app/` (gitignored). Stack: Electron 36 + NativeAOT `SpaceStationService.exe`.
