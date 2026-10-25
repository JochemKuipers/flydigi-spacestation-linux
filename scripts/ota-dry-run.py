#!/usr/bin/env python3
"""Dry-run Vader 4 Pro HID OTA: start → ACK → finish (no image payload).

Always sends finish after start so the pad is not left in firmware-update mode.

python3 scripts/ota-dry-run.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.enumerate import PID, VID, list_vader4_interfaces
from flydigi.ota import OtaPreflightError, preflight_start_ack, usb_ota_ready


def _hex(data: bytes, n: int = 16) -> str:
    return " ".join(f"{b:02x}" for b in data[:n]) + (" …" if len(data) > n else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=float, default=2.5)
    ap.add_argument("--path", type=Path, default=None)
    args = ap.parse_args()

    for i in list_vader4_interfaces(VID, PID):
        if i.bus == "usb":
            print(f"  {i.hidraw} IF{i.interface_number} {i.phys}")

    path = args.path or usb_ota_ready()
    if path is None:
        print("ERROR: no USB IF3 (FFEF)", file=sys.stderr)
        return 1

    print(f"\nPreflight on {path} (start → finish)")
    try:
        ack = preflight_start_ack(path, timeout=args.timeout)
    except OtaPreflightError as exc:
        print(f"RESULT: fail — {exc}", file=sys.stderr)
        return 2

    print(f"IN start ACK: {_hex(ack, 16)}")
    print("RESULT: OK — channel alive, finish sent (not left in update mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
