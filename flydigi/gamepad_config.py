"""Onboard gamepad config blob (IF2 cmd 235/234) — V2 layout.

Vader 4 Pro (config v1.3) live dump is **840 bytes** (84 parcels × 10;
header byte[2] == 83 = max parcel index). Older flydigictl pads used 520 bytes
(52 parcels). Offsets match Space Station 4 `getConfigListsV2`. Key slot
indices 0–31 align with SS4 `device_config_f4` hotspot `id` values when id < 32
(JsLeft/JsRight use 240/241 UI-only ids and are not remapped via this blob).

Writing a truncated 520-byte blob is ACK'd for the early parcels but the pad
reverts to flash within ~1s — remaps look saved then bounce back on reconnect.

Completing a full 234 transfer (all 84 data parcels) makes fw 6.9.x discard
the stage and reload flash. Stage with the final parcel omitted, then
SaveFlash (80/3) immediately — no config read in between — and remaps stick
across reconnect (**O**).
"""

from __future__ import annotations

from dataclasses import dataclass, field

KEY_NAMES = [
    "UP",
    "RIGHT",
    "DOWN",
    "LEFT",
    "A",
    "B",
    "SELECT",
    "X",
    "Y",
    "START",
    "LB",
    "RB",
    "LT",
    "RT",
    "THUMBL",
    "THUMBR",
    "C",
    "Z",
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "MENU",
    "?",
    "?",
    "HOME",
    "BACK",
    "?",
    "?",
    "?",
]


@dataclass
class Curve:
    type: int = 0
    zero: int = 0  # deadzone
    p0x: int = 0
    p0y: int = 0
    p1x: int = 0
    p1y: int = 0
    end: int = 100

    def to_bytes(self) -> bytes:
        return bytes(
            (
                self.type & 0xFF,
                self.zero & 0xFF,
                self.p0x & 0xFF,
                self.p0y & 0xFF,
                self.p1x & 0xFF,
                self.p1y & 0xFF,
                self.end & 0xFF,
            )
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Curve:
        d = data.ljust(7, b"\x00")
        return cls(d[0], d[1], d[2], d[3], d[4], d[5], d[6])


@dataclass
class KeyMap:
    key_id: int
    name: str
    map_id: int  # 255 = native / identity
    turbo_type: int = 0
    turbo: int = 0

    @property
    def is_remapped(self) -> bool:
        # 255 = identity; 254 = keyboard/macro (host); 32 = SS unused filler.
        if self.map_id in (255, self.key_id):
            return False
        if self.map_id in (254, 32):
            return True
        return 0 <= self.map_id < 32


@dataclass
class MotorSide:
    type: int = 0
    min: int = 0
    max: int = 100
    scale: int = 100


@dataclass
class MotorConfig:
    main_switch: bool = True  # wire: 0 = on, 1 = off
    left: MotorSide = field(default_factory=MotorSide)
    right: MotorSide = field(default_factory=MotorSide)


@dataclass
class MotionConfig:
    map_type: int = 0
    open_key_id: int = 0
    open_map_method: int = 0
    zero: int = 0
    sens_x: int = 50
    sens_y: int = 50
    mode: int = 0
    open_key_ext_id: int = 0


@dataclass
class GamepadConfig:
    raw: bytearray
    version: str = "1.3"
    package_length: int = 82
    keys: list[KeyMap] = field(default_factory=list)
    left_stick: Curve = field(default_factory=Curve)
    right_stick: Curve = field(default_factory=Curve)
    left_trigger: Curve = field(default_factory=Curve)
    right_trigger: Curve = field(default_factory=Curve)
    motion: MotionConfig = field(default_factory=MotionConfig)
    motor: MotorConfig = field(default_factory=MotorConfig)
    # embedded basic LED (legacy 10-byte block inside config)
    led_mode: int = 0
    led_period: int = 0
    led_light: int = 100
    led_rgb0: tuple[int, int, int] = (0, 0, 0)
    led_rgb1: tuple[int, int, int] = (0, 0, 0)

    # V2 offsets
    OFF_VERSION = 0
    OFF_PKG = 2
    OFF_LED = 3
    OFF_KEYS = 13
    OFF_JOY = 109
    OFF_TRIG = 123
    OFF_MOTION = 137
    OFF_MOTOR = 145


def decode_gamepad_config(data: bytes) -> GamepadConfig:
    raw = bytearray(data)
    if len(raw) < 154:
        raise ValueError(f"config too short: {len(raw)}")
    cfg = GamepadConfig(raw=raw)
    cfg.version = f"{raw[0]}.{raw[1]}"
    cfg.package_length = max(0, raw[2] - 1)

    led = raw[3:13]
    cfg.led_mode = led[1]
    cfg.led_period = led[2]
    cfg.led_light = led[3]
    cfg.led_rgb0 = (led[4], led[5], led[6])
    cfg.led_rgb1 = (led[7], led[8], led[9])

    keys_blob = raw[13:109]
    cfg.keys = []
    for i in range(min(32, len(keys_blob) // 3)):
        base = i * 3
        name = KEY_NAMES[i] if i < len(KEY_NAMES) else f"K{i}"
        cfg.keys.append(
            KeyMap(
                key_id=i,
                name=name,
                map_id=keys_blob[base],
                turbo_type=keys_blob[base + 1],
                turbo=keys_blob[base + 2],
            )
        )

    cfg.left_stick = Curve.from_bytes(raw[109:116])
    cfg.right_stick = Curve.from_bytes(raw[116:123])
    cfg.left_trigger = Curve.from_bytes(raw[123:130])
    cfg.right_trigger = Curve.from_bytes(raw[130:137])

    m = raw[137:145]
    cfg.motion = MotionConfig(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7])

    mot = raw[145:154]
    left = MotorSide(mot[1], min(mot[2], mot[3]), max(mot[2], mot[3]), mot[4])
    right = MotorSide(mot[5], min(mot[6], mot[7]), max(mot[6], mot[7]), mot[8])
    cfg.motor = MotorConfig(main_switch=(mot[0] == 0), left=left, right=right)
    return cfg


def encode_gamepad_config(cfg: GamepadConfig) -> bytes:
    """Re-pack editable fields into the original blob (preserves unknown tails)."""
    raw = bytearray(cfg.raw)
    if len(raw) < 154:
        raw.extend(b"\x00" * (154 - len(raw)))

    # version / package length left as-is unless caller changed them
    ver_parts = cfg.version.split(".")
    if len(ver_parts) >= 2:
        raw[0] = int(ver_parts[0]) & 0xFF
        raw[1] = int(ver_parts[1]) & 0xFF
    raw[2] = (cfg.package_length + 1) & 0xFF

    raw[3] = 32
    raw[4] = cfg.led_mode & 0xFF
    raw[5] = cfg.led_period & 0xFF
    raw[6] = cfg.led_light & 0xFF
    raw[7:10] = bytes(cfg.led_rgb0)
    raw[10:13] = bytes(cfg.led_rgb1)

    for i, k in enumerate(cfg.keys[:32]):
        base = 13 + i * 3
        raw[base] = k.map_id & 0xFF
        raw[base + 1] = k.turbo_type & 0xFF
        raw[base + 2] = k.turbo & 0xFF

    raw[109:116] = cfg.left_stick.to_bytes()
    raw[116:123] = cfg.right_stick.to_bytes()
    raw[123:130] = cfg.left_trigger.to_bytes()
    raw[130:137] = cfg.right_trigger.to_bytes()

    m = cfg.motion
    raw[137:145] = bytes(
        (
            m.map_type,
            m.open_key_id,
            m.open_map_method,
            m.zero,
            m.sens_x,
            m.sens_y,
            m.mode,
            m.open_key_ext_id,
        )
    )

    mot = cfg.motor
    raw[145] = 0 if mot.main_switch else 1
    raw[146] = mot.left.type & 0xFF
    raw[147] = mot.left.min & 0xFF
    raw[148] = mot.left.max & 0xFF
    raw[149] = mot.left.scale & 0xFF
    raw[150] = mot.right.type & 0xFF
    raw[151] = mot.right.min & 0xFF
    raw[152] = mot.right.max & 0xFF
    raw[153] = mot.right.scale & 0xFF
    return bytes(raw)
