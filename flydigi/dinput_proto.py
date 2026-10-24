"""Flydigi Vader 4 Pro DInput control protocol on USB IF2.

Wire format cross-checked against pipe01/flydigictl and live 04b4:2412 captures
(GetDeviceInfo cmd 236 → response with byte[15]==236).
"""

from __future__ import annotations

import math
import os
import select
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .enumerate import find_input_interface
from .v1_report import PACKET_LEN, parse_v1_report

CMD_GET_DONGLE_VERSION = 17
CMD_READ_LED_CONFIG = 229
CMD_WRITE_LED_START = 231
CMD_WRITE_CONFIG_START = 234
CMD_READ_CONFIG = 235
CMD_GET_DEVICE_INFO = 236
CMD_HAPTIC = 0x0F  # SDL V1 rumble on report 5

LED_PACKAGE_LENGTH = 49
CONFIG_PACKAGE_LENGTH = 52
MAX_PARCEL = 10


@dataclass
class DeviceInfo:
    device_id: int
    device_mac: bytes
    fw_l: int
    fw_h: int
    battery: int
    cpu_type: int
    connection_type: int
    motion_sensor_type: int

    @property
    def firmware_version(self) -> str:
        fl, fl2 = self.fw_l & 15, self.fw_l >> 4
        fh, fh2 = self.fw_h & 15, self.fw_h >> 4
        return f"{fh2}.{fh}.{fl2}.{fl}"

    @property
    def battery_level(self) -> int | None:
        # Vader 4 Pro: flydigictl treats 0..4 as charge steps; else percentage
        if 0 <= self.battery <= 4:
            return self.battery * 25
        if self.battery <= 100:
            return self.battery
        return None


@dataclass
class LedConfig:
    version: bytes = field(default_factory=lambda: bytes((1, 0)))
    type: int = 0
    loop_start: int = 0
    loop_end: int = 0
    loop_time: int = 50  # inverted speed: higher = slower
    light_scale: int = 100
    rgb_num: int = 5
    led_mode: int = 5  # steady
    reserve: bytes = field(default_factory=lambda: bytes([255] * 11))
    # 16 groups × 10 units × RGB — we only fill rgb_num groups
    groups: list[list[tuple[int, int, int]]] = field(default_factory=list)

    # SS4 LED_TYPE_*: Unknown=0, FLOW=1, BREATH=2, GRADIENT=3, FEEDBACK=4, ON=5, Close=6, Default=7
    MODE_OFF = 0  # treated as off by firmware; Close=6 also works
    MODE_STREAMLINED = 1  # FLOW
    MODE_BREATHING = 2
    MODE_GRADIENT = 3
    MODE_FEEDBACK = 4
    MODE_STEADY = 5  # ON
    MODE_CLOSE = 6


def encode_led_config(cfg: LedConfig) -> bytes:
    out = bytearray()
    out += cfg.version[:2].ljust(2, b"\x00")
    out.append(cfg.type & 0xFF)
    out.append(cfg.loop_start & 0xFF)
    out.append(cfg.loop_end & 0xFF)
    out.append(cfg.loop_time & 0xFF)
    out.append(cfg.light_scale & 0xFF)
    out.append(cfg.rgb_num & 0xFF)
    out.append(cfg.led_mode & 0xFF)
    out += (cfg.reserve[:11]).ljust(11, b"\xff")
    groups = list(cfg.groups)
    while len(groups) < 16:
        groups.append([(0, 0, 0)] * 10)
    for g in groups[:16]:
        units = list(g)
        while len(units) < 10:
            units.append((0, 0, 0))
        for r, g_, b in units[:10]:
            out.extend((r & 0xFF, g_ & 0xFF, b & 0xFF))
    return bytes(out)


def decode_led_config(data: bytes) -> LedConfig:
    if len(data) < 20:
        raise ValueError("LED config too short")
    cfg = LedConfig(
        version=data[:2],
        type=data[2],
        loop_start=data[3],
        loop_end=data[4],
        loop_time=data[5],
        light_scale=data[6],
        rgb_num=data[7],
        led_mode=data[8],
        reserve=data[9:20],
        groups=[],
    )
    idx = 20
    for _ in range(15):  # flydigictl uses 15 groups from device
        units = []
        for j in range(10):
            if idx + 2 >= len(data):
                units.append((0, 0, 0))
            else:
                units.append((data[idx], data[idx + 1], data[idx + 2]))
            idx += 3
        cfg.groups.append(units)
    return cfg


def _groups_from_ss_table(table_idx: int, n: int = 5) -> list[list[tuple[int, int, int]]]:
    """Copy official NewLedTypeDto.ledUnits[mode][led][frame][rgb]."""
    from flydigi.ss4_led_tables import LED_UNITS

    table = LED_UNITS[table_idx]
    groups: list[list[tuple[int, int, int]]] = []
    for led in range(n):
        frames = [tuple(table[led][f]) for f in range(10)]  # type: ignore[misc]
        groups.append(frames)  # type: ignore[arg-type]
    return groups


def _dim(color: tuple[int, int, int], factor: float = 0.8) -> tuple[int, int, int]:
    return (
        min(255, int(color[0] * factor)),
        min(255, int(color[1] * factor)),
        min(255, int(color[2] * factor)),
    )


def _zero_frames() -> list[tuple[int, int, int]]:
    return [(0, 0, 0)] * 10


def _create_led_units(colors: list[tuple[int, int, int]], dimming: bool) -> list[tuple[int, int, int]]:
    """NewLedTypeDto.CreateLedUnits — breath: color on even frames, black on odd."""
    out: list[tuple[int, int, int]] = []
    for i in range(10):
        if i % 2 == 0:
            c = colors[min(i // 2, len(colors) - 1)]
            out.append(_dim(c) if dimming else c)
        else:
            out.append((0, 0, 0))
    return out


def _create_led_units2(colors: list[tuple[int, int, int]], dimming: bool) -> list[tuple[int, int, int]]:
    """NewLedTypeDto.CreateLedUnits2 — gradient: first two frames are the two colors."""
    out: list[tuple[int, int, int]] = []
    for i in range(10):
        if i < 2 and i < len(colors):
            out.append(_dim(colors[i]) if dimming else colors[i])
        else:
            out.append((0, 0, 0))
    return out


def _create_led_units3(colors: list[tuple[int, int, int]], dimming: bool) -> list[tuple[int, int, int]]:
    """NewLedTypeDto.CreateLedUnits3 — feedback/steady: only frame 0 lit."""
    c = colors[0] if colors else (0, 0, 0)
    return [(_dim(c) if dimming else c)] + [(0, 0, 0)] * 9


def _breath_groups_custom(color: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    """Match GetLedGroupListByCustom Id=2 (5× same color)."""
    colors = [color] * 5
    return [
        _create_led_units(colors, False),
        _create_led_units(colors, True),
        _zero_frames(),
        _zero_frames(),
        _create_led_units(colors, True),
    ]


def _gradient_groups_custom(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    """Match GetLedGroupListByCustom Id=3."""
    pair = [c1, c2]
    return [_create_led_units2(pair, False) for _ in range(5)]


def _feedback_groups_custom(color: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    """Match GetLedGroupListByCustom Id=4."""
    colors = [color]
    return [
        _create_led_units3(colors, False),
        _create_led_units3(colors, True),
        _zero_frames(),
        _zero_frames(),
        _create_led_units3(colors, True),
    ]


def _steady_groups_custom(color: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    """Match GetLedGroupListByCustom Id=5."""
    colors = [color]
    return [_create_led_units3(colors, False) for _ in range(5)]


def steady_led(r: int, g: int, b: int, brightness: int = 100) -> LedConfig:
    color = (r, g, b)
    return LedConfig(
        led_mode=LedConfig.MODE_STEADY,
        rgb_num=5,
        loop_start=0,
        loop_end=0,
        loop_time=15,
        type=0,
        light_scale=max(0, min(100, brightness)),
        groups=_steady_groups_custom(color),
    )


def off_led(brightness: int = 0) -> LedConfig:
    # Official Close mode is LedMode=6 (not 0)
    return LedConfig(
        led_mode=LedConfig.MODE_CLOSE,
        rgb_num=5,
        loop_start=0,
        loop_end=0,
        loop_time=15,
        light_scale=brightness,
        groups=_groups_from_ss_table(5, 5),
    )


def build_led(
    mode: int,
    *,
    r: int = 0,
    g: int = 0,
    b: int = 0,
    brightness: int = 80,
    speed: int = 50,
) -> LedConfig:
    """Build NewLedConfig using Space Station's official F4 defaults.

    Source: NewLedTypeDto.GetDefaultConfig / ledUnits / GetLedGroupListByCustom.
    Moving rainbow is Flow (mode 1, loop_end=5) — not Gradient.
    """
    from flydigi.ss4_led_tables import MODE_DEFAULTS

    brightness = max(0, min(100, int(brightness)))
    # SS default LoopTime=15 at mid UI speed; higher speed → lower time
    loop_time = max(5, min(40, round(15 * (150 - int(speed)) / 100)))
    color = (int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)
    n = 5

    if mode in (LedConfig.MODE_OFF, LedConfig.MODE_CLOSE):
        return off_led(brightness)

    wire_mode = mode if mode in MODE_DEFAULTS else LedConfig.MODE_STEADY
    meta = MODE_DEFAULTS[wire_mode]

    if wire_mode == LedConfig.MODE_STREAMLINED:
        # Exact official rainbow chase table — do not tint
        groups = _groups_from_ss_table(int(meta["table"]), n)
    elif wire_mode == LedConfig.MODE_BREATHING:
        groups = _breath_groups_custom(color)
    elif wire_mode == LedConfig.MODE_GRADIENT:
        c2 = (max(0, 255 - color[0]), max(0, 255 - color[1]), max(0, 255 - color[2]))
        groups = _gradient_groups_custom(color, c2)
    elif wire_mode == LedConfig.MODE_FEEDBACK:
        groups = _feedback_groups_custom(color)
    else:
        groups = _steady_groups_custom(color)

    return LedConfig(
        led_mode=wire_mode,
        type=1 if wire_mode == LedConfig.MODE_FEEDBACK else 0,
        rgb_num=n,
        loop_start=0,
        loop_end=int(meta["loop_end"]),
        loop_time=loop_time,
        light_scale=brightness,
        groups=groups,
    )


def _split_parcels(header: bytes, inner_cmd: int, data: bytes) -> list[bytes]:
    parcel_count = max(1, math.ceil(len(data) / MAX_PARCEL))
    buf = bytearray(header)
    # pad header to MAX_PARCEL+4 like flydigictl
    while len(buf) < MAX_PARCEL + 4:
        buf.append(0)
    header_block = bytes(buf[: MAX_PARCEL + 4])
    out_stream = bytearray(header_block)
    for i in range(parcel_count):
        out_stream.append(5)
        out_stream.append(inner_cmd & 0xFF)
        for j in range(MAX_PARCEL):
            di = i * MAX_PARCEL + j
            out_stream.append(data[di] if di < len(data) else 0)
        out_stream.append(160)
        out_stream.append(i & 0xFF)
    chunk_size = MAX_PARCEL + 4
    return [bytes(out_stream[k : k + chunk_size]) for k in range(0, len(out_stream), chunk_size)]


def led_config_parcels(data: bytes, config_id: int = 0) -> list[bytes]:
    parcel_count = max(1, math.ceil(len(data) / MAX_PARCEL))
    header = bytes((5, CMD_WRITE_LED_START, config_id & 0xFF, parcel_count & 0xFF))
    return _split_parcels(header, 51, data)


def gamepad_config_parcels(data: bytes, config_id: int = 0) -> list[bytes]:
    parcel_count = max(1, math.ceil(len(data) / MAX_PARCEL))
    header = bytes((5, CMD_WRITE_CONFIG_START, parcel_count & 0xFF, 160, config_id & 0xFF))
    return _split_parcels(header, 34, data)


class DInputDevice:
    """Exclusive-ish session on IF2 hidraw for input + commands."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            iface = find_input_interface()
            if iface is None:
                raise FileNotFoundError("Vader 4 Pro IF2 not found")
            path = iface.hidraw
        self.path = path
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self._config_id = 0
        self._acks: list[int] = []
        self._device_info: DeviceInfo | None = None
        self._led_chunks: dict[int, bytes] = {}
        self._led_expected = LED_PACKAGE_LENGTH
        self._cfg_chunks: dict[int, bytes] = {}
        self._cfg_expected = CONFIG_PACKAGE_LENGTH
        self._led_data: bytes | None = None
        self._cfg_data: bytes | None = None
        self._dongle_fw: tuple[int, int] | None = None

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

    def fileno(self) -> int:
        return self.fd

    def write_raw(self, data: bytes) -> None:
        os.write(self.fd, data)

    def send_command(self, cmd: int, *args: int) -> None:
        buf = bytearray(12)
        buf[0] = 5
        buf[1] = cmd & 0xFF
        for i, a in enumerate(args[:10]):
            buf[2 + i] = a & 0xFF
        self.write_raw(bytes(buf))

    def rumble(self, low: int, high: int) -> None:
        """V1 haptic on OUT report 5 (HID report count 31 → write 32 bytes).

        SDL packs Uint16 rumble as high bytes into [2]/[3]; motors need the
        packet refreshed ~every 20–50 ms while active (one-shot feels dead).
        """
        lo = max(0, min(255, int(low)))
        hi = max(0, min(255, int(high)))
        buf = bytearray(32)
        buf[0] = 5
        buf[1] = CMD_HAPTIC
        buf[2] = lo
        buf[3] = hi
        self.write_raw(bytes(buf))

    def request_device_info(self) -> None:
        self._device_info = None
        self.send_command(CMD_GET_DEVICE_INFO)

    def request_dongle_version(self) -> None:
        self._dongle_fw = None
        self.send_command(CMD_GET_DONGLE_VERSION)

    def request_led_config(self, config_id: int | None = None) -> None:
        cid = self._config_id if config_id is None else config_id
        self._led_chunks.clear()
        self._led_data = None
        self.send_command(CMD_READ_LED_CONFIG, cid)

    def request_gamepad_config(self, config_id: int | None = None) -> None:
        cid = self._config_id if config_id is None else config_id
        self._cfg_chunks.clear()
        self._cfg_data = None
        self.send_command(CMD_READ_CONFIG, cid)

    def write_led_config(self, cfg: LedConfig, config_id: int | None = None) -> None:
        cid = self._config_id if config_id is None else config_id
        data = encode_led_config(cfg)
        for chunk in led_config_parcels(data, cid):
            self.write_raw(chunk)
            time.sleep(0.02)

    def pump(self, timeout: float = 0.0) -> object | None:
        """Read one packet; return V1Report, DeviceInfo update, or None."""
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        try:
            data = os.read(self.fd, 64)
        except BlockingIOError:
            return None
        return self._dispatch(data)

    def _dispatch(self, data: bytes) -> object | None:
        if len(data) < 2:
            return None
        # V1 gamepad stream
        rep = parse_v1_report(data)
        if rep is not None:
            return rep

        if len(data) > 15 and data[15] == CMD_GET_DEVICE_INFO:
            info = DeviceInfo(
                device_id=data[3],
                device_mac=bytes(data[5:9]),
                fw_l=data[9],
                fw_h=data[10],
                battery=data[11],
                cpu_type=data[12],
                connection_type=data[13],
                motion_sensor_type=data[14],
            )
            self._device_id_seen(info)
            self._device_info = info
            return info

        if data[0] == 4 and data[1] == CMD_GET_DONGLE_VERSION and len(data) > 3:
            self._dongle_fw = (data[2], data[3])
            return ("dongle", self._dongle_fw)

        if len(data) > 15 and data[15] == CMD_READ_LED_CONFIG:
            idx = data[3]
            self._led_chunks[idx] = bytes(data[5:15])
            if len(self._led_chunks) >= self._led_expected:
                buf = bytearray()
                for i in range(self._led_expected):
                    buf += self._led_chunks.get(i, b"\x00" * 10)
                self._led_data = bytes(buf)
                return ("led", self._led_data)

        if len(data) > 15 and data[15] == CMD_READ_CONFIG:
            idx = data[3]
            self._cfg_chunks[idx] = bytes(data[5:15])
            if len(self._cfg_chunks) >= self._cfg_expected:
                buf = bytearray()
                for i in range(self._cfg_expected):
                    buf += self._cfg_chunks.get(i, b"\x00" * 10)
                self._cfg_data = bytes(buf)
                return ("config", self._cfg_data)

        if len(data) > 15 and data[15] in (CMD_WRITE_CONFIG_START, CMD_WRITE_LED_START, 51):
            self._acks.append(int(data[3]))
            return ("ack", data[3])

        return None

    def _device_id_seen(self, info: DeviceInfo) -> None:
        # mapping profile id often equals onboard slot; keep 0 default
        pass

    def wait_device_info(
        self,
        timeout: float = 2.0,
        on_report: Callable[[object], None] | None = None,
    ) -> DeviceInfo:
        self.request_device_info()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self.pump(0.1)
            if isinstance(msg, DeviceInfo):
                return msg
            if msg is not None and on_report is not None:
                on_report(msg)
        raise TimeoutError("no device info response")

    def wait_led_config(
        self,
        timeout: float = 3.0,
        on_report: Callable[[object], None] | None = None,
    ) -> LedConfig:
        self.request_led_config()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self.pump(0.1)
            if isinstance(msg, tuple) and msg[0] == "led":
                return decode_led_config(msg[1])
            if msg is not None and on_report is not None:
                on_report(msg)
        raise TimeoutError("no LED config response")
