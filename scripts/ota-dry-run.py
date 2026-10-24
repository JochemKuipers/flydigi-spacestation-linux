#!/usr/bin/env python3
"""Dry-run Vader 4 Pro HID OTA start frame — no image payload.

  python3 scripts/ota-dry-run.py
"""

from __future__ import annotations

import argparse
import os
import select
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.enumerate import PID, VID, list_vader4_interfaces  # noqa: E402
from flydigi.ota import OUT_LEN, REPORT_ID, usb_ota_ready  # noqa: E402


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

    print(f"\nOpening {path}")
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    pkt = bytearray(OUT_LEN)
    pkt[0] = REPORT_ID
    pkt[1:6] = bytes([2, 2, 0, 1, 0xFF])
    print(f"OUT start: {_hex(bytes(pkt), 12)}")
    os.write(fd, bytes(pkt))

    deadline = time.monotonic() + args.timeout
    got = 0
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], 0.2)
        if not r:
            continue
        try:
            data = os.read(fd, OUT_LEN)
        except BlockingIOError:
            continue
        if not data:
            continue
        got += 1
        tag = " ← report 5" if data[0] == 5 else ""
        print(f"IN [{len(data)}]: {_hex(data, 16)}{tag}")
    os.close(fd)
    if got:
        print(f"RESULT: {got} IN(s) — OTA channel alive")
        return 0
    print("RESULT: no IN")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
