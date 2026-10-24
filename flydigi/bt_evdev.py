"""Bridge BlueZ 'Flydigi VADER4P' (d7d7:0041) into our report shape.

Prefers the kernel hid-generic node (not our own uinput republish). Reads
hidraw when possible for C/Z/M/Guide; falls back to evdev for sticks/triggers.
"""

from __future__ import annotations

import os
import select
from dataclasses import dataclass
from pathlib import Path

from evdev import InputDevice, ecodes

from .bt_hid_report import BtHidReport, hat_from_xy, parse_bt_hid_report
from .enumerate import BT_PID, BT_VID


@dataclass
class BtEvdevState:
    lx: int = 0
    ly: int = 0
    rx: int = 0
    ry: int = 0
    lt: int = 0
    rt: int = 0
    hat_x: int = 0
    hat_y: int = 0
    buttons: dict[str, bool] | None = None

    def __post_init__(self) -> None:
        if self.buttons is None:
            self.buttons = {
                "a": False, "b": False, "x": False, "y": False,
                "lb": False, "rb": False, "select": False, "start": False,
                "guide": False, "ls": False, "rs": False,
                "c": False, "z": False, "m1": False, "m2": False,
                "m3": False, "m4": False, "fn": False,
            }


# Face / shoulder / menu from kernel gamepad bits. Do NOT map TL2/TR2 → C/Z
# (those fire with analog triggers on this firmware).
BTN_FROM_EV = {
    ecodes.BTN_SOUTH: "a",
    ecodes.BTN_EAST: "b",
    ecodes.BTN_NORTH: "x",
    ecodes.BTN_WEST: "y",
    ecodes.BTN_TL: "lb",
    ecodes.BTN_TR: "rb",
    ecodes.BTN_SELECT: "select",
    ecodes.BTN_START: "start",
    ecodes.BTN_THUMBL: "ls",
    ecodes.BTN_THUMBR: "rs",
}

# Consumer-page keys hid-generic emits for the extra Flydigi controls.
KEY_FROM_EV = {
    ecodes.KEY_EJECTCD: "m1",
    ecodes.KEY_CHANNELUP: "m2",
    ecodes.KEY_CHANNELDOWN: "m3",
    ecodes.KEY_TV: "m4",
    ecodes.KEY_CAMERA: "c",
    ecodes.KEY_RED: "z",
    ecodes.KEY_ENTER: "guide",
    ecodes.BTN_0: "fn",
    ecodes.KEY_PROGRAM: "fn",
    ecodes.KEY_WWW: "guide",
}


def _scale_stick(v: int, vmin: int, vmax: int) -> int:
    if vmax == vmin:
        return 0
    mid = (vmin + vmax) / 2.0
    half = (vmax - vmin) / 2.0
    if abs(v - mid) < 1:
        return 0
    return int(max(-32767, min(32767, (v - mid) * 32767 / half)))


def _is_uinput(dev: InputDevice) -> bool:
    phys = (dev.phys or "").lower()
    return "py-evdev-uinput" in phys or phys == "py-evdev-uinput"


def find_bt_evdev() -> InputDevice | None:
    """Return the kernel Flydigi VADER4P node — never our uinput clone."""
    from evdev import list_devices

    named: InputDevice | None = None
    by_id: InputDevice | None = None
    for path in list_devices():
        d = InputDevice(path)
        if _is_uinput(d):
            continue
        if d.name == "Flydigi VADER4P":
            named = d
            break
        if d.info.vendor == BT_VID and d.info.product == BT_PID:
            by_id = d
    return named or by_id


def find_bt_hidraw() -> Path | None:
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return None
    for entry in sorted(root.iterdir()):
        try:
            uevent = (entry / "device" / "uevent").read_text()
        except OSError:
            continue
        up = uevent.upper()
        if "D7D7" in up and "0041" in up:
            node = Path("/dev") / entry.name
            if node.exists():
                return node
        if "FLYDIGI" in up and "VADER4P" in up:
            node = Path("/dev") / entry.name
            if node.exists():
                return node
    return None


class BtEvdevReader:
    def __init__(self, device: InputDevice | None = None) -> None:
        self.dev = device or find_bt_evdev()
        if self.dev is None:
            raise FileNotFoundError("Flydigi VADER4P BT input device not found")
        if _is_uinput(self.dev):
            raise RuntimeError(f"refusing uinput loop device {self.dev.path}")
        self.state = BtEvdevState()
        self._hid_fd: int | None = None
        self._hid_path = find_bt_hidraw()
        if self._hid_path is not None:
            try:
                self._hid_fd = os.open(self._hid_path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                self._hid_fd = None
        self._pull_abs()

    def fileno(self) -> int:
        # Prefer hidraw for select when open — richer button bits.
        if self._hid_fd is not None:
            return self._hid_fd
        return self.dev.fd

    def close(self) -> None:
        if self._hid_fd is not None:
            try:
                os.close(self._hid_fd)
            except OSError:
                pass
            self._hid_fd = None

    def _pull_abs(self) -> None:
        d = self.dev
        st = self.state
        try:
            for code, attr, scale in (
                (ecodes.ABS_X, "lx", True),
                (ecodes.ABS_Y, "ly", True),
                (ecodes.ABS_Z, "rx", True),
                (ecodes.ABS_RZ, "ry", True),
                (ecodes.ABS_GAS, "lt", False),
                (ecodes.ABS_BRAKE, "rt", False),
                (ecodes.ABS_HAT0X, "hat_x", False),
                (ecodes.ABS_HAT0Y, "hat_y", False),
            ):
                info = d.absinfo(code)
                if scale:
                    setattr(st, attr, _scale_stick(info.value, info.min, info.max))
                else:
                    setattr(st, attr, int(info.value))
        except OSError:
            pass

    def pump(self) -> BtHidReport | None:
        """Read hidraw and/or evdev; return a snapshot if anything changed."""
        changed = False
        st = self.state
        assert st.buttons is not None

        # 1) hidraw path — authoritative for extras
        if self._hid_fd is not None:
            try:
                r, _, _ = select.select([self._hid_fd], [], [], 0)
            except (ValueError, OSError):
                r = []
            if r:
                try:
                    data = os.read(self._hid_fd, 64)
                except BlockingIOError:
                    data = b""
                except OSError:
                    data = b""
                    self.close()
                if data:
                    rep = parse_bt_hid_report(data)
                    if rep is not None:
                        # Keep LT/RT from evdev abs if hid tail is unreliable.
                        self._drain_evdev()
                        buttons = dict(rep.buttons)
                        return BtHidReport(
                            raw=rep.raw,
                            lx=rep.lx,
                            ly=rep.ly,
                            rx=rep.rx,
                            ry=rep.ry,
                            lt=st.lt,
                            rt=st.rt,
                            hat_x=rep.hat_x,
                            hat_y=rep.hat_y,
                            hat=rep.hat or hat_from_xy(rep.hat_x, rep.hat_y),
                            buttons=buttons,
                        )

        # 2) evdev-only fallback
        try:
            r, _, _ = select.select([self.dev.fd], [], [], 0)
        except (ValueError, OSError):
            return None
        if not r:
            return None
        if self._drain_evdev():
            changed = True
        if not changed:
            return None
        return BtHidReport(
            raw=b"",
            lx=st.lx,
            ly=st.ly,
            rx=st.rx,
            ry=st.ry,
            lt=st.lt,
            rt=st.rt,
            hat_x=st.hat_x,
            hat_y=st.hat_y,
            hat=hat_from_xy(st.hat_x, st.hat_y),
            buttons=dict(st.buttons),
        )

    def _drain_evdev(self) -> bool:
        changed = False
        st = self.state
        assert st.buttons is not None
        try:
            events = self.dev.read()
        except BlockingIOError:
            return False
        except OSError:
            return False
        for e in events:
            if e.type == ecodes.EV_KEY:
                name = BTN_FROM_EV.get(e.code) or KEY_FROM_EV.get(e.code)
                if name is not None:
                    st.buttons[name] = e.value != 0
                    changed = True
            elif e.type == ecodes.EV_ABS:
                if e.code == ecodes.ABS_X:
                    info = self.dev.absinfo(ecodes.ABS_X)
                    st.lx = _scale_stick(e.value, info.min, info.max)
                    changed = True
                elif e.code == ecodes.ABS_Y:
                    info = self.dev.absinfo(ecodes.ABS_Y)
                    st.ly = _scale_stick(e.value, info.min, info.max)
                    changed = True
                elif e.code == ecodes.ABS_Z:
                    info = self.dev.absinfo(ecodes.ABS_Z)
                    st.rx = _scale_stick(e.value, info.min, info.max)
                    changed = True
                elif e.code == ecodes.ABS_RZ:
                    info = self.dev.absinfo(ecodes.ABS_RZ)
                    st.ry = _scale_stick(e.value, info.min, info.max)
                    changed = True
                elif e.code == ecodes.ABS_GAS:
                    st.lt = int(e.value)
                    changed = True
                elif e.code == ecodes.ABS_BRAKE:
                    st.rt = int(e.value)
                    changed = True
                elif e.code == ecodes.ABS_HAT0X:
                    st.hat_x = int(e.value)
                    changed = True
                elif e.code == ecodes.ABS_HAT0Y:
                    st.hat_y = int(e.value)
                    changed = True
        return changed
