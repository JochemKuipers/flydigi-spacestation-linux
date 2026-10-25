"""Buttons page — pad remap, keyboard, combo, macro, turbo."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flydigi.button_actions import KEYBOARD_CHOICES, MODIFIER_KEYS
from flydigi.gamepad_config import KEY_NAMES

from .labels import KEY_LABELS, hotspot_label
from .widgets import LivePadView

Rpc = Callable[..., dict]

REMAP_KEYS: list[int] = [
    i
    for i, name in enumerate(KEY_NAMES)
    if name != "?" and i < len(KEY_LABELS) and KEY_LABELS[i] != "—"
]

# Mapping modes: Click / Turbo / Keyboard / Combo / Macro
MODE_CONTROLLER = "controller"
MODE_TURBO = "turbo"
MODE_KEYBOARD = "keyboard"
MODE_COMBO = "combo"
MODE_MACRO = "macro"


def _label(kid: int) -> str:
    if 0 <= kid < len(KEY_LABELS) and KEY_LABELS[kid] != "—":
        return KEY_LABELS[kid]
    if 0 <= kid < len(KEY_NAMES):
        return KEY_NAMES[kid]
    return f"key_{kid}"


def _kb_label(code: str) -> str:
    for name, lab in KEYBOARD_CHOICES:
        if name == code:
            return lab
    return code.replace("KEY_", "")


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def _qt_to_key_name(key: int, modifiers: Qt.KeyboardModifier) -> list[str]:
    """Map a Qt key event to linux KEY_* names (best-effort)."""
    names: list[str] = []
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        names.append("KEY_LEFTCTRL")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        names.append("KEY_LEFTSHIFT")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        names.append("KEY_LEFTALT")
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        names.append("KEY_LEFTMETA")
    table = {
        Qt.Key.Key_Space: "KEY_SPACE",
        Qt.Key.Key_Return: "KEY_ENTER",
        Qt.Key.Key_Enter: "KEY_ENTER",
        Qt.Key.Key_Escape: "KEY_ESC",
        Qt.Key.Key_Tab: "KEY_TAB",
        Qt.Key.Key_Backspace: "KEY_BACKSPACE",
        Qt.Key.Key_Up: "KEY_UP",
        Qt.Key.Key_Down: "KEY_DOWN",
        Qt.Key.Key_Left: "KEY_LEFT",
        Qt.Key.Key_Right: "KEY_RIGHT",
    }
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        names.append(f"KEY_F{key - Qt.Key.Key_F1 + 1}")
        return names
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        names.append(f"KEY_{chr(ord('A') + (key - Qt.Key.Key_A))}")
        return names
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        names.append(f"KEY_{key - Qt.Key.Key_0}")
        return names
    if key in table:
        names.append(table[key])
    return names


class KeyCapture(QLineEdit):
    """Click then press a keyboard key to bind."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click, then press a key…")
        self._codes: list[str] = []
        self.changed_cb: Callable[[], None] | None = None

    def set_codes(self, codes: list[str]) -> None:
        self._codes = list(codes)
        self.setText(
            " + ".join(_kb_label(c) for c in self._codes) if self._codes else ""
        )

    def codes(self) -> list[str]:
        return list(self._codes)

    def keyPressEvent(self, event) -> None:
        if event.key() in (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            return
        codes = _qt_to_key_name(event.key(), event.modifiers())
        # For pure keyboard mode we want the primary key only (drop mods unless combo)
        if codes:
            self.set_codes(codes)
            if self.changed_cb:
                self.changed_cb()
        event.accept()


class ButtonsPage(QWidget):
    """Click a control → pick Click / Keyboard / Combo / Macro / Turbo."""

    def __init__(self, rpc: Rpc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rpc = rpc
        self._transport = "unknown"
        self._keys: dict[int, dict[str, Any]] = {}
        self._actions: dict[str, dict[str, Any]] = {}
        self._selected: int | None = None
        self._chip_btns: dict[int, QPushButton] = {}
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("Buttons")
        title.setObjectName("PageTitle")
        lead = QLabel(
            "Pick a control from the list or the pad, then choose what it should send — "
            "another button, a keyboard key, a combo, a short macro, or turbo."
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(lead)

        body = QHBoxLayout()
        body.setSpacing(12)

        # —— All controls (primary) ——
        list_card = _card()
        ll = QVBoxLayout(list_card)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(6)
        lt = QLabel("All controls")
        lt.setObjectName("CardTitle")
        ll.addWidget(lt)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chip_host = QWidget()
        chip_col = QVBoxLayout(chip_host)
        chip_col.setContentsMargins(0, 0, 0, 0)
        chip_col.setSpacing(4)
        self._chip_btns = {}
        for kid in REMAP_KEYS:
            b = QPushButton(_label(kid))
            b.setObjectName("KeyChip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=kid: self.select_key(k))
            chip_col.addWidget(b)
            self._chip_btns[kid] = b
        chip_col.addStretch()
        scroll.setWidget(chip_host)
        self._chip_scroll = scroll
        ll.addWidget(scroll, stretch=1)
        # Was 3:2 (~60% list); ~20% narrower list → ~48% / 52%.
        body.addWidget(list_card, stretch=12)

        # —— Pad + mapping editor ——
        right = QVBoxLayout()
        right.setSpacing(12)

        pad_card = _card()
        pl = QVBoxLayout(pad_card)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(4)
        self.pad = LivePadView(show_led=False)
        self.pad.setMinimumSize(320, 200)
        self.pad.setMaximumHeight(330)
        self.pad.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.pad.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pad.hotspot_clicked.connect(self._on_hotspot)
        pl.addWidget(self.pad)
        hint = QLabel("Click a control on the pad to select it.")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(hint)
        right.addWidget(pad_card)

        insp = _card()
        il = QVBoxLayout(insp)
        il.setContentsMargins(14, 14, 14, 14)
        il.setSpacing(8)
        it = QLabel("Mapping")
        it.setObjectName("CardTitle")
        il.addWidget(it)

        self.sel_label = QLabel("No button selected")
        self.sel_label.setObjectName("CardTitle")
        il.addWidget(self.sel_label)

        self.mode = QComboBox()
        self.mode.addItem("Click (pad button)", MODE_CONTROLLER)
        self.mode.addItem("Keyboard", MODE_KEYBOARD)
        self.mode.addItem("Key combo", MODE_COMBO)
        self.mode.addItem("Macro", MODE_MACRO)
        self.mode.addItem("Turbo (rapid fire)", MODE_TURBO)
        self.mode.setEnabled(False)
        self.mode.currentIndexChanged.connect(self._on_mode_changed)
        il.addWidget(QLabel("Type"))
        il.addWidget(self.mode)

        self.mode_stack = QStackedWidget()
        # 0 controller
        w0 = QWidget()
        l0 = QVBoxLayout(w0)
        l0.setContentsMargins(0, 0, 0, 0)
        self.map_to = QComboBox()
        self.map_to.addItem("Default (no remap)", 255)
        for kid in REMAP_KEYS:
            self.map_to.addItem(_label(kid), kid)
        self.map_to.currentIndexChanged.connect(self._on_editor_changed)
        l0.addWidget(QLabel("Sends as"))
        l0.addWidget(self.map_to)
        self.mode_stack.addWidget(w0)

        # 1 keyboard
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(0, 0, 0, 0)
        self.kb_capture = KeyCapture()
        self.kb_capture.changed_cb = self._on_editor_changed
        self.kb_pick = QComboBox()
        self.kb_pick.addItem("— choose —", "")
        for code, lab in KEYBOARD_CHOICES:
            if code in MODIFIER_KEYS:
                continue
            self.kb_pick.addItem(lab, code)
        self.kb_pick.currentIndexChanged.connect(self._on_kb_pick)
        l1.addWidget(QLabel("Keyboard key"))
        l1.addWidget(self.kb_capture)
        l1.addWidget(self.kb_pick)
        self.mode_stack.addWidget(w1)

        # 2 combo
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        l2.setContentsMargins(0, 0, 0, 0)
        self.mod_ctrl = QCheckBox("Ctrl")
        self.mod_shift = QCheckBox("Shift")
        self.mod_alt = QCheckBox("Alt")
        self.mod_meta = QCheckBox("Meta")
        for m in (self.mod_ctrl, self.mod_shift, self.mod_alt, self.mod_meta):
            m.toggled.connect(self._on_editor_changed)
        mods = QHBoxLayout()
        for m in (self.mod_ctrl, self.mod_shift, self.mod_alt, self.mod_meta):
            mods.addWidget(m)
        l2.addLayout(mods)
        self.combo_key = QComboBox()
        self.combo_key.addItem("— key —", "")
        for code, lab in KEYBOARD_CHOICES:
            if code in MODIFIER_KEYS:
                continue
            self.combo_key.addItem(lab, code)
        self.combo_key.currentIndexChanged.connect(self._on_editor_changed)
        l2.addWidget(QLabel("With key"))
        l2.addWidget(self.combo_key)
        self.mode_stack.addWidget(w2)

        # 3 macro
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(0, 0, 0, 0)
        self.macro_trigger = QComboBox()
        self.macro_trigger.addItem("Press once", "once")
        self.macro_trigger.addItem("Hold to repeat", "hold")
        self.macro_trigger.currentIndexChanged.connect(self._on_editor_changed)
        l3.addWidget(QLabel("Trigger"))
        l3.addWidget(self.macro_trigger)
        self.macro_steps = QLineEdit()
        self.macro_steps.setPlaceholderText(
            "Keys separated by commas, e.g. A, B, Enter"
        )
        self.macro_steps.textChanged.connect(self._on_editor_changed)
        l3.addWidget(QLabel("Sequence"))
        l3.addWidget(self.macro_steps)
        tip = QLabel(
            "Each key is pressed briefly in order when you trigger the macro."
        )
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        l3.addWidget(tip)
        self.mode_stack.addWidget(w3)

        # 4 turbo (same as controller target + turbo flags)
        w4 = QWidget()
        l4 = QVBoxLayout(w4)
        l4.setContentsMargins(0, 0, 0, 0)
        self.turbo_map = QComboBox()
        self.turbo_map.addItem("Same button", -1)
        for kid in REMAP_KEYS:
            self.turbo_map.addItem(_label(kid), kid)
        self.turbo_map.currentIndexChanged.connect(self._on_editor_changed)
        self.turbo_speed = QSpinBox()
        self.turbo_speed.setRange(1, 255)
        self.turbo_speed.setValue(10)
        self.turbo_speed.valueChanged.connect(self._on_editor_changed)
        l4.addWidget(QLabel("Turbo target"))
        l4.addWidget(self.turbo_map)
        row = QHBoxLayout()
        row.addWidget(QLabel("Fire rate"))
        row.addWidget(self.turbo_speed, stretch=1)
        l4.addLayout(row)
        self.mode_stack.addWidget(w4)

        il.addWidget(self.mode_stack)

        self.changed_note = QLabel("")
        self.changed_note.setObjectName("Muted")
        self.changed_note.setWordWrap(True)
        il.addWidget(self.changed_note)

        reset = QPushButton("Reset this button")
        reset.clicked.connect(self._reset_selected)
        il.addWidget(reset)
        right.addWidget(insp, stretch=1)

        actions = _card()
        al = QVBoxLayout(actions)
        al.setContentsMargins(12, 12, 12, 12)
        al.setSpacing(8)
        self.status = QLabel(
            "Open this page with the pad on USB / dongle to load mappings."
        )
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        al.addWidget(self.status)
        brow = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_from_pad)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.save_to_pad)
        brow.addWidget(reload_btn)
        brow.addWidget(save_btn)
        al.addLayout(brow)
        right.addWidget(actions)

        body.addLayout(right, stretch=13)
        root.addLayout(body, stretch=1)

    def set_transport(self, transport: str) -> None:
        self._transport = transport

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._transport != "bluetooth" and not self._keys:
            QTimer.singleShot(0, self.reload_from_pad)

    def on_report(self, rep: dict) -> None:
        self.pad.set_report(rep)

    def _usb_ok(self) -> bool:
        if self._transport == "bluetooth":
            QMessageBox.information(
                self,
                "Cable or dongle needed",
                "Button remaps need USB or the 2.4 GHz dongle.",
            )
            return False
        return True

    @Slot()
    def reload_from_pad(self) -> None:
        if not self._usb_ok():
            return
        resp = self._rpc("config_get")
        if not resp.get("ok"):
            return
        self._keys = {}
        for k in resp["config"].get("keys") or []:
            kid = int(k["id"])
            self._keys[kid] = {
                "id": kid,
                "map_id": int(k.get("map_id", 255)),
                "turbo_type": int(k.get("turbo_type", 0)),
                "turbo": int(k.get("turbo", 0)),
            }
        for kid in REMAP_KEYS:
            self._keys.setdefault(
                kid, {"id": kid, "map_id": 255, "turbo_type": 0, "turbo": 0}
            )
        acts = self._rpc("actions_get")
        self._actions = dict(acts.get("actions") or {}) if acts.get("ok") else {}
        self._refresh_chips()
        if self._selected is not None:
            self.select_key(self._selected)
        self.status.setText("Loaded pad map + keyboard/macro actions.")

    @Slot()
    def save_to_pad(self) -> None:
        if not self._usb_ok():
            return
        self.status.setText("Saving…")
        # Onboard: controller + turbo only; clear map for keys using host actions.
        payload = []
        for kid in sorted(set(REMAP_KEYS) | set(self._keys)):
            act = self._actions.get(str(kid)) or {}
            mode = act.get("mode")
            row = self._keys.get(kid) or {
                "id": kid,
                "map_id": 255,
                "turbo_type": 0,
                "turbo": 0,
            }
            if mode in (MODE_KEYBOARD, MODE_COMBO, MODE_MACRO):
                payload.append({"id": kid, "map_id": 255, "turbo_type": 0, "turbo": 0})
            else:
                payload.append(
                    {
                        "id": kid,
                        "map_id": int(row.get("map_id", 255)),
                        "turbo_type": int(row.get("turbo_type", 0)),
                        "turbo": int(row.get("turbo", 0)),
                    }
                )
        ok_keys = self._rpc("config_set_keys", keys=payload).get("ok")
        ok_act = self._rpc("actions_set", actions=self._actions).get("ok")
        if ok_keys:
            for item in payload:
                kid = int(item["id"])
                self._keys[kid] = {
                    "id": kid,
                    "map_id": int(item["map_id"]),
                    "turbo_type": int(item["turbo_type"]),
                    "turbo": int(item["turbo"]),
                }
        if ok_act:
            # Keep local actions; daemon already has them.
            pass
        self._refresh_chips()
        if self._selected is not None:
            self.select_key(self._selected)
        if ok_keys and ok_act:
            self.status.setText("Saved pad map + keyboard/macro actions.")
        elif ok_keys:
            self.status.setText("Pad map saved; keyboard/macro save failed.")
        elif ok_act:
            self.status.setText("Keyboard/macro saved; pad map write failed.")
        else:
            self.status.setText("Save failed.")

    @Slot(int, str)
    def _on_hotspot(self, key_id: int, ss4_name: str) -> None:
        if key_id < 0 or key_id >= 32:
            self.status.setText(f"{hotspot_label(ss4_name, None)}: not remappable here")
            return
        if key_id not in REMAP_KEYS:
            self.status.setText(f"{hotspot_label(ss4_name, key_id)}: unused slot")
            return
        self.select_key(key_id)

    def select_key(self, key_id: int) -> None:
        self._selected = key_id
        self.sel_label.setText(_label(key_id))
        row = self._keys.setdefault(
            key_id, {"id": key_id, "map_id": 255, "turbo_type": 0, "turbo": 0}
        )
        act = self._actions.get(str(key_id)) or {}
        mode = act.get("mode")
        if not mode:
            if int(row.get("turbo_type", 0)) != 0:
                mode = MODE_TURBO
            else:
                mode = MODE_CONTROLLER
        self._loading = True
        self.mode.setEnabled(True)
        idx = self.mode.findData(mode)
        self.mode.setCurrentIndex(max(0, idx))
        self._fill_mode_widgets(mode, row, act)
        self._loading = False
        self._sync_stack()
        self._update_changed_note()
        for kid, btn in self._chip_btns.items():
            btn.setChecked(kid == key_id)
        chip = self._chip_btns.get(key_id)
        if chip is not None:
            self._chip_scroll.ensureWidgetVisible(chip)
        self.pad.set_selected_key(key_id)

    def _fill_mode_widgets(self, mode: str, row: dict, act: dict) -> None:
        map_id = int(row.get("map_id", 255))
        if map_id in (255, self._selected):
            map_id = 255
        self.map_to.setCurrentIndex(max(0, self.map_to.findData(map_id)))
        keys = list(act.get("keys") or [])
        self.kb_capture.set_codes(keys[:1] if mode == MODE_KEYBOARD else keys)
        if keys:
            self.kb_pick.setCurrentIndex(max(0, self.kb_pick.findData(keys[-1])))
        self.mod_ctrl.setChecked("KEY_LEFTCTRL" in keys)
        self.mod_shift.setChecked("KEY_LEFTSHIFT" in keys)
        self.mod_alt.setChecked("KEY_LEFTALT" in keys)
        self.mod_meta.setChecked("KEY_LEFTMETA" in keys)
        primary = next((k for k in keys if k not in MODIFIER_KEYS), "")
        self.combo_key.setCurrentIndex(max(0, self.combo_key.findData(primary)))
        steps = act.get("steps") or []
        names = []
        for step in steps:
            sk = step.get("keys") or []
            if sk:
                names.append(_kb_label(sk[0]))
        self.macro_steps.setText(", ".join(names))
        trig = act.get("trigger") or "once"
        self.macro_trigger.setCurrentIndex(max(0, self.macro_trigger.findData(trig)))
        tmap = map_id if map_id != 255 else -1
        self.turbo_map.setCurrentIndex(max(0, self.turbo_map.findData(tmap)))
        self.turbo_speed.setValue(max(1, int(row.get("turbo", 0)) or 10))

    def _sync_stack(self) -> None:
        mode = self.mode.currentData()
        mapping = {
            MODE_CONTROLLER: 0,
            MODE_KEYBOARD: 1,
            MODE_COMBO: 2,
            MODE_MACRO: 3,
            MODE_TURBO: 4,
        }
        self.mode_stack.setCurrentIndex(mapping.get(mode, 0))

    def _on_mode_changed(self) -> None:
        self._sync_stack()
        if not self._loading:
            self._on_editor_changed()

    def _on_kb_pick(self) -> None:
        if self._loading:
            return
        code = self.kb_pick.currentData()
        if code:
            self.kb_capture.set_codes([code])
            self._on_editor_changed()

    def _on_editor_changed(self) -> None:
        if self._loading or self._selected is None:
            return
        kid = self._selected
        mode = self.mode.currentData()
        row = {"id": kid, "map_id": 255, "turbo_type": 0, "turbo": 0}
        act: dict[str, Any] | None = None

        if mode == MODE_CONTROLLER:
            row["map_id"] = int(self.map_to.currentData())
            self._actions.pop(str(kid), None)
        elif mode == MODE_TURBO:
            tmap = self.turbo_map.currentData()
            row["map_id"] = kid if tmap == -1 else int(tmap)
            row["turbo_type"] = 1
            row["turbo"] = self.turbo_speed.value()
            self._actions.pop(str(kid), None)
        elif mode == MODE_KEYBOARD:
            codes = self.kb_capture.codes()
            # drop modifiers for pure keyboard — one key
            codes = [c for c in codes if c not in MODIFIER_KEYS] or codes
            act = {"mode": MODE_KEYBOARD, "keys": codes[:1]}
        elif mode == MODE_COMBO:
            codes = []
            if self.mod_ctrl.isChecked():
                codes.append("KEY_LEFTCTRL")
            if self.mod_shift.isChecked():
                codes.append("KEY_LEFTSHIFT")
            if self.mod_alt.isChecked():
                codes.append("KEY_LEFTALT")
            if self.mod_meta.isChecked():
                codes.append("KEY_LEFTMETA")
            primary = self.combo_key.currentData()
            if primary:
                codes.append(primary)
            act = {"mode": MODE_COMBO, "keys": codes}
        elif mode == MODE_MACRO:
            parts = [p.strip() for p in self.macro_steps.text().split(",") if p.strip()]
            steps = []
            for part in parts:
                code = self._resolve_key_token(part)
                if code:
                    steps.append({"keys": [code], "hold_ms": 50, "delay_ms": 80})
            act = {
                "mode": MODE_MACRO,
                "trigger": self.macro_trigger.currentData(),
                "steps": steps,
            }

        self._keys[kid] = row
        if act is not None:
            self._actions[str(kid)] = act
        self._update_changed_note()
        self._refresh_chips()
        self.status.setText("Unsaved changes — Save when ready.")

    def _resolve_key_token(self, token: str) -> str | None:
        t = token.strip()
        upper = t.upper()
        if upper.startswith("KEY_"):
            return upper
        for code, lab in KEYBOARD_CHOICES:
            if lab.upper() == upper or code.replace("KEY_", "") == upper:
                return code
        # single letter/digit
        if len(t) == 1 and t.isalpha():
            return f"KEY_{t.upper()}"
        if len(t) == 1 and t.isdigit():
            return f"KEY_{t}"
        return None

    def _reset_selected(self) -> None:
        if self._selected is None:
            return
        kid = self._selected
        self._keys[kid] = {"id": kid, "map_id": 255, "turbo_type": 0, "turbo": 0}
        self._actions.pop(str(kid), None)
        self.select_key(kid)
        self.status.setText("Unsaved changes — Save when ready.")

    def _update_changed_note(self) -> None:
        if self._selected is None:
            self.changed_note.setText("")
            return
        kid = self._selected
        row = self._keys.get(kid) or {}
        act = self._actions.get(str(kid)) or {}
        mode = act.get("mode")
        if mode == MODE_KEYBOARD:
            keys = act.get("keys") or []
            self.changed_note.setText(
                f"Keyboard → {' + '.join(_kb_label(k) for k in keys)}"
                if keys
                else "Keyboard (no key)."
            )
        elif mode == MODE_COMBO:
            keys = act.get("keys") or []
            self.changed_note.setText(
                f"Combo → {' + '.join(_kb_label(k) for k in keys)}"
                if keys
                else "Combo (incomplete)."
            )
        elif mode == MODE_MACRO:
            n = len(act.get("steps") or [])
            self.changed_note.setText(
                f"Macro · {n} step(s) · {act.get('trigger', 'once')}"
            )
        elif int(row.get("turbo_type", 0)) != 0:
            mid = int(row.get("map_id", kid))
            tgt = "same" if mid in (255, kid) else _label(mid)
            self.changed_note.setText(
                f"Turbo → {tgt} ×{int(row.get('turbo', 0) or 10)}"
            )
        else:
            mid = int(row.get("map_id", 255))
            if mid not in (255, kid):
                self.changed_note.setText(f"Remapped → {_label(mid)}")
            else:
                self.changed_note.setText("Default (no remap).")

    def _refresh_chips(self) -> None:
        for kid, btn in self._chip_btns.items():
            row = self._keys.get(kid) or {"map_id": 255, "turbo_type": 0, "turbo": 0}
            act = self._actions.get(str(kid)) or {}
            name = _label(kid)
            mode = act.get("mode")
            if mode == MODE_KEYBOARD:
                keys = act.get("keys") or []
                tag = f"{name} → ⌨ {_kb_label(keys[0])}" if keys else f"{name} → ⌨"
            elif mode == MODE_COMBO:
                keys = act.get("keys") or []
                tag = (
                    f"{name} → {'+'.join(_kb_label(k) for k in keys)}"
                    if keys
                    else f"{name} → combo"
                )
            elif mode == MODE_MACRO:
                tag = f"{name} → macro"
            else:
                mid = int(row.get("map_id", 255))
                tag = name
                if mid not in (255, kid):
                    tag = f"{name} → {_label(mid)}"
                if int(row.get("turbo_type", 0)) != 0:
                    tag += " · turbo"
            btn.setText(tag)
