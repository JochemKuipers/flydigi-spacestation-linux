"""Flydigi V1 input report (IF2, report ID 0x04, magic 0xFE).

Layout cross-checked against live Vader 4 Pro dongle captures and
SDL_hidapi_flydigi.c HandleStatePacketV1.
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

REPORT_ID = 0x04
MAGIC = 0xFE
PACKET_LEN = 32


def _i16(lo: int, hi: int) -> int:
    return unpack_from("<h", bytes((lo & 0xFF, hi & 0xFF)))[0]


def _stick(u8: int) -> int:
    """Map 0..255 centered at 0x7F to roughly -32767..32767."""
    if u8 == 0x7F:
        return 0
    return int((u8 - 0x7F) * 32767 / 0x7F)


def _trigger(u8: int) -> int:
    return u8


@dataclass(frozen=True)
class V1Report:
    raw: bytes
    buttons: dict[str, bool]
    hat: int  # 0..8 linux-style: 0=up ... 8=center encoded separately
    hat_x: int
    hat_y: int
    lx: int
    ly: int
    rx: int
    ry: int
    lt: int
    rt: int
    accel: tuple[int, int, int]
    gyro: tuple[int, int, int]


_HAT_TO_XY = {
    0x01: (0, -1),
    0x03: (1, -1),
    0x02: (1, 0),
    0x06: (1, 1),
    0x04: (0, 1),
    0x0C: (-1, 1),
    0x08: (-1, 0),
    0x09: (-1, -1),
}


def parse_v1_report(data: bytes) -> V1Report | None:
    if len(data) < PACKET_LEN:
        return None
    if data[0] != REPORT_ID or data[1] != MAGIC:
        return None

    b7, b8, b9, b10 = data[7], data[8], data[9], data[10]
    hat_n = b9 & 0x0F
    hx, hy = _HAT_TO_XY.get(hat_n, (0, 0))

    buttons = {
        "a": bool(b9 & 0x10),
        "b": bool(b9 & 0x20),
        "select": bool(b9 & 0x40),
        "x": bool(b9 & 0x80),
        "y": bool(b10 & 0x01),
        "start": bool(b10 & 0x02),
        "lb": bool(b10 & 0x04),
        "rb": bool(b10 & 0x08),
        "ls": bool(b10 & 0x40),
        "rs": bool(b10 & 0x80),
        "guide": bool(b8 & 0x08),
        "c": bool(b7 & 0x01),
        "z": bool(b7 & 0x02),
        "m1": bool(b7 & 0x04),
        "m2": bool(b7 & 0x08),
        "m3": bool(b7 & 0x10),
        "m4": bool(b7 & 0x20),
    }

    accel = (
        _i16(data[11], data[12]),
        _i16(data[15], data[16]),
        _i16(data[13], data[14]),
    )
    # SDL V1 gyro packing
    gyro = (
        _i16(data[26], data[27]),
        _i16(data[18], data[20]),
        _i16(data[29], data[30]),
    )

    return V1Report(
        raw=bytes(data[:PACKET_LEN]),
        buttons=buttons,
        hat=hat_n,
        hat_x=hx,
        hat_y=hy,
        lx=_stick(data[17]),
        ly=_stick(data[19]),
        rx=_stick(data[21]),
        ry=_stick(data[22]),
        lt=_trigger(data[23]),
        rt=_trigger(data[24]),
        accel=accel,
        gyro=gyro,
    )
