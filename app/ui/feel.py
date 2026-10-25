"""Feel page — stick/trigger curves + motors (SS4-style)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

Rpc = Callable[..., dict]


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


class CurvePreview(QWidget):
    """Response curve: physical input (X) → output (Y), with center deadzone band."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setObjectName("CurvePreview")
        self._zero = 0
        self._end = 100
        self._live: tuple[float, float] | None = (
            None  # normalized -1..1 stick, or 0..1 trigger
        )

    def set_curve(self, zero: int, end: int) -> None:
        self._zero = max(0, min(100, int(zero)))
        self._end = max(self._zero + 1, min(100, int(end)))
        self.update()

    def set_live_stick(self, x: float, y: float) -> None:
        self._live = (max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))
        self.update()

    def set_live_trigger(self, t: float) -> None:
        self._live = (max(0.0, min(1.0, t)), 0.0)
        self.update()

    def clear_live(self) -> None:
        self._live = None
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 18
        plot = self.rect().adjusted(margin, margin, -margin, -margin)
        p.fillRect(self.rect(), QColor("#1a1c22"))
        p.fillRect(plot, QColor("#12141a"))

        # Deadzone band (center → gray)
        dz_w = plot.width() * (self._zero / 100.0)
        p.fillRect(
            int(plot.left()),
            int(plot.top()),
            int(dz_w),
            int(plot.height()),
            QColor(126, 133, 142, 70),
        )
        # Outer unused (end → 100)
        if self._end < 100:
            ow = plot.width() * ((100 - self._end) / 100.0)
            p.fillRect(
                int(plot.right() - ow),
                int(plot.top()),
                int(ow),
                int(plot.height()),
                QColor(40, 90, 250, 40),
            )

        # Grid
        p.setPen(QPen(QColor("#2c303a"), 1))
        for i in range(5):
            t = i / 4
            x = plot.left() + plot.width() * t
            y = plot.top() + plot.height() * t
            p.drawLine(int(x), int(plot.top()), int(x), int(plot.bottom()))
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))

        # Ideal response: 0 until zero, then linear to end→100%
        p.setPen(QPen(QColor("#4c8dff"), 2.5))
        z = self._zero / 100.0
        e = self._end / 100.0
        pts = []
        for i in range(101):
            xin = i / 100.0
            if xin <= z:
                yout = 0.0
            elif xin >= e:
                yout = 1.0
            else:
                yout = (xin - z) / (e - z)
            px = plot.left() + xin * plot.width()
            py = plot.bottom() - yout * plot.height()
            pts.append((px, py))
        for i in range(len(pts) - 1):
            p.drawLine(
                int(pts[i][0]), int(pts[i][1]), int(pts[i + 1][0]), int(pts[i + 1][1])
            )

        # Live sample
        if self._live is not None:
            lx, ly = self._live
            if abs(ly) > 0.02 or abs(lx) > 0.02 or (ly == 0.0 and lx >= 0):
                # stick: magnitude; trigger: lx only
                mag = (lx * lx + ly * ly) ** 0.5 if abs(ly) > 0.02 else abs(lx)
                mag = max(0.0, min(1.0, mag))
                if mag <= z:
                    out = 0.0
                elif mag >= e:
                    out = 1.0
                else:
                    out = (mag - z) / (e - z)
                cx = plot.left() + mag * plot.width()
                cy = plot.bottom() - out * plot.height()
                p.setPen(QPen(QColor("#22e4d0"), 2))
                p.setBrush(QColor("#22e4d0"))
                p.drawEllipse(int(cx - 5), int(cy - 5), 10, 10)

        p.setPen(QColor("#9a958c"))
        p.drawText(
            plot.adjusted(4, 4, -4, -4),
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft),
            "in",
        )
        p.drawText(
            plot.adjusted(4, 4, -4, -4),
            int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft),
            "out",
        )


class FeelPage(QWidget):
    """Sticks/triggers + vibration — one save path, live curve like Space Station."""

    TARGETS = (
        ("left_stick", "Left stick"),
        ("right_stick", "Right stick"),
        ("left_trigger", "LT"),
        ("right_trigger", "RT"),
    )

    def __init__(self, rpc: Rpc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rpc = rpc
        self._transport = "unknown"
        self._config: dict[str, Any] | None = None
        self._curves: dict[str, dict[str, int]] = {
            k: {"zero": 0, "end": 100} for k, _ in self.TARGETS
        }
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        title = QLabel("Feel")
        title.setObjectName("PageTitle")
        lead = QLabel(
            "Center deadzone and outer limit for each stick/trigger, plus motor strength. "
            "Same onboard curve fields Space Station writes."
        )
        lead.setObjectName("PageLead")
        lead.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(lead)

        body = QHBoxLayout()
        body.setSpacing(14)

        # —— curves ——
        curve_card = _card()
        cl = QVBoxLayout(curve_card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(10)
        ht = QLabel("Response curve")
        ht.setObjectName("CardTitle")
        cl.addWidget(ht)
        tip = QLabel("X = physical throw · Y = what games see. Gray = deadzone.")
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        cl.addWidget(tip)

        self.target = QComboBox()
        for key, label in self.TARGETS:
            self.target.addItem(label, key)
        self.target.currentIndexChanged.connect(self._on_target)
        cl.addWidget(self.target)

        self.preview = CurvePreview()
        cl.addWidget(self.preview, stretch=1)

        self.dz = QSlider(Qt.Orientation.Horizontal)
        self.dz.setRange(0, 40)
        self.end = QSlider(Qt.Orientation.Horizontal)
        self.end.setRange(50, 100)
        self.end.setValue(100)
        self.dz_val = QLabel("0%")
        self.dz_val.setObjectName("Value")
        self.end_val = QLabel("100%")
        self.end_val.setObjectName("Value")
        self.dz.valueChanged.connect(self._on_curve_sliders)
        self.end.valueChanged.connect(self._on_curve_sliders)

        row_dz = QHBoxLayout()
        row_dz.addWidget(QLabel("Center deadzone"))
        row_dz.addWidget(self.dz, stretch=1)
        row_dz.addWidget(self.dz_val)
        cl.addLayout(row_dz)
        row_end = QHBoxLayout()
        row_end.addWidget(QLabel("Outer limit"))
        row_end.addWidget(self.end, stretch=1)
        row_end.addWidget(self.end_val)
        cl.addLayout(row_end)
        body.addWidget(curve_card, stretch=3)

        # —— vibration + actions ——
        side = QVBoxLayout()
        side.setSpacing(14)
        vib = _card()
        vl = QVBoxLayout(vib)
        vl.setContentsMargins(16, 16, 16, 16)
        vl.setSpacing(10)
        vt = QLabel("Vibration")
        vt.setObjectName("CardTitle")
        vl.addWidget(vt)
        self.motor_on = QCheckBox("Motors enabled")
        self.motor_on.setChecked(True)
        self.motor_on.toggled.connect(lambda _v: self._mark_dirty())
        vl.addWidget(self.motor_on)
        self.motor_l = QSlider(Qt.Orientation.Horizontal)
        self.motor_r = QSlider(Qt.Orientation.Horizontal)
        self.motor_l.setRange(0, 100)
        self.motor_r.setRange(0, 100)
        self.motor_l.setValue(100)
        self.motor_r.setValue(100)
        self.motor_l_val = QLabel("100%")
        self.motor_r_val = QLabel("100%")
        for s in (self.motor_l, self.motor_r):
            s.valueChanged.connect(self._on_motor_sliders)
        lr = QHBoxLayout()
        lr.addWidget(QLabel("Left"))
        lr.addWidget(self.motor_l, stretch=1)
        lr.addWidget(self.motor_l_val)
        vl.addLayout(lr)
        rr = QHBoxLayout()
        rr.addWidget(QLabel("Right"))
        rr.addWidget(self.motor_r, stretch=1)
        rr.addWidget(self.motor_r_val)
        vl.addLayout(rr)
        trow = QHBoxLayout()
        test = QPushButton("Test motors")
        test.setObjectName("Primary")
        test.clicked.connect(self._test_rumble)
        stop = QPushButton("Stop")
        stop.clicked.connect(lambda: self._rpc("rumble", low=0, high=0, duration_ms=0))
        trow.addWidget(test)
        trow.addWidget(stop)
        trow.addStretch()
        vl.addLayout(trow)
        side.addWidget(vib)

        actions = _card()
        al = QVBoxLayout(actions)
        al.setContentsMargins(16, 16, 16, 16)
        al.setSpacing(8)
        self.status = QLabel(
            "Open this page with the pad on USB / dongle to load settings."
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
        side.addStretch()
        body.addLayout(side, stretch=2)

        root.addLayout(body, stretch=1)
        self._on_target()

    def set_transport(self, transport: str) -> None:
        self._transport = transport

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._transport != "bluetooth" and self._config is None:
            QTimer.singleShot(0, self.reload_from_pad)

    def on_report(self, rep: dict) -> None:
        key = self.target.currentData()
        if key == "left_stick":
            self.preview.set_live_stick(
                rep.get("lx", 0) / 32767.0, rep.get("ly", 0) / 32767.0
            )
        elif key == "right_stick":
            self.preview.set_live_stick(
                rep.get("rx", 0) / 32767.0, rep.get("ry", 0) / 32767.0
            )
        elif key == "left_trigger":
            self.preview.set_live_trigger(rep.get("lt", 0) / 255.0)
        elif key == "right_trigger":
            self.preview.set_live_trigger(rep.get("rt", 0) / 255.0)

    def _usb_ok(self) -> bool:
        if self._transport == "bluetooth":
            QMessageBox.information(
                self,
                "Cable or dongle needed",
                "Feel settings need USB or the 2.4 GHz dongle.",
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
        self._config = resp["config"]
        for key, _ in self.TARGETS:
            c = self._config.get(key) or {}
            self._curves[key] = {
                "zero": int(c.get("zero", 0)),
                "end": int(c.get("end", 100)),
            }
        m = self._config.get("motor") or {}
        self.motor_on.blockSignals(True)
        self.motor_on.setChecked(bool(m.get("main_switch", True)))
        self.motor_on.blockSignals(False)
        left = m.get("left") or {}
        right = m.get("right") or {}
        self.motor_l.blockSignals(True)
        self.motor_r.blockSignals(True)
        self.motor_l.setValue(int(left.get("scale", 100)))
        self.motor_r.setValue(int(right.get("scale", 100)))
        self.motor_l.blockSignals(False)
        self.motor_r.blockSignals(False)
        self.motor_l_val.setText(f"{self.motor_l.value()}%")
        self.motor_r_val.setText(f"{self.motor_r.value()}%")
        self._dirty = False
        self._apply_target_to_sliders()
        self.status.setText("Loaded from the controller.")

    @Slot()
    def save_to_pad(self) -> None:
        if not self._usb_ok():
            return
        self.status.setText("Saving…")
        ok = self._rpc(
            "config_set_feel",
            **{k: dict(v) for k, v in self._curves.items()},
            main_switch=self.motor_on.isChecked(),
            left={"scale": self.motor_l.value()},
            right={"scale": self.motor_r.value()},
        ).get("ok")
        if ok:
            self._dirty = False
            self.status.setText("Saved to the pad.")
        else:
            self.status.setText("Save failed — nothing written.")

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.status.setText("Unsaved changes — Save to pad when ready.")

    def _on_target(self) -> None:
        # Sliders already write into the active target; just load the new one.
        self._apply_target_to_sliders()

    def _apply_target_to_sliders(self) -> None:
        key = str(self.target.currentData())
        c = self._curves[key]
        self.dz.blockSignals(True)
        self.end.blockSignals(True)
        self.dz.setValue(int(c["zero"]))
        self.end.setValue(max(self.end.minimum(), int(c["end"])))
        self.dz.blockSignals(False)
        self.end.blockSignals(False)
        self._refresh_curve_labels()
        self.preview.set_curve(c["zero"], c["end"])

    def _on_curve_sliders(self) -> None:
        key = str(self.target.currentData())
        zero = self.dz.value()
        end = max(zero + 1, self.end.value())
        if end != self.end.value():
            self.end.blockSignals(True)
            self.end.setValue(end)
            self.end.blockSignals(False)
        self._curves[key] = {"zero": zero, "end": end}
        self._refresh_curve_labels()
        self.preview.set_curve(zero, end)
        self._mark_dirty()

    def _refresh_curve_labels(self) -> None:
        self.dz_val.setText(f"{self.dz.value()}%")
        self.end_val.setText(f"{self.end.value()}%")

    def _on_motor_sliders(self) -> None:
        self.motor_l_val.setText(f"{self.motor_l.value()}%")
        self.motor_r_val.setText(f"{self.motor_r.value()}%")
        self._mark_dirty()

    @Slot()
    def _test_rumble(self) -> None:
        if not self._usb_ok():
            return
        # Scale UI 0–100 → rumble bytes roughly
        lo = int(self.motor_l.value() * 2.55)
        hi = int(self.motor_r.value() * 2.55)
        self._rpc("rumble", low=lo, high=hi, duration_ms=1200)
        QTimer.singleShot(500, lambda: self._rpc("rumble", low=0, high=0))
