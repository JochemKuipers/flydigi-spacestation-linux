#!/usr/bin/env python3
"""Interactively map Flydigi VADER4P Bluetooth DInput controls.

For each control:
  1. Press/hold it on the pad (live HID/KEY hits print here)
  2. Keyboard (single key, no Enter):
       n or Space  — lock & next
       s           — skip
       q           — quit & save

The pad is EVIOCGRAB'd so Z (kernel KEY_ENTER) cannot type into this terminal.
"""

from __future__ import annotations

import json
import os
import select
import sys
import termios
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Self

from evdev import InputDevice, ecodes, list_devices

CONTROLS = [
    "a",
    "b",
    "x",
    "y",
    "lb",
    "rb",
    "select",
    "start",
    "ls",
    "rs",
    "lt",
    "rt",
    "hat_up",
    "hat_right",
    "hat_down",
    "hat_left",
    "c",
    "z",
    "m1",
    "m2",
    "m3",
    "m4",
    "guide",
    "fn",
]

OUT_DEFAULT = ROOT / "captures" / "bt-button-map.json"


def find_vader4p() -> InputDevice:
    for path in list_devices():
        d = InputDevice(path)
        if d.name == "Flydigi VADER4P" and "uinput" not in (d.phys or ""):
            return d
    raise SystemExit("Flydigi VADER4P not found — BT DInput (blue LED) + connected")


def find_hidraw() -> Path:
    for e in sorted(Path("/sys/class/hidraw").iterdir()):
        u = (e / "device" / "uevent").read_text()
        if "D7D7" in u.upper() and "0041" in u.upper():
            return Path("/dev") / e.name
    raise SystemExit("d7d7:0041 hidraw not found")


def key_name(code: int) -> str:
    n = ecodes.KEY.get(code) or ecodes.BTN.get(code) or str(code)
    return n[0] if isinstance(n, tuple) else str(n)


def open_hidraw(path: Path) -> int:
    try:
        return os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        import subprocess

        subprocess.check_call(["sudo", "chmod", "a+rw", str(path)])
        return os.open(path, os.O_RDONLY | os.O_NONBLOCK)


class RawStdin:
    """cbreak stdin: read one byte at a time without needing Enter."""

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self.fd)

    def __enter__(self) -> Self:
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc: object) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self._old)

    def read_key(self) -> str | None:
        if not select.select([self.fd], [], [], 0)[0]:
            return None
        ch = os.read(self.fd, 1)
        if not ch:
            return None
        return ch.decode("utf-8", errors="ignore")


def capture_one(
    dev: InputDevice, hid_fd: int, label: str, stdin: RawStdin
) -> tuple[str, dict]:
    best = {
        "ev_keys": {},
        "hid_btn_bits": 0,
        "hid_cons_bits": 0,
        "hid_hat": 0,
        "abs": {},
        "raw9_12": "",
        "samples": 0,
    }
    print(f"=== {label.upper()} ===")
    print(f"  Hold [{label}] on the pad, then: n/Space=next  s=skip  q=quit")
    sys.stdout.write("  live: (waiting)\r")
    sys.stdout.flush()

    while True:
        r, _, _ = select.select([dev.fd, hid_fd, stdin.fd], [], [], 0.25)

        if stdin.fd in r:
            ch = stdin.read_key()
            # drain any extra buffered bytes from the same press
            while True:
                extra = stdin.read_key()
                if extra is None:
                    break
                ch = extra if ch is None else ch
            if ch is None:
                continue
            print()
            if ch in ("q", "Q"):
                return "quit", best
            if ch in ("s", "S"):
                return "skip", best
            if ch in ("n", "N", " ", "\r", "\n"):
                return "ok", best
            # ignore other keys
            sys.stdout.write("  live: (n=next s=skip q=quit)\r")
            sys.stdout.flush()
            continue

        if hid_fd in r:
            try:
                data = os.read(hid_fd, 64)
            except BlockingIOError:
                data = b""
            if len(data) >= 12 and data[0] == 1:
                packed = data[9] | (data[10] << 8)
                hat = packed & 0x0F
                btns = (packed >> 4) & 0xFFF
                cons = int.from_bytes(data[11:14], "little")
                if btns or cons or hat not in (0, 8):
                    best["hid_btn_bits"] |= btns
                    best["hid_cons_bits"] |= cons
                    best["hid_hat"] = hat
                    best["raw9_12"] = data[9:13].hex()
                    best["samples"] += 1
                    sys.stdout.write(
                        f"  live: btns={btns:012b} cons={cons:016b} hat={hat}   \r"
                    )
                    sys.stdout.flush()

        if dev.fd in r:
            for e in dev.read():
                if e.type == ecodes.EV_KEY and e.value:
                    name = key_name(e.code)
                    best["ev_keys"][name] = best["ev_keys"].get(name, 0) + 1
                    sys.stdout.write(f"  live: KEY {name}                        \r")
                    sys.stdout.flush()
                elif e.type == ecodes.EV_ABS and e.code in (
                    ecodes.ABS_GAS,
                    ecodes.ABS_BRAKE,
                    ecodes.ABS_HAT0X,
                    ecodes.ABS_HAT0Y,
                ):
                    an = ecodes.ABS[e.code]
                    best["abs"][an] = e.value
                    sys.stdout.write(f"  live: ABS {an}={e.value}                \r")
                    sys.stdout.flush()


def derive(mapping: dict) -> dict:
    btn_bit: dict[str, int] = {}
    cons_bit: dict[str, int] = {}
    key_map: dict[str, str] = {}
    for name, s in mapping.items():
        bb = int(s.get("hid_btn_bits") or 0)
        cb = int(s.get("hid_cons_bits") or 0)
        if bb and (bb).bit_count() == 1:
            btn_bit[name] = bb.bit_length() - 1
        if cb and (cb).bit_count() == 1:
            cons_bit[name] = cb.bit_length() - 1
        if s.get("ev_keys"):
            top = max(s["ev_keys"].items(), key=lambda kv: kv[1])[0]
            key_map[top] = name
    return {"btn_bit": btn_bit, "cons_bit": cons_bit, "key_map": key_map}


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    only = sys.argv[2:]
    controls = [c for c in CONTROLS if not only or c in only]

    if not sys.stdin.isatty():
        raise SystemExit("Need a real terminal (tty) for single-key controls")

    dev = find_vader4p()
    hr = find_hidraw()
    print(f"device  {dev.path} ({dev.name})")
    print(f"hidraw  {hr}")
    print(f"output  {out}")
    print("grabbing pad so KEY_ENTER (Z) cannot type into this terminal…")
    print()

    hid_fd = open_hidraw(hr)
    mapping: dict[str, dict] = {}
    try:
        dev.grab()
    except OSError as exc:
        print(f"warning: could not grab device ({exc}); Z may still inject Enter")

    try:
        with RawStdin() as stdin:
            for name in controls:
                action, sample = capture_one(dev, hid_fd, name, stdin)
                if action == "quit":
                    break
                if action == "skip":
                    print(f"  skipped {name}\n")
                    continue
                mapping[name] = sample
                print(
                    f"  locked {name}: keys={list(sample['ev_keys'])} "
                    f"btn={sample['hid_btn_bits']:012b} "
                    f"cons={sample['hid_cons_bits']:016b}\n"
                )
    finally:
        try:
            dev.ungrab()
        except OSError:
            pass
        os.close(hid_fd)

    derived = derive(mapping)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "device": "Flydigi VADER4P",
        "vid_pid": "d7d7:0041",
        "controls": mapping,
        "derived": derived,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out}")
    print("derived:", json.dumps(derived, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
