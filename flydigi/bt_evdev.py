"""Bridge BlueZ/hid-generic 'Flydigi VADER4P' (d7d7:0041) into our report shape.

BT DInput uses a standard HID gamepad; the kernel already creates an input
node. We re-publish a clean Flydigi-named uinput device with consistent
axes (matching the USB daemon) so games see one coherent pad.
"""

from __future__ import annotations

from dataclasses import dataclass

from evdev import InputDevice, ecodes

from .bt_hid_report import BtHidReport


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
                "m3": False, "m4": False,
            }


BTN_FROM_EV = {
    ecodes.BTN_SOUTH: "a",
    ecodes.BTN_EAST: "b",
    ecodes.BTN_NORTH: "x",
    ecodes.BTN_WEST: "y",
    ecodes.BTN_TL: "lb",
    ecodes.BTN_TR: "rb",
    ecodes.BTN_SELECT: "select",
    ecodes.BTN_START: "start",
    ecodes.BTN_MODE: "guide",
    ecodes.BTN_THUMBL: "ls",
    ecodes.BTN_THUMBR: "rs",
    # On this BT descriptor, TL2/TR2 are often C/Z stand-ins when M-buttons
    # are absent from the HID map.
    ecodes.BTN_TL2: "c",
    ecodes.BTN_TR2: "z",
}


def _scale_stick(v: int, vmin: int, vmax: int) -> int:
    if vmax == vmin:
        return 0
    # map [vmin,vmax] → [-32767,32767]
    mid = (vmin + vmax) / 2.0
    half = (vmax - vmin) / 2.0
    if abs(v - mid) < 1:
        return 0
    return int(max(-32767, min(32767, (v - mid) * 32767 / half)))


def find_bt_evdev() -> InputDevice | None:
    from evdev import list_devices

    for path in list_devices():
        d = InputDevice(path)
        if d.info.vendor == 0xD7D7 and d.info.product == 0x0041:
            return d
        if "VADER4P" in d.name.upper():
            return d
    return None


class BtEvdevReader:
    def __init__(self, device: InputDevice | None = None) -> None:
        self.dev = device or find_bt_evdev()
        if self.dev is None:
            raise FileNotFoundError("Flydigi VADER4P BT input device not found")
        self.state = BtEvdevState()
        # seed abs
        self._pull_abs()

    def fileno(self) -> int:
        return self.dev.fd

    def _pull_abs(self) -> None:
        d = self.dev
        st = self.state
        try:
            ax = d.absinfo(ecodes.ABS_X)
            ay = d.absinfo(ecodes.ABS_Y)
            az = d.absinfo(ecodes.ABS_Z)
            arz = d.absinfo(ecodes.ABS_RZ)
            st.lx = _scale_stick(ax.value, ax.min, ax.max)
            st.ly = _scale_stick(ay.value, ay.min, ay.max)
            st.rx = _scale_stick(az.value, az.min, az.max)
            st.ry = _scale_stick(arz.value, arz.min, arz.max)
        except OSError:
            pass
        for code, attr in ((ecodes.ABS_GAS, "lt"), (ecodes.ABS_BRAKE, "rt"),
                           (ecodes.ABS_HAT0X, "hat_x"), (ecodes.ABS_HAT0Y, "hat_y")):
            try:
                info = d.absinfo(code)
                if attr in ("lt", "rt"):
                    setattr(st, attr, int(info.value))
                else:
                    setattr(st, attr, int(info.value))
            except OSError:
                pass

    def pump(self) -> BtHidReport | None:
        """Read pending evdev events; return a snapshot report if anything changed."""
        changed = False
        try:
            events = self.dev.read()
        except BlockingIOError:
            return None
        except OSError:
            return None
        st = self.state
        assert st.buttons is not None
        for e in events:
            if e.type == ecodes.EV_KEY:
                name = BTN_FROM_EV.get(e.code)
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
            hat=0,
            buttons=dict(st.buttons),
        )
