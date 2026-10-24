"""Load calibrated BT DInput button map (from scripts/bt-calibrate-buttons.py)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_MAP_PATHS = (
    Path(__file__).resolve().parent / "bt_button_map.json",
    Path(__file__).resolve().parents[1] / "captures" / "bt-button-map.json",
)


@lru_cache(maxsize=1)
def load_bt_map() -> dict:
    for path in _MAP_PATHS:
        if path.is_file():
            data = json.loads(path.read_text())
            data["_path"] = str(path)
            return data
    return {"derived": {}, "_path": None}


def btn_names_by_bit() -> list[str | None]:
    """12 gamepad button bit → name (None = ignore)."""
    derived = load_bt_map().get("derived") or {}
    bit_map: dict[str, int] = derived.get("btn_bit") or {}
    out: list[str | None] = [None] * 12
    for name, bit in bit_map.items():
        if name in ("lt", "rt"):
            # Digital trigger clicks — analog axes carry LT/RT intensity.
            continue
        if 0 <= int(bit) < 12:
            out[int(bit)] = name
    return out


def cons_names_by_bit() -> dict[int, str]:
    derived = load_bt_map().get("derived") or {}
    return {int(b): n for n, b in (derived.get("cons_bit") or {}).items()}


def key_name_map() -> dict[str, str]:
    """Linux KEY_/BTN_ name → our control name."""
    derived = load_bt_map().get("derived") or {}
    raw = dict(derived.get("key_map") or {})
    # Drop digital trigger clicks from button semantics.
    raw.pop("BTN_TL2", None)
    raw.pop("BTN_TR2", None)
    return raw
