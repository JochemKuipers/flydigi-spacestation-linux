"""Bluetooth DInput HID report parser for Flydigi VADER4P (d7d7:0041).

Report ID 0x01 — standard Game Pad (not USB IF2 04 FE). Layout from live
descriptor + captures in captures/bt-dinput-blue-20261024/.

Packing after report ID:
  int8 X Y Z Rz
  u8  ×4          (unused / vendor; LT/RT are Gas/Brake at tail)
  hat:4 + buttons:12   (exactly 2 bytes)
  consumer:15 bits     (C/Z/M/Guide/FN disguised as media keys)
  +1 consumer bit
  u8 Brake, u8 Gas
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

REPORT_ID = 0x01

# 12 button usages in descriptor order → our names.
# Usages 0x0E/0x0F are digital trigger clicks (kernel TL2/TR2), NOT C/Z.
_BTN_NAMES = (
    "a", "b", "x", "y", "lb", "rb", "select", "start", "ls", "rs",
    "_lt_click", "_rt_click",
)

# Consumer bits (after the 12 gamepad buttons), mapped from live KEY_* captures.
# Indices match descriptor order: 0x36,0x84,0xB8,0x9C,0x9D,0x89,0x8D,0x65,0x82,0x8A,…
_CONSUMER_NAMES = (
    None,       # 0 Menu
    None,       # 1
    "m1",       # 2 Eject → KEY_EJECTCD
    "m2",       # 3 → KEY_CHANNELUP
    "m3",       # 4 → KEY_CHANNELDOWN
    "m4",       # 5 → KEY_TV
    None,       # 6
    "c",        # 7 Camera → KEY_CAMERA
    "z",        # 8
    "guide",    # 9
    "fn",       # 10 (+ padding bits)
    None,
    None,
    None,
    None,
)


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

    buttons = {n: False for n in (
        "a", "b", "x", "y", "lb", "rb", "select", "start", "guide",
        "ls", "rs", "c", "z", "m1", "m2", "m3", "m4", "fn",
    )}
    for i, name in enumerate(_BTN_NAMES):
        if name.startswith("_"):
            continue
        if btn_bits & (1 << i):
            buttons[name] = True

    # Consumer field begins at bit 16 of the hat/button region → data[11].
    cons = int.from_bytes(data[11:14], "little") if len(data) >= 14 else 0
    for i, name in enumerate(_CONSUMER_NAMES):
        if name and (cons & (1 << i)):
            buttons[name] = True

    # Gas/Brake are the last two bytes of the fixed report (descriptor order:
    # Brake 0xC5, Accelerator 0xC4).
    lt = rt = 0
    if len(data) >= 16:
        # Prefer explicit tail; fall back to bytes 5/6 if short.
        rt = data[-2]
        lt = data[-1]
        # Heuristic: idle reports end with …9a6d8400 noise; real triggers are
        # the descriptor Gas/Brake near the end. Live idle had lt/rt via evdev
        # ABS_GAS/BRAKE — keep both paths in the evdev bridge.
        if len(data) >= 21:
            # Observed layout: … [cons…] [01 00] [9a 6d] [brake?] [gas?]
            pass

    return BtHidReport(
        raw=bytes(data),
        lx=_stick8(x),
        ly=_stick8(y),
        rx=_stick8(z),
        ry=_stick8(rz),
        lt=lt,
        rt=rt,
        hat_x=hx,
        hat_y=hy,
        hat=hat if hat else hat_from_xy(hx, hy),
        buttons=buttons,
    )
