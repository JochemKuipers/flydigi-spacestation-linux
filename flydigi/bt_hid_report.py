"""Bluetooth DInput HID report parser for Flydigi VADER4P (d7d7:0041).

Report ID 0x01 — standard Game Pad (not USB IF2 04 FE). Button/consumer
bit assignments come from the calibrated map (flydigi/bt_button_map.json).
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

from .bt_map import btn_names_by_bit, cons_names_by_bit

REPORT_ID = 0x01


def _stick8(v: int) -> int:
    if v == 0:
        return 0
    return int(max(-32767, min(32767, v * 32767 / 127)))


def _hat_xy(hat: int) -> tuple[int, int]:
    table = {
        1: (0, -1),
        2: (1, -1),
        3: (1, 0),
        4: (1, 1),
        5: (0, 1),
        6: (-1, 1),
        7: (-1, 0),
        8: (-1, -1),
    }
    return table.get(hat, (0, 0))


def hat_from_xy(hx: int, hy: int) -> int:
    table = {
        (0, -1): 1,
        (1, -1): 2,
        (1, 0): 3,
        (1, 1): 4,
        (0, 1): 5,
        (-1, 1): 6,
        (-1, 0): 7,
        (-1, -1): 8,
        (0, 0): 0,
    }
    return table.get((hx, hy), 0)


@dataclass(frozen=True)
class BtHidReport:
    raw: bytes
    lx: int
    ly: int
    rx: int
    ry: int
    lt: int
    rt: int
    hat_x: int
    hat_y: int
    hat: int
    buttons: dict[str, bool]


def parse_bt_hid_report(data: bytes) -> BtHidReport | None:
    if len(data) < 14 or data[0] != REPORT_ID:
        return None

    x, y, z, rz = unpack_from("bbbb", data, 1)
    packed = data[9] | (data[10] << 8)
    hat = packed & 0x0F
    btn_bits = (packed >> 4) & 0xFFF
    hx, hy = _hat_xy(hat)

    buttons = {
        n: False
        for n in (
            "a",
            "b",
            "x",
            "y",
            "lb",
            "rb",
            "select",
            "start",
            "guide",
            "ls",
            "rs",
            "c",
            "z",
            "m1",
            "m2",
            "m3",
            "m4",
            "fn",
        )
    }
    for i, name in enumerate(btn_names_by_bit()):
        if name and (btn_bits & (1 << i)):
            buttons[name] = True

    cons = int.from_bytes(data[11:14], "little") if len(data) >= 14 else 0
    for bit, name in cons_names_by_bit().items():
        if cons & (1 << bit):
            buttons[name] = True

    return BtHidReport(
        raw=bytes(data),
        lx=_stick8(x),
        ly=_stick8(y),
        rx=_stick8(z),
        ry=_stick8(rz),
        lt=0,  # filled from evdev ABS by bridge
        rt=0,
        hat_x=hx,
        hat_y=hy,
        hat=hat if hat else hat_from_xy(hx, hy),
        buttons=buttons,
    )
