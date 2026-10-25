"""Buttons page — pad-first remap + turbo (SS4-style)."""

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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from flydigi.gamepad_config import KEY_NAMES

from .labels import KEY_LABELS, hotspot_label
from .widgets import LivePadView

Rpc = Callable[..., dict]

# Remappable slots that aren't "?" placeholders (aligns with SS4 F4 hotspots < 32).
REMAP_KEYS: list[int] = [
    i
    for i, name in enumerate(KEY_NAMES)
    if name != "?" and i < len(KEY_LABELS) and KEY_LABELS[i] != "—"
]


def _label(kid: int) -> str:
    if 0 <= kid < len(KEY_LABELS) and KEY_LABELS[kid] != "—":
        return KEY_LABELS[kid]
    if 0 <= kid < len(KEY_NAMES):
        return KEY_NAMES[kid]
    return f"key_{kid}"


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


class ButtonsPage(QWidget):
    """Click a control on the pad → edit map / turbo in the inspector."""

    def __init__(self, rpc: Rpc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rpc = rpc
        self._transport = "unknown"
        self._keys: dict[int, dict[str, Any]] = {}
        self._selected: int | None = None
        self._chip_btns: dict[int, QPushButton] = {}
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        title = QLabel("Buttons")
        title.setObjectName("PageTitle")
        lead = QLabel(
            "Select a button on the pad (or the list), choose what it should send, "
            "and optionally turn on rapid fire. Save writes the onboard map Space Station uses."
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(lead)

        body = QHBoxLayout()
        body.setSpacing(14)

        pad_card = _card()
        pl = QVBoxLayout(pad_card)
        pl.setContentsMargins(12, 12, 12, 12)
        self.pad = LivePadView()
        self.pad.hotspot_clicked.connect(self._on_hotspot)
        pl.addWidget(self.pad, stretch=1)
        hint = QLabel("Click a labeled control to edit it.")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(hint)
        body.addWidget(pad_card, stretch=3)

        side = QVBoxLayout()
        side.setSpacing(12)

        insp = _card()
        il = QVBoxLayout(insp)
        il.setContentsMargins(16, 16, 16, 16)
        il.setSpacing(10)
        it = QLabel("Mapping")
        it.setObjectName("CardTitle")
        il.addWidget(it)

        self.sel_label = QLabel("No button selected")
        self.sel_label.setObjectName("CardTitle")
        il.addWidget(self.sel_label)

        il.addWidget(QLabel("Sends as"))
        self.map_to = QComboBox()
        self.map_to.addItem("Default (no remap)", 255)
        for kid in REMAP_KEYS:
            self.map_to.addItem(_label(kid), kid)
        self.map_to.setEnabled(False)
        self.map_to.currentIndexChanged.connect(self._on_editor_changed)
        il.addWidget(self.map_to)

        self.turbo = QCheckBox("Rapid fire")
        self.turbo.setEnabled(False)
        self.turbo.toggled.connect(self._on_editor_changed)
        il.addWidget(self.turbo)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Fire rate"))
        self.turbo_speed = QSpinBox()
        self.turbo_speed.setRange(1, 255)
        self.turbo_speed.setValue(10)
        self.turbo_speed.setEnabled(False)
        self.turbo_speed.valueChanged.connect(self._on_editor_changed)
        speed_row.addWidget(self.turbo_speed, stretch=1)
        il.addLayout(speed_row)

        self.changed_note = QLabel("")
        self.changed_note.setObjectName("Muted")
        self.changed_note.setWordWrap(True)
        il.addWidget(self.changed_note)

        reset = QPushButton("Reset this button")
        reset.clicked.connect(self._reset_selected)
        il.addWidget(reset)
        side.addWidget(insp)

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
        ll.addWidget(scroll, stretch=1)
        side.addWidget(list_card, stretch=1)

        actions = _card()
        al = QVBoxLayout(actions)
        al.setContentsMargins(16, 16, 16, 16)
        al.setSpacing(8)
        self.status = QLabel(
            "Open this page with the pad on USB / dongle to load mappings."
        )
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        al.addWidget(self.status)
        brow = QHBoxLayout()
        reload_btn = QPushButton("Reload from pad")
        reload_btn.clicked.connect(self.reload_from_pad)
        save_btn = QPushButton("Save to pad")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.save_to_pad)
        brow.addWidget(reload_btn)
        brow.addWidget(save_btn)
        al.addLayout(brow)
        side.addWidget(actions)

        body.addLayout(side, stretch=2)
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
        self._refresh_chips()
        if self._selected is not None:
            self.select_key(self._selected)
        self.status.setText("Loaded mappings from the controller.")

    @Slot()
    def save_to_pad(self) -> None:
        if not self._usb_ok():
            return
        payload = [
            {
                "id": kid,
                "map_id": int(row["map_id"]),
                "turbo_type": int(row.get("turbo_type", 0)),
                "turbo": int(row.get("turbo", 0)),
            }
            for kid, row in sorted(self._keys.items())
        ]
        self.status.setText("Saving…")
        if self._rpc("config_set_keys", keys=payload).get("ok"):
            self.status.setText("Saved to the pad.")
        else:
            self.status.setText("Save failed — mappings were not written.")

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
        map_id = int(row.get("map_id", 255))
        if map_id in (255, key_id):
            map_id = 255
        self._loading = True
        self.map_to.setEnabled(True)
        self.turbo.setEnabled(True)
        idx = self.map_to.findData(map_id)
        self.map_to.setCurrentIndex(max(0, idx))
        turbo_on = int(row.get("turbo_type", 0)) != 0
        self.turbo.setChecked(turbo_on)
        self.turbo_speed.setEnabled(turbo_on)
        self.turbo_speed.setValue(max(1, int(row.get("turbo", 0)) or 10))
        self._loading = False
        self._update_changed_note()
        for kid, btn in self._chip_btns.items():
            btn.setChecked(kid == key_id)
        self.pad.set_selected_key(key_id)

    def _on_editor_changed(self) -> None:
        if self._loading or self._selected is None:
            return
        map_id = int(self.map_to.currentData())
        turbo_on = self.turbo.isChecked()
        self.turbo_speed.setEnabled(turbo_on)
        self._keys[self._selected] = {
            "id": self._selected,
            "map_id": map_id,
            "turbo_type": 1 if turbo_on else 0,
            "turbo": self.turbo_speed.value() if turbo_on else 0,
        }
        self._update_changed_note()
        self._refresh_chips()
        self.status.setText("Unsaved changes — Save to pad when ready.")

    def _reset_selected(self) -> None:
        if self._selected is None:
            return
        kid = self._selected
        self._keys[kid] = {"id": kid, "map_id": 255, "turbo_type": 0, "turbo": 0}
        self.select_key(kid)
        self.status.setText("Unsaved changes — Save to pad when ready.")

    def _update_changed_note(self) -> None:
        if self._selected is None:
            self.changed_note.setText("")
            return
        row = self._keys[self._selected]
        mid = int(row["map_id"])
        bits: list[str] = []
        if mid not in (255, self._selected):
            bits.append(f"remapped → {_label(mid)}")
        if int(row.get("turbo_type", 0)) != 0:
            bits.append(f"turbo ×{int(row.get('turbo', 0) or 10)}")
        self.changed_note.setText(
            " · ".join(bits) if bits else "Default (no remap, no turbo)."
        )

    def _refresh_chips(self) -> None:
        for kid, btn in self._chip_btns.items():
            row = self._keys.get(kid) or {"map_id": 255, "turbo_type": 0, "turbo": 0}
            name = _label(kid)
            mid = int(row.get("map_id", 255))
            tag = name
            if mid not in (255, kid):
                tag = f"{name} → {_label(mid)}"
            if int(row.get("turbo_type", 0)) != 0:
                tag += " · turbo"
            btn.setText(tag)
