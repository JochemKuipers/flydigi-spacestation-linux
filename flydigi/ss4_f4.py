"""Space Station 4.2.2.3 F4 overlay helpers (ported assets, no Electron)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Bundled under the UI package; fall back relative to this file for tests.
_UI_SS4 = Path(__file__).resolve().parent.parent / "app" / "ui" / "assets" / "ss4"

# SS4 hotspot name → report / KEY_NAMES style
SS4_TO_REPORT: dict[str, str] = {
    "JsLeft": "ls",
    "JsRight": "rs",
    "Thl": "ls",  # stick click shares stick center; highlight via ls/rs buttons
    "Thr": "rs",
    "A": "a",
    "B": "b",
    "X": "x",
    "Y": "y",
    "Up": "hat_up",
    "Right": "hat_right",
    "Down": "hat_down",
    "Left": "hat_left",
    "Lt": "lt",
    "Lb": "lb",
    "Rt": "rt",
    "Rb": "rb",
    "C": "c",
    "Z": "z",
    "Select": "select",
    "Start": "start",
    "Home": "guide",
    "Fn": "fn",
    "M1": "m1",
    "M2": "m2",
    "M3": "m3",
    "M4": "m4",
}

# Onboard key-map slot index (0..31) ↔ SS4 ControllerKey id when id < 32
# Joysticks use 240/241 in SS4 UI only — not in the 32-slot key blob.


@lru_cache(maxsize=1)
def load_device_config() -> dict[str, Any]:
    path = _UI_SS4 / "device_config_f4.json"
    if not path.is_file():
        return {
            "viewBox": {"width": 508, "height": 421},
            "hotspots": [],
            "led_path": [],
            "wireframe": "device_wireframe_f4.svg",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if "led_path" not in data:
        # Approximate V in viewBox space (from community pad_layout scaled 1000×708 → 508×421)
        data["led_path"] = [
            [193.0, 46.0],
            [255.0, 103.0],
            [316.0, 44.0],
        ]
    data.setdefault("wireframe", "device_wireframe_f4.svg")
    return data


def assets_dir() -> Path:
    return _UI_SS4


def hotspot_by_name(name: str) -> dict[str, Any] | None:
    for h in load_device_config().get("hotspots") or []:
        if h.get("name") == name:
            return h
    return None


def ss4_name_for_key_id(key_id: int) -> str | None:
    for h in load_device_config().get("hotspots") or []:
        hid = int(h.get("id", -1))
        if hid == key_id:
            return str(h.get("name"))
    return None


def report_name(ss4_name: str) -> str | None:
    return SS4_TO_REPORT.get(ss4_name)
