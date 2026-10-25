#!/usr/bin/env python3
"""Full HID OTA flash for Vader 4 Pro (f4).

Always runs a start-frame dry-run first (no image bytes). Aborts if that ACK
fails — that is the safety gate for older/unknown pad firmware.

  python3 scripts/ota-flash.py
  python3 scripts/ota-flash.py --yes
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.dinput_proto import DInputDevice
from flydigi.enumerate import PID, VID, find_config_interface, list_vader4_interfaces
from flydigi.ota import (
    DEFAULT_BIN,
    PROVEN_PAD_VERSIONS,
    flash_bin,
    load_image,
    usb_ota_ready,
)


def _read_pad_version() -> str | None:
    try:
        dev = DInputDevice()
        info = dev.wait_device_info(timeout=2.0)
        dev.close()
        return info.firmware_version if info else None
    except (OSError, TimeoutError, RuntimeError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin", type=Path, default=DEFAULT_BIN)
    ap.add_argument("--path", type=Path, default=None, help="hidraw override")
    ap.add_argument("--yes", action="store_true", help="skip confirmation")
    ap.add_argument(
        "--no-preflight",
        action="store_true",
        help="skip start-frame dry-run (unsafe; not recommended)",
    )
    ap.add_argument(
        "--allow-untested",
        action="store_true",
        help=argparse.SUPPRESS,  # obsolete no-op kept for old scripts
    )
    args = ap.parse_args()

    usb = [i for i in list_vader4_interfaces(VID, PID) if i.bus == "usb"]
    print("USB interfaces:")
    for i in usb:
        print(f"  {i.hidraw} IF{i.interface_number} {i.phys}")
    if not usb or (usb_ota_ready() is None and args.path is None):
        print("ERROR: no USB IF3 — plug in wired DInput", file=sys.stderr)
        return 1

    pad_ver = _read_pad_version()
    print(f"pad firmware: {pad_ver or 'unknown'}")
    if pad_ver and pad_ver not in PROVEN_PAD_VERSIONS:
        print(
            f"note: full write proven on {', '.join(sorted(PROVEN_PAD_VERSIONS))}; "
            f"dry-run ACK still required before data"
        )

    _image, size, crc = load_image(args.bin)
    print(f"image {args.bin.name}: size={size} crc={crc:#x} (+16 FF pad)")
    print(
        "plan: dry-run start ACK → full write"
        if not args.no_preflight
        else "plan: FULL WRITE (no preflight)"
    )
    if not args.yes:
        print("Do not unplug.")
        try:
            ans = input("Type YES to continue: ").strip()
        except EOFError:
            ans = ""
        if ans != "YES":
            print("aborted")
            return 1

    last = [-1]

    def on_progress(pct: int, index: int) -> None:
        if pct != last[0] and (pct % 5 == 0 or pct >= 99):
            print(f"\rprogress {pct:3d}%  index={index}", end="", flush=True)
            last[0] = pct

    def on_status(msg: str) -> None:
        print(f"\n{msg}")

    try:
        t0 = time.monotonic()
        flash_bin(
            args.bin,
            hidraw=args.path,
            on_progress=on_progress,
            on_status=on_status,
            preflight=not args.no_preflight,
            pad_version=pad_ver,
        )
        print(f"\nOTA success — done in {time.monotonic() - t0:.1f}s")
    except (OSError, TimeoutError, RuntimeError, ValueError) as e:
        print(f"\nFLASH ERROR: {e}", file=sys.stderr)
        return 2

    print("waiting for device…")
    time.sleep(2.0)
    for _ in range(30):
        if find_config_interface(VID, PID):
            break
        time.sleep(0.5)
    else:
        print("device not back yet — check cable / mode")
        return 3

    try:
        dev = DInputDevice()
        info = dev.wait_device_info(timeout=3.0)
        dev.close()
        if info:
            print(
                f"post-flash firmware={info.firmware_version} device_id={info.device_id}"
            )
        else:
            print("post-flash: no DeviceInfo yet")
    except (OSError, TimeoutError, RuntimeError) as e:
        print(f"post-flash info: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
