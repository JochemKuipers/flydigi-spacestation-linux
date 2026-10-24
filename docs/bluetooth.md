# Bluetooth path

## DInput — blue LED (live, 2026-10-24)

| Field | Value |
|-------|-------|
| Status LED | **Blue** |
| Mode | **DInput** |
| BlueZ name | `Flydigi VADER4P` |
| Address | `A4:C1:38:10:33:34` |
| HID ID | `0005:D7D7:0041` |
| Modalias | `bluetooth:vD7D7p0041d0101` |
| Kernel driver | `hid-generic` |
| Report map | Standard HID **Game Pad** report ID `0x01` (not USB `04 FE` V1) |
| Extra GATT | Nordic UART (`6e400001-…`), vendor `00010203-…` (config TBD) |
| Captures | `captures/bt-dinput-blue-20261024/` |

`flydigi-vader4d` treats this as transport `bt`: bridges the kernel `Flydigi VADER4P` evdev node into a clean uinput **Flydigi Vader 4 Pro** (`d7d7:0041`). USB IF2 commands (LED/config/cmd 236) are **not** on this HID collection — those stay dongle/wired until NUS/vendor GATT is reverse-engineered.

M1–M4 / full IMU are likely USB-IF2-only; BT HID exposes face buttons, sticks, triggers, hat, and (via TL2/TR2) C/Z stand-ins.

### Connect tips

1. Rear switch → Bluetooth, hold **FN ◯ + A** until LED is **blue**.
2. Press **HOME** to wake/advertise; `bluetoothctl connect A4:C1:38:10:33:34`.
3. `python3 driver/flydigi_vader4d.py --list` should show `bus=bluetooth` / `d7d7:0041`.
4. Install udev: `./scripts/install-driver.sh` (includes `d7d7:0041` hidraw access).

If BlueZ shows Connected but **no input events**:

- Press **HOME** to wake; wiggle sticks / face buttons.
- Tap **FN ◯** once — BT DInput advertises Appearance `0x03c2` (mouse); FN may toggle gyro-mouse vs gamepad stream (same idea as USB).
- Do **not** poke Nordic UART randomly — speculative GATT writes have dropped the link in testing.
- Prefer **dongle/wired** for full IF2 features (M-buttons, IMU, LED/config/rumble). BT DInput is a lighter HID gamepad.

## XInput — white LED (captured)

| Field | Value |
|-------|-------|
| Status LED | **White** |
| Mode | **XInput** |
| Identity | `Xbox Wireless Controller` `045e:02e0`, driver `microsoft` |
| Captures | `captures/bt-xinput-white-20261024/` |

Out of scope for this stack (Xbox spoof). Switch with **FN ◯ + A** for DInput.
