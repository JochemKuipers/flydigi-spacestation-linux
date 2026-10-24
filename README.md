# Flydigi Vader 4 Pro — Linux DInput + Space Station port

Native Linux support for the Flydigi Vader 4 Pro **without** Xbox/XInput spoofing, `xpad`, or Steam Input.

**Private repo:** [jochem-kuipers/flydigi-spacestation-linux](https://origin.cursor.com/jochem-kuipers/flydigi-spacestation-linux) on Cursor Origin.

## Status

| Component | Status |
|-----------|--------|
| Diagnosis (dongle DInput) | Documented — see [docs/diagnosis.md](docs/diagnosis.md) |
| Protocol notes | Partial — see [docs/protocol.md](docs/protocol.md) |
| `flydigi-vader4d` (hidraw IF2 → uinput) | Implemented (test/install below) |
| Space Station Linux GUI | Early shell — device + live V1 monitor |
| Firmware updater | Locked until DFU RE completes |
| Bluetooth | Not verified yet |

## Requirements

- Linux with `hidraw` + `uinput`
- Python 3.11+ with `python-evdev` (`pacman -S python-evdev`)
- Controller in **PC/DInput** mode (community: blue LED, FN/O+A)
- Dongle or wired USB `04b4:2412`

## Quick start (driver)

```bash
# List IF0–IF3 hidraw nodes
python3 driver/flydigi_vader4d.py --list

# Foreground daemon (creates uinput "Flydigi Vader 4 Pro")
python3 driver/flydigi_vader4d.py

# Persist across reboot
./scripts/install-driver.sh
```

Verify with `evtest` — you should see face buttons, C/Z, M1–M4, sticks, triggers, dpad. VID/PID remain `04b4:2412`.

## Companion UI (early)

```bash
# deps: pacman -S pyside6 python-evdev
python3 app/spacestation_linux.py
# or CLI monitor:
python3 app/monitor_v1.py
```

## Space Station extract

Installer is Inno Setup **7** (stock `innoextract` 1.9 cannot unpack it). Extracted via Wine into `vendor/spacestation-4.2.2.3/app/` (gitignored). Stack: Electron 36 UI + NativeAOT-like `SpaceStationService.exe` + `hidapi.dll` + firmware tools.

## Docs

- [docs/diagnosis.md](docs/diagnosis.md) — why stock Linux DInput looks broken
- [docs/protocol.md](docs/protocol.md) — report map and config notes
