#!/usr/bin/env python3
"""Minimal live V1 report monitor (CLI stand-in until the Qt GUI lands)."""

from __future__ import annotations

import os
import select
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flydigi.enumerate import find_input_interface
from flydigi.v1_report import parse_v1_report


def main() -> int:
    iface = find_input_interface()
    if iface is None:
        print(
            "No Vader 4 Pro IF2 hidraw found (need DInput 04b4:2412)", file=sys.stderr
        )
        return 1
    print(f"Reading {iface.hidraw} (USB iface {iface.interface_number})")
    fd = os.open(iface.hidraw, os.O_RDONLY | os.O_NONBLOCK)
    try:
        while True:
            r, _, _ = select.select([fd], [], [], 1.0)
            if not r:
                continue
            data = os.read(fd, 64)
            rep = parse_v1_report(data)
            if not rep:
                continue
            pressed = [k for k, v in rep.buttons.items() if v]
            print(
                f"\rsticks=({rep.lx:6d},{rep.ly:6d}) ({rep.rx:6d},{rep.ry:6d}) "
                f"T={rep.lt:3d}/{rep.rt:3d} hat=({rep.hat_x},{rep.hat_y}) "
                f"btn={','.join(pressed) or '-':20s}",
                end="",
                flush=True,
            )
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
