"""Human-readable names for onboard key IDs / report buttons."""

from __future__ import annotations

# Index order matches flydigi.gamepad_config.KEY_NAMES
KEY_LABELS = [
    "D-pad up",
    "D-pad right",
    "D-pad down",
    "D-pad left",
    "A (bottom)",
    "B (right)",
    "Select / View",
    "X (left)",
    "Y (top)",
    "Start / Menu",
    "LB (left bumper)",
    "RB (right bumper)",
    "LT (left trigger)",
    "RT (right trigger)",
    "Left stick click",
    "Right stick click",
    "C",
    "Z",
    "Back button M1",
    "Back button M2",
    "Back button M3",
    "Back button M4",
    "Back button M5",
    "Back button M6",
    "Home / Guide",
    "—",
    "—",
    "Home",
    "Back",
    "—",
    "—",
    "—",
]

REPORT_BUTTON_LABELS = {
    "a": "A",
    "b": "B",
    "x": "X",
    "y": "Y",
    "lb": "LB",
    "rb": "RB",
    "lt": "LT",
    "rt": "RT",
    "ls": "L3",
    "rs": "R3",
    "select": "Select",
    "start": "Start",
    "guide": "Home",
    "c": "C",
    "z": "Z",
    "m1": "M1",
    "m2": "M2",
    "m3": "M3",
    "m4": "M4",
}

# Single-word overlay glyphs drawn inside hotspot shapes
OVERLAY_LABELS = {
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "C": "C",
    "Z": "Z",
    "Lt": "LT",
    "Lb": "LB",
    "Rt": "RT",
    "Rb": "RB",
    "Select": "Select",
    "Start": "Start",
    "Home": "Home",
    "Fn": "FN",
    "M1": "M1",
    "M2": "M2",
    "M3": "M3",
    "M4": "M4",
}

# Sticks (incl. clicks) + d-pad: shapes only, no text
OVERLAY_SKIP = frozenset(
    {"JsLeft", "JsRight", "Thl", "Thr", "Up", "Right", "Down", "Left"}
)

# Longer names for tables / status (not overlay)
SS4_HOTSPOT_LABELS = {
    "JsLeft": "Left stick",
    "JsRight": "Right stick",
    "Thl": "L3",
    "Thr": "R3",
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "Up": "D-pad up",
    "Right": "D-pad right",
    "Down": "D-pad down",
    "Left": "D-pad left",
    "Lt": "LT",
    "Lb": "LB",
    "Rt": "RT",
    "Rb": "RB",
    "C": "C",
    "Z": "Z",
    "Select": "Select",
    "Start": "Start",
    "Home": "Home",
    "Fn": "FN",
    "M1": "M1",
    "M2": "M2",
    "M3": "M3",
    "M4": "M4",
}


def key_label(key_id: int, fallback: str = "") -> str:
    if 0 <= key_id < len(KEY_LABELS) and KEY_LABELS[key_id] != "—":
        return KEY_LABELS[key_id]
    return fallback or f"Button {key_id}"


def hotspot_label(ss4_name: str, key_id: int | None = None) -> str:
    if ss4_name in SS4_HOTSPOT_LABELS:
        return SS4_HOTSPOT_LABELS[ss4_name]
    if key_id is not None:
        return key_label(key_id, ss4_name)
    return ss4_name


def overlay_label(ss4_name: str) -> str | None:
    if ss4_name in OVERLAY_SKIP:
        return None
    return OVERLAY_LABELS.get(ss4_name)
