#!/usr/bin/env python3
"""Send OTA finish on IF3 to leave firmware-update mode after a hung flash/dry-run.

  python3 scripts/ota-abort.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.ota import recover_firmware_update_mode, usb_ota_ready


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, default=None)
    args = ap.parse_args()

    path = args.path or usb_ota_ready()
    if path is None:
        print("ERROR: no USB IF3 (FFEF) — use wired DInput", file=sys.stderr)
        return 1

    print(f"recover finish on {path}")
    status = recover_firmware_update_mode(path)
    print(f"RESULT: {status}")
    if status in ("cleared", "replied"):
        return 0
    if status == "unavailable":
        return 1
    print(
        "no reply — unplug/replug or use Companion → Firmware → Exit update mode",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
