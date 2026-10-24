#!/usr/bin/env python3
"""Userspace DInput driver for Flydigi Vader 4 Pro.

Reads hidraw interface 2 (report 0x04 / magic 0xFE) and republishes a single
uinput gamepad with Flydigi VID/PID — no Xbox spoofing, no Steam Input, no xpad.
"""

from __future__ import annotations

import argparse
import os
import select
import signal
import sys
import time
from pathlib import Path

# Allow running from a git checkout without installing the package.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evdev import AbsInfo, UInput, ecodes

from flydigi.enumerate import VID, PID, find_input_interface, list_vader4_interfaces
from flydigi.v1_report import parse_v1_report

BTN_MAP = {
    "a": ecodes.BTN_SOUTH,
    "b": ecodes.BTN_EAST,
    "x": ecodes.BTN_NORTH,
    "y": ecodes.BTN_WEST,
    "lb": ecodes.BTN_TL,
    "rb": ecodes.BTN_TR,
    "select": ecodes.BTN_SELECT,
    "start": ecodes.BTN_START,
    "guide": ecodes.BTN_MODE,
    "ls": ecodes.BTN_THUMBL,
    "rs": ecodes.BTN_THUMBR,
    "c": ecodes.BTN_C,
    "z": ecodes.BTN_Z,
    "m1": ecodes.BTN_TRIGGER_HAPPY1,
    "m2": ecodes.BTN_TRIGGER_HAPPY2,
    "m3": ecodes.BTN_TRIGGER_HAPPY3,
    "m4": ecodes.BTN_TRIGGER_HAPPY4,
}

CAP = {
    ecodes.EV_KEY: list(BTN_MAP.values()),
    ecodes.EV_ABS: [
        (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Y, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_RX, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_RY, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        # Motion (raw int16); consumers that understand ABS misc can use these.
        (ecodes.ABS_MISC, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
    ],
}


def open_hidraw(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_NONBLOCK)


def wait_for_device(timeout: float | None = None) -> object:
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        iface = find_input_interface()
        if iface is not None:
            return iface
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Vader 4 Pro IF2 hidraw not found")
        time.sleep(0.5)


def run(once_list: bool = False) -> int:
    if once_list:
        for i in list_vader4_interfaces():
            print(f"{i.hidraw} iface={i.interface_number} phys={i.phys} name={i.name}")
        return 0

    stop = False

    def _stop(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("flydigi-vader4d: waiting for 04b4:2412 interface 2…", flush=True)
    iface = wait_for_device()
    print(f"flydigi-vader4d: using {iface.hidraw} (iface {iface.interface_number})", flush=True)

    fd = open_hidraw(iface.hidraw)
    ui = UInput(
        CAP,
        name="Flydigi Vader 4 Pro",
        vendor=VID,
        product=PID,
        version=0x0111,
        bustype=ecodes.BUS_USB,
    )
    last: dict[str, object] = {}

    try:
        while not stop:
            r, _, _ = select.select([fd], [], [], 1.0)
            if not r:
                # Device hot-unplug: re-open when gone
                if not iface.hidraw.exists():
                    print("flydigi-vader4d: device gone, waiting…", flush=True)
                    os.close(fd)
                    iface = wait_for_device()
                    fd = open_hidraw(iface.hidraw)
                    print(f"flydigi-vader4d: reopened {iface.hidraw}", flush=True)
                continue
            try:
                data = os.read(fd, 64)
            except BlockingIOError:
                continue
            except OSError as exc:
                print(f"flydigi-vader4d: read error {exc}, reconnecting…", flush=True)
                try:
                    os.close(fd)
                except OSError:
                    pass
                iface = wait_for_device()
                fd = open_hidraw(iface.hidraw)
                continue

            report = parse_v1_report(data)
            if report is None:
                continue

            for name, code in BTN_MAP.items():
                val = 1 if report.buttons[name] else 0
                key = f"b:{name}"
                if last.get(key) != val:
                    ui.write(ecodes.EV_KEY, code, val)
                    last[key] = val

            for abs_code, value, key in (
                (ecodes.ABS_X, report.lx, "lx"),
                (ecodes.ABS_Y, report.ly, "ly"),
                (ecodes.ABS_RX, report.rx, "rx"),
                (ecodes.ABS_RY, report.ry, "ry"),
                (ecodes.ABS_Z, report.lt, "lt"),
                (ecodes.ABS_RZ, report.rt, "rt"),
                (ecodes.ABS_HAT0X, report.hat_x, "hx"),
                (ecodes.ABS_HAT0Y, report.hat_y, "hy"),
            ):
                if last.get(key) != value:
                    ui.write(ecodes.EV_ABS, abs_code, value)
                    last[key] = value

            ui.syn()
    finally:
        ui.close()
        try:
            os.close(fd)
        except OSError:
            pass
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true", help="List matching hidraw nodes and exit")
    args = p.parse_args()
    raise SystemExit(run(once_list=args.list))


if __name__ == "__main__":
    main()
