"""Bluetooth DInput HID report parser for Flydigi VADER4P (d7d7:0041).

Unlike USB IF2 (04 FE V1), BT DInput exposes a standard HID Game Pad
collection (report ID 0x01) via BlueZ/uhid. Layout taken from the live
report descriptor in captures/bt-dinput-blue-20261024/.
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

REPORT_ID = 0x01


def _stick8(v: int) -> int:
    """Signed int8 (-128..127) → roughly -32767..32767."""
    if v == 0:
        return 0
    return int(v * 32767 / 127)


def _hat_xy(hat: int) -> tuple[int, int]:
    # HID hat 1..8, 0/8+ = center (null)
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
    """Parse report ID 1.

    Descriptor order (simplified):
      X Y Z Rz          int8 ×4
      4× u8             (Vx-style / extras — first two used as LT/RT empirically TBD)
      hat nibble
      12 button bits    usages 1,2,4,5,7,8,9,a,b,c,e,f
      consumer + sim axes follow (ignored for gamepad uinput)
    """
    if len(data) < 12 or data[0] != REPORT_ID:
        return None

    x, y, z, rz = unpack_from("bbbb", data, 1)
    # bytes 5..8: four u8 axes from descriptor (0x40..0x43). On this pad
    # kernel maps GAS/BRAKE separately at end; mid bytes often LT/RT-like.
    u0, u1, u2, u3 = data[5], data[6], data[7], data[8]
    hat_byte = data[9]
    hat = hat_byte & 0x0F
    hx, hy = _hat_xy(hat)

    # 12 buttons packed after hat nibble padding — bits start at byte 10
    # Descriptor: 4-bit hat + 4-bit pad, then 12×1-bit buttons.
    btn_bits = int.from_bytes(data[10:12], "little") if len(data) >= 12 else 0
    # Button usages in descriptor order (skipping 3,6,d):
    usage_order = [1, 2, 4, 5, 7, 8, 9, 0xA, 0xB, 0xC, 0xE, 0xF]
    # Map to our names (best-effort Xbox-ish):
    name_by_usage = {
        1: "a",
        2: "b",
        4: "x",
        5: "y",
        7: "lb",
        8: "rb",
        9: "select",
        0xA: "start",
        0xB: "ls",
        0xC: "rs",
        0xE: "c",
        0xF: "z",
    }
    buttons = {n: False for n in (
        "a", "b", "x", "y", "lb", "rb", "select", "start", "guide",
        "ls", "rs", "c", "z", "m1", "m2", "m3", "m4",
    )}
    for i, usage in enumerate(usage_order):
        name = name_by_usage.get(usage)
        if name and (btn_bits >> i) & 1:
            buttons[name] = True

    # Prefer trailing sim axes if present (descriptor Gas/Brake near end).
    lt, rt = u0, u1
    if len(data) >= 15:
        # heuristic: last two bytes before end often brake/gas in this descriptor
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
        hat=hat,
        buttons=buttons,
    )
