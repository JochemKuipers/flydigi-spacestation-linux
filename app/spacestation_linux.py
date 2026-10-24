#!/usr/bin/env python3
"""Flydigi Space Station (Linux) — Vader 4 Pro companion (early UI).

Phase goals: device discovery, live DInput monitor, placeholders for
profiles / lighting / rumble / firmware (protocol still being recovered).
"""

from __future__ import annotations

import os
import select
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.enumerate import (  # noqa: E402
    find_config_interface,
    find_input_interface,
    list_vader4_interfaces,
)
from flydigi.v1_report import parse_v1_report  # noqa: E402


class HidPoller(QObject):
    report = Signal(object)
    status = Signal(str)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="hid-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.finished.emit()

    def _run(self) -> None:
        while not self._stop.is_set():
            iface = find_input_interface()
            if iface is None:
                self.status.emit("Waiting for Vader 4 Pro (04b4:2412 IF2, DInput)…")
                self._stop.wait(0.8)
                continue
            self.status.emit(f"Connected {iface.hidraw} (USB iface {iface.interface_number})")
            try:
                fd = os.open(iface.hidraw, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as exc:
                self.status.emit(f"Open failed: {exc}")
                self._stop.wait(1.0)
                continue
            try:
                while not self._stop.is_set():
                    if not iface.hidraw.exists():
                        self.status.emit("Device disconnected")
                        break
                    r, _, _ = select.select([fd], [], [], 0.5)
                    if not r:
                        continue
                    try:
                        data = os.read(fd, 64)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        self.status.emit(f"Read error: {exc}")
                        break
                    rep = parse_v1_report(data)
                    if rep:
                        self.report.emit(rep)
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
            time.sleep(0.3)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flydigi Space Station (Linux) — Vader 4 Pro")
        self.resize(920, 640)

        tabs = QTabWidget()
        tabs.addTab(self._build_device_tab(), "Device")
        tabs.addTab(self._build_live_tab(), "Live input")
        tabs.addTab(self._build_placeholder("Profiles", "Button mapping / onboard profiles — protocol WIP"), "Profiles")
        tabs.addTab(self._build_placeholder("Sticks & triggers", "Curves / deadzones / trigger modes — protocol WIP"), "Sticks")
        tabs.addTab(self._build_placeholder("Lighting", "LED modes including Feedback (f4) — protocol WIP"), "Lighting")
        tabs.addTab(self._build_placeholder("Rumble", "Motor + trigger vibration — protocol WIP"), "Rumble")
        tabs.addTab(self._build_firmware_tab(), "Firmware")
        self.setCentralWidget(tabs)

        self._poller = HidPoller()
        self._poller.status.connect(self._on_status)
        self._poller.report.connect(self._on_report)

        self._refresh_devices()
        self._poller.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._poller.stop()
        super().closeEvent(event)

    def _build_device_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.device_status = QLabel("…")
        self.device_status.setWordWrap(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.device_list = QTextEdit()
        self.device_list.setReadOnly(True)
        self.device_list.setFont(mono)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh USB/HID")
        refresh.clicked.connect(self._refresh_devices)
        row.addWidget(refresh)
        row.addStretch()
        layout.addWidget(QLabel("Connection"))
        layout.addWidget(self.device_status)
        layout.addLayout(row)
        layout.addWidget(QLabel("Interfaces (IF2 = gamepad stream, IF3 = config)"))
        layout.addWidget(self.device_list)
        tip = QLabel(
            "Use PC/DInput mode (blue LED). FN toggles onboard gyro-mouse (firmware), "
            "not something this app invents."
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        return w

    def _build_live_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        box = QGroupBox("V1 report (IF2)")
        form = QFormLayout(box)
        self.lbl_sticks = QLabel("—")
        self.lbl_triggers = QLabel("—")
        self.lbl_hat = QLabel("—")
        self.lbl_buttons = QLabel("—")
        self.lbl_motion = QLabel("—")
        for label, widget in (
            ("Sticks L/R", self.lbl_sticks),
            ("Triggers", self.lbl_triggers),
            ("Hat", self.lbl_hat),
            ("Buttons", self.lbl_buttons),
            ("Accel / gyro (raw)", self.lbl_motion),
        ):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, widget)
        layout.addWidget(box)
        layout.addStretch()
        return w

    def _build_firmware_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(
            QLabel(
                "Firmware updates are intentionally gated until the Space Station "
                "DFU sequence is fully reverse-engineered. Prefer a wired link for flash."
            )
        )
        btn = QPushButton("Firmware updater (disabled)")
        btn.setEnabled(False)
        layout.addWidget(btn)
        warn = QPushButton("Why is this locked?")
        warn.clicked.connect(
            lambda: QMessageBox.information(
                self,
                "Firmware safety",
                "Space Station ships NativeAOT FirmwareConsole + vendor ISP DLLs. "
                "We will enable flashing only after command framing, image format, "
                "and abort paths are verified on this pad.",
            )
        )
        layout.addWidget(warn)
        layout.addStretch()
        return w

    def _build_placeholder(self, title: str, body: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        layout.addWidget(QLabel(body))
        layout.addStretch()
        return w

    @Slot()
    def _refresh_devices(self) -> None:
        lines = []
        for i in list_vader4_interfaces():
            role = {0: "gamepad-lite", 1: "mouse", 2: "DInput+IMU", 3: "config"}.get(
                i.interface_number, "?"
            )
            lines.append(f"{i.hidraw}  iface={i.interface_number} ({role})  {i.phys}")
        cfg = find_config_interface()
        inp = find_input_interface()
        if not lines:
            self.device_list.setPlainText("(no 04b4:2412 hidraw nodes)")
        else:
            self.device_list.setPlainText("\n".join(lines))
        extra = []
        if inp:
            extra.append(f"input={inp.hidraw}")
        if cfg:
            extra.append(f"config={cfg.hidraw}")
        if extra:
            self.device_status.setText("Device present — " + ", ".join(extra))

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        self.device_status.setText(msg)

    @Slot(object)
    def _on_report(self, rep: object) -> None:
        self.lbl_sticks.setText(
            f"L=({rep.lx}, {rep.ly})  R=({rep.rx}, {rep.ry})"
        )
        self.lbl_triggers.setText(f"LT={rep.lt}  RT={rep.rt}")
        self.lbl_hat.setText(f"({rep.hat_x}, {rep.hat_y}) raw={rep.hat:#x}")
        pressed = [k for k, v in rep.buttons.items() if v]
        self.lbl_buttons.setText(", ".join(pressed) if pressed else "(none)")
        self.lbl_motion.setText(
            f"accel={rep.accel}  gyro={rep.gyro}"
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Flydigi Space Station Linux")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
