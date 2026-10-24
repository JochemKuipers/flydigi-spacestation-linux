# Bluetooth DInput path

## Status

**Not verified** on this Vader 4 Pro yet — no Flydigi BT pairing present on the
dev machine (only an unrelated Xbox Wireless Controller showed up in BlueZ).

Community notes and flydigictl both treat Bluetooth as a separate, often
incomplete path versus the `04b4:2412` dongle/wired composite.

## When you pair

1. Put the pad in PC/DInput mode, then hold the vendor BT pair combo (see
   Flydigi manual — typically a FN + face-button hold until LEDs blink).
2. `bluetoothctl scan on` / pair / trust / connect.
3. Check hidraw:

   ```bash
   python3 driver/flydigi_vader4d.py --list
   ```

   Name-based matching should list any `Flydigi*VADER*` hidraw even if the
   Bluetooth VID:PID differs from `04b4:2412`.
4. Capture `HID_ID`, `HID_NAME`, `HID_PHYS`, and a few IF packets into
   `captures/bt-*.txt`, then we lock `EXTRA_IDS` in `flydigi/enumerate.py` and
   confirm the V1 `04 FE` stream + report `05` commands behave like USB IF2.

## Expected software path

Same as USB once a suitable hidraw appears:

`hidraw → flydigi-vader4d → uinput + control socket`

If BT exposes only a partial HID collection (no IF2-equivalent), the daemon
will need a BT-specific report parser — that is why we need a live capture
before claiming parity.
