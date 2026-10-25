"""Host-side button actions (keyboard / combo / macro).

Space Station maps keyboard & macros through a Windows virtual-HID helper
(FeizVKB / flydigimapclient). On Linux the daemon owns the pad reports, so we
replay the same ideas via a second uinput keyboard device. Pad→pad remaps stay
in the onboard 3-byte key map.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from evdev import UInput, ecodes

# Onboard key slot → report button name (for suppressing / edge detect).
KEY_ID_TO_REPORT: dict[int, str] = {
    0: "hat_up",
    1: "hat_right",
    2: "hat_down",
    3: "hat_left",
    4: "a",
    5: "b",
    6: "select",
    7: "x",
    8: "y",
    9: "start",
    10: "lb",
    11: "rb",
    12: "lt",
    13: "rt",
    14: "ls",
    15: "rs",
    16: "c",
    17: "z",
    18: "m1",
    19: "m2",
    20: "m3",
    21: "m4",
    24: "guide",
    25: "fn",
    27: "guide",
}

# Common keyboard targets shown in the UI (linux KEY_* names).
KEYBOARD_CHOICES: list[tuple[str, str]] = [
    ("KEY_A", "A"),
    ("KEY_B", "B"),
    ("KEY_C", "C"),
    ("KEY_D", "D"),
    ("KEY_E", "E"),
    ("KEY_F", "F"),
    ("KEY_G", "G"),
    ("KEY_H", "H"),
    ("KEY_I", "I"),
    ("KEY_J", "J"),
    ("KEY_K", "K"),
    ("KEY_L", "L"),
    ("KEY_M", "M"),
    ("KEY_N", "N"),
    ("KEY_O", "O"),
    ("KEY_P", "P"),
    ("KEY_Q", "Q"),
    ("KEY_R", "R"),
    ("KEY_S", "S"),
    ("KEY_T", "T"),
    ("KEY_U", "U"),
    ("KEY_V", "V"),
    ("KEY_W", "W"),
    ("KEY_X", "X"),
    ("KEY_Y", "Y"),
    ("KEY_Z", "Z"),
    ("KEY_1", "1"),
    ("KEY_2", "2"),
    ("KEY_3", "3"),
    ("KEY_4", "4"),
    ("KEY_5", "5"),
    ("KEY_6", "6"),
    ("KEY_7", "7"),
    ("KEY_8", "8"),
    ("KEY_9", "9"),
    ("KEY_0", "0"),
    ("KEY_SPACE", "Space"),
    ("KEY_ENTER", "Enter"),
    ("KEY_TAB", "Tab"),
    ("KEY_ESC", "Esc"),
    ("KEY_BACKSPACE", "Backspace"),
    ("KEY_LEFTSHIFT", "Shift"),
    ("KEY_LEFTCTRL", "Ctrl"),
    ("KEY_LEFTALT", "Alt"),
    ("KEY_LEFTMETA", "Meta"),
    ("KEY_UP", "↑"),
    ("KEY_DOWN", "↓"),
    ("KEY_LEFT", "←"),
    ("KEY_RIGHT", "→"),
    ("KEY_F1", "F1"),
    ("KEY_F2", "F2"),
    ("KEY_F3", "F3"),
    ("KEY_F4", "F4"),
    ("KEY_F5", "F5"),
    ("KEY_F6", "F6"),
    ("KEY_F7", "F7"),
    ("KEY_F8", "F8"),
    ("KEY_F9", "F9"),
    ("KEY_F10", "F10"),
    ("KEY_F11", "F11"),
    ("KEY_F12", "F12"),
]

MODIFIER_KEYS = ("KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_LEFTALT", "KEY_LEFTMETA")


def default_actions_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "flydigi-vader4d" / "button_actions.json"


def _key_code(name: str) -> int | None:
    return getattr(ecodes, name, None)


def keyboard_cap() -> dict[int, list[int]]:
    codes = []
    for name, _ in KEYBOARD_CHOICES:
        code = _key_code(name)
        if code is not None:
            codes.append(code)
    # ensure modifiers present
    for name in MODIFIER_KEYS:
        code = _key_code(name)
        if code is not None and code not in codes:
            codes.append(code)
    return {ecodes.EV_KEY: sorted(set(codes))}


class ActionPlayer:
    """Applies host-side keyboard/combo/macro overlays on report edges."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_actions_path()
        self.actions: dict[str, dict[str, Any]] = {}
        self.kb: UInput | None = None
        self._pressed: dict[str, bool] = {}
        self._macro_lock = threading.Lock()
        self._macro_stop = threading.Event()
        self._macro_thread: threading.Thread | None = None
        self.load()

    def ensure_keyboard(self) -> UInput:
        if self.kb is None:
            self.kb = UInput(
                keyboard_cap(),
                name="Flydigi Vader 4 Pro Keyboard",
                vendor=0x04B4,
                product=0x2412,
                version=0x0111,
            )
        return self.kb

    def close(self) -> None:
        self._macro_stop.set()
        if self._macro_thread and self._macro_thread.is_alive():
            self._macro_thread.join(timeout=1.0)
        if self.kb is not None:
            try:
                self.kb.close()
            except OSError:
                pass
            self.kb = None

    def load(self) -> None:
        if not self.path.is_file():
            self.actions = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.actions = {
                str(k): v for k, v in (data.get("actions") or data or {}).items()
            }
        except (OSError, json.JSONDecodeError, TypeError):
            self.actions = {}

    def save(self, actions: dict[str, dict[str, Any]] | None = None) -> None:
        if actions is not None:
            self.actions = {str(k): v for k, v in actions.items() if v}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"actions": self.actions}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def overlay_report_names(self) -> set[str]:
        """Report button names that should not be forwarded as gamepad presses."""
        out: set[str] = set()
        for kid, act in self.actions.items():
            mode = (act or {}).get("mode")
            if mode in ("keyboard", "combo", "macro"):
                name = KEY_ID_TO_REPORT.get(int(kid))
                if name:
                    out.add(name)
        return out

    def on_report(
        self,
        buttons: dict[str, bool],
        *,
        hat_x: int,
        hat_y: int,
        lt: int = 0,
        rt: int = 0,
    ) -> None:
        """Edge-detect physical buttons and fire overlays."""
        state = dict(buttons)
        state["hat_up"] = hat_y < 0
        state["hat_down"] = hat_y > 0
        state["hat_left"] = hat_x < 0
        state["hat_right"] = hat_x > 0
        state["lt"] = lt > 32
        state["rt"] = rt > 32

        for kid_s, act in list(self.actions.items()):
            mode = (act or {}).get("mode")
            if mode not in ("keyboard", "combo", "macro"):
                continue
            report = KEY_ID_TO_REPORT.get(int(kid_s))
            if not report:
                continue
            down = bool(state.get(report))
            was = self._pressed.get(report, False)
            if down == was:
                continue
            self._pressed[report] = down
            if mode == "macro":
                if down:
                    self._start_macro(act)
                elif (act or {}).get("trigger") == "hold":
                    self._macro_stop.set()
            else:
                keys = list((act or {}).get("keys") or [])
                if mode == "keyboard" and keys or mode == "combo" and keys:
                    self._tap_chord(keys, down)

    def _tap_chord(self, key_names: list[str], down: bool) -> None:
        kb = self.ensure_keyboard()
        codes = [c for n in key_names if (c := _key_code(n)) is not None]
        if not codes:
            return
        if down:
            for c in codes:
                kb.write(ecodes.EV_KEY, c, 1)
        else:
            for c in reversed(codes):
                kb.write(ecodes.EV_KEY, c, 0)
        kb.syn()

    def _start_macro(self, act: dict[str, Any]) -> None:
        self._macro_stop.set()
        if self._macro_thread and self._macro_thread.is_alive():
            self._macro_thread.join(timeout=0.5)
        self._macro_stop.clear()
        steps = list(act.get("steps") or [])
        trigger = act.get("trigger") or "once"
        self._macro_thread = threading.Thread(
            target=self._run_macro,
            args=(steps, trigger),
            name="flydigi-macro",
            daemon=True,
        )
        self._macro_thread.start()

    def _run_macro(self, steps: list[dict[str, Any]], trigger: str) -> None:
        with self._macro_lock:
            loop = trigger in ("hold", "toggle")
            while not self._macro_stop.is_set():
                for step in steps:
                    if self._macro_stop.is_set():
                        return
                    keys = list(step.get("keys") or [])
                    hold_ms = max(0, int(step.get("hold_ms", 50)))
                    delay_ms = max(0, int(step.get("delay_ms", 50)))
                    self._tap_chord(keys, True)
                    if hold_ms:
                        self._macro_stop.wait(hold_ms / 1000.0)
                    self._tap_chord(keys, False)
                    if delay_ms:
                        self._macro_stop.wait(delay_ms / 1000.0)
                if not loop:
                    return
                # hold mode: keep looping until stop; tiny pause between cycles
                self._macro_stop.wait(0.01)
