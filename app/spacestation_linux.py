#!/usr/bin/env python3
"""Flydigi Space Station (Linux) — Vader 4 Pro companion.

Talks to flydigi-vader4d over its Unix socket (uinput + IF2 commands multiplexed).
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flydigi.enumerate import list_vader4_interfaces  # noqa: E402
from flydigi.ipc import DaemonClient, default_socket_path  # noqa: E402
from flydigi.gamepad_config import KEY_NAMES  # noqa: E402

LED_MODES = [
    (0, "Off"),
    (1, "Streamlined"),
    (2, "Breathing"),
    (3, "Gradient"),
    (4, "Feedback"),
    (5, "Steady"),
]


class DaemonBridge(QObject):
    status = Signal(str)
    info = Signal(dict)
    report = Signal(dict)
    config = Signal(dict)
    led = Signal(dict)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._path = default_socket_path()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="daemon-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def call(self, cmd: str, **kwargs):
        with DaemonClient(self._path) as c:
            return c.request(cmd, **kwargs)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                client = DaemonClient(self._path)
                client.connect(timeout=1.0)
            except OSError:
                self.status.emit(f"Waiting for daemon ({self._path})…")
                self._stop.wait(1.0)
                continue
            self.status.emit(f"Connected to daemon @ {self._path}")
            try:
                info = client.request("info")
                if info.get("ok"):
                    self.info.emit(info["info"])
                client.request("subscribe")
                client._sock.settimeout(0.5)  # noqa: SLF001
                while not self._stop.is_set():
                    line = client._readline()  # noqa: SLF001
                    if line is None:
                        # timeout — keep alive
                        continue
                    msg = json.loads(line)
                    if msg.get("event") == "report":
                        self.report.emit(msg)
            except Exception as exc:  # noqa: BLE001
                self.status.emit(f"Daemon link lost: {exc}")
            finally:
                client.close()
            self._stop.wait(0.5)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flydigi Space Station (Linux) — Vader 4 Pro")
        self.resize(980, 700)
        self._color = QColor(0, 200, 80)
        self._config: dict | None = None
        self._transport: str = "unknown"

        tabs = QTabWidget()
        tabs.addTab(self._build_device_tab(), "Device")
        tabs.addTab(self._build_live_tab(), "Live input")
        tabs.addTab(self._build_profiles_tab(), "Profiles")
        tabs.addTab(self._build_sticks_tab(), "Sticks & triggers")
        tabs.addTab(self._build_lighting_tab(), "Lighting")
        tabs.addTab(self._build_rumble_tab(), "Rumble")
        tabs.addTab(self._build_mode_tab(), "Mode")
        tabs.addTab(self._build_firmware_tab(), "Firmware")
        self.setCentralWidget(tabs)

        self._bridge = DaemonBridge()
        self._bridge.status.connect(self._on_status)
        self._bridge.info.connect(self._on_info)
        self._bridge.report.connect(self._on_report)
        self._bridge.error.connect(lambda m: QMessageBox.warning(self, "Error", m))
        self._refresh_hid()
        self._bridge.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bridge.stop()
        super().closeEvent(event)

    def _rpc(self, cmd: str, **kwargs) -> dict:
        try:
            resp = self._bridge.call(cmd, **kwargs)
        except OSError as exc:
            QMessageBox.warning(self, "Daemon", f"Cannot reach flydigi-vader4d:\n{exc}")
            return {"ok": False, "error": str(exc)}
        if not resp.get("ok"):
            QMessageBox.warning(self, "Command failed", resp.get("error", "unknown"))
        return resp

    def _require_usb_config(self) -> bool:
        if self._transport == "bluetooth":
            QMessageBox.information(
                self,
                "USB / dongle required",
                "LED, rumble, and onboard profiles need the 2.4G dongle or USB-C.\n"
                "Bluetooth DInput is input-only (same as official Space Station).",
            )
            return False
        return True

    def _build_device_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.device_status = QLabel("…")
        self.device_status.setWordWrap(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setFont(mono)
        self.info_box.setMaximumHeight(160)
        self.hid_list = QTextEdit()
        self.hid_list.setReadOnly(True)
        self.hid_list.setFont(mono)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_all)
        row.addWidget(refresh)
        row.addStretch()
        layout.addWidget(QLabel("Daemon / device"))
        layout.addWidget(self.device_status)
        layout.addLayout(row)
        layout.addWidget(QLabel("Identity (cmd 236)"))
        layout.addWidget(self.info_box)
        layout.addWidget(QLabel("USB hidraw interfaces"))
        layout.addWidget(self.hid_list)
        tip = QLabel(
            "PC/DInput mode (blue LED). FN toggles onboard gyro-mouse (firmware). "
            "Start the driver first: python3 driver/flydigi_vader4d.py"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        return w

    def _build_live_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        box = QGroupBox("V1 report (via daemon)")
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
            ("Accel / gyro", self.lbl_motion),
        ):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, widget)
        layout.addWidget(box)
        layout.addStretch()
        return w

    def _build_profiles_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        load = QPushButton("Load from pad")
        load.clicked.connect(self._load_config)
        apply = QPushButton("Apply key map")
        apply.clicked.connect(self._apply_keys)
        reset = QPushButton("Reset selected → native")
        reset.clicked.connect(self._reset_key_native)
        row.addWidget(load)
        row.addWidget(apply)
        row.addWidget(reset)
        row.addStretch()
        layout.addLayout(row)
        self.key_table = QTableWidget(0, 4)
        self.key_table.setHorizontalHeaderLabels(["Key", "Maps to", "Turbo", "Remapped"])
        self.key_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.key_table)
        return w

    def _build_sticks_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()
        self.dz_left = QSpinBox()
        self.dz_left.setRange(0, 100)
        self.dz_right = QSpinBox()
        self.dz_right.setRange(0, 100)
        self.dz_lt = QSpinBox()
        self.dz_lt.setRange(0, 100)
        self.dz_rt = QSpinBox()
        self.dz_rt.setRange(0, 100)
        form.addRow("Left stick deadzone", self.dz_left)
        form.addRow("Right stick deadzone", self.dz_right)
        form.addRow("LT deadzone", self.dz_lt)
        form.addRow("RT deadzone", self.dz_rt)
        layout.addLayout(form)
        row = QHBoxLayout()
        load = QPushButton("Load")
        load.clicked.connect(self._load_sticks)
        apply = QPushButton("Apply to pad")
        apply.clicked.connect(self._apply_sticks)
        row.addWidget(load)
        row.addWidget(apply)
        row.addStretch()
        layout.addLayout(row)
        note = QLabel("Writes onboard config (cmd 234). Curve points beyond deadzone are preserved.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return w

    def _build_lighting_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()
        self.led_mode = QComboBox()
        for value, name in LED_MODES:
            self.led_mode.addItem(name, value)
        self.led_mode.setCurrentIndex(5)
        self.led_brightness = QSlider(Qt.Orientation.Horizontal)
        self.led_brightness.setRange(0, 100)
        self.led_brightness.setValue(80)
        self.led_speed = QSlider(Qt.Orientation.Horizontal)
        self.led_speed.setRange(0, 100)
        self.led_speed.setValue(50)
        self.color_btn = QPushButton("Pick color")
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        form.addRow("Mode", self.led_mode)
        form.addRow("Brightness", self.led_brightness)
        form.addRow("Speed (stream/breath)", self.led_speed)
        form.addRow("Color", self.color_btn)
        layout.addLayout(form)
        row = QHBoxLayout()
        getb = QPushButton("Read from pad")
        getb.clicked.connect(self._led_get)
        setb = QPushButton("Apply")
        setb.clicked.connect(self._led_set)
        row.addWidget(getb)
        row.addWidget(setb)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return w

    def _build_rumble_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()
        self.rumble_lo = QSlider(Qt.Orientation.Horizontal)
        self.rumble_hi = QSlider(Qt.Orientation.Horizontal)
        for s in (self.rumble_lo, self.rumble_hi):
            s.setRange(0, 255)
            s.setValue(180)
        form.addRow("Low motor", self.rumble_lo)
        form.addRow("High motor", self.rumble_hi)
        layout.addLayout(form)
        row = QHBoxLayout()
        test = QPushButton("Test (1.5s)")
        test.clicked.connect(self._rumble_test)
        stop = QPushButton("Stop")
        stop.clicked.connect(
            lambda: self._rpc("rumble", low=0, high=0, duration_ms=0)
        )
        row.addWidget(test)
        row.addWidget(stop)
        row.addStretch()
        layout.addLayout(row)

        box = QGroupBox("Onboard motor curve (config)")
        mform = QFormLayout(box)
        self.motor_on = QCheckBox("Motors enabled")
        self.motor_on.setChecked(True)
        self.motor_l_scale = QSpinBox()
        self.motor_r_scale = QSpinBox()
        for s in (self.motor_l_scale, self.motor_r_scale):
            s.setRange(0, 100)
            s.setValue(100)
        mform.addRow(self.motor_on)
        mform.addRow("Left scale", self.motor_l_scale)
        mform.addRow("Right scale", self.motor_r_scale)
        mrow = QHBoxLayout()
        mload = QPushButton("Load motor cfg")
        mload.clicked.connect(self._load_motor)
        mapply = QPushButton("Apply motor cfg")
        mapply.clicked.connect(self._apply_motor)
        mrow.addWidget(mload)
        mrow.addWidget(mapply)
        mrow.addStretch()
        layout.addWidget(box)
        layout.addLayout(mrow)
        layout.addStretch()
        return w

    def _build_mode_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("<b>Input protocol (firmware combos)</b>"))
        layout.addWidget(
            QLabel(
                "This Linux stack only supports <b>PC / DInput</b> (blue status LED, "
                "USB ID 04b4:2412). Mode changes are done on the pad — they re-enumerate USB."
            )
        )
        box = QGroupBox("Hold until the status LED changes")
        form = QFormLayout(box)
        form.addRow("DInput (blue)", QLabel("FN ◯ + A"))
        form.addRow("XInput (white)", QLabel("FN ◯ + X  — becomes Xbox-like; leave this stack"))
        form.addRow("Gyro-mouse toggle", QLabel("FN ◯  (DInput only; firmware feature)"))
        form.addRow("Onboard profiles", QLabel("SELECT + A/B/X/Y"))
        form.addRow("Rear switch", QLabel("Dongle / Bluetooth / NS / Mobile"))
        layout.addWidget(box)
        tip = QLabel(
            "Bluetooth DInput is stubbed — pair the pad, run "
            "`python3 driver/flydigi_vader4d.py --list`, and capture hidraw IDs "
            "(see docs/bluetooth.md)."
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch()
        return w

    def _build_firmware_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(
            QLabel(
                "Firmware updates stay gated until the Space Station DFU sequence "
                "(FirmwareConsole / ISP DLLs) is fully reverse-engineered. Prefer wired."
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
                "Flashing will be enabled only after command framing, image format, "
                "and abort paths are verified on this pad.",
            )
        )
        layout.addWidget(warn)
        layout.addStretch()
        return w

    def _update_color_btn(self) -> None:
        self.color_btn.setStyleSheet(
            f"background:{self._color.name()}; color:{'#000' if self._color.lightness() > 140 else '#fff'};"
        )
        self.color_btn.setText(self._color.name())

    @Slot()
    def _pick_color(self) -> None:
        c = QColorDialog.getColor(self._color, self, "LED color")
        if c.isValid():
            self._color = c
            self._update_color_btn()

    @Slot()
    def _refresh_all(self) -> None:
        self._refresh_hid()
        resp = self._rpc("info")
        if resp.get("ok"):
            self._on_info(resp["info"])

    def _refresh_hid(self) -> None:
        lines = []
        for i in list_vader4_interfaces():
            role = {0: "gamepad-lite", 1: "mouse", 2: "DInput+IMU", 3: "config?"}.get(
                i.interface_number, "?"
            )
            lines.append(
                f"{i.hidraw}  bus={i.bus}  iface={i.interface_number} ({role})  {i.phys}"
            )
        self.hid_list.setPlainText("\n".join(lines) if lines else "(no Flydigi Vader hidraw)")

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        self.device_status.setText(msg)

    @Slot(dict)
    def _on_info(self, info: dict) -> None:
        transport = info.get("transport") or info.get("connection_type") or ""
        if transport == "bluetooth" or info.get("hid", "").startswith("d7d7"):
            self._transport = "bluetooth"
        else:
            self._transport = "usb"
        lines = [
            f"transport = {self._transport}",
            f"device_id = {info.get('device_id')}",
            f"firmware  = {info.get('firmware')}",
            f"battery   = {info.get('battery')}% (raw {info.get('battery_raw')})",
            f"cpu/conn/motion = {info.get('cpu_type')}/{info.get('connection_type')}/{info.get('motion_sensor_type')}",
            f"mac       = {info.get('mac')}",
            f"hid       = {info.get('hid')}",
            f"name      = {info.get('name')}",
        ]
        if self._transport == "bluetooth":
            lines.append("")
            lines.append("BT DInput: input only — use dongle/USB for LED, rumble, profiles.")
        self.info_box.setPlainText("\n".join(lines))

    @Slot(dict)
    def _on_report(self, rep: dict) -> None:
        self.lbl_sticks.setText(f"L=({rep['lx']}, {rep['ly']})  R=({rep['rx']}, {rep['ry']})")
        self.lbl_triggers.setText(f"LT={rep['lt']}  RT={rep['rt']}")
        self.lbl_hat.setText(f"({rep['hat_x']}, {rep['hat_y']}) raw={rep['hat']:#x}")
        btns = rep.get("buttons") or {}
        self.lbl_buttons.setText(", ".join(btns) if btns else "(none)")
        self.lbl_motion.setText(f"accel={rep.get('accel')}  gyro={rep.get('gyro')}")

    @Slot()
    def _load_config(self) -> None:
        if not self._require_usb_config():
            return
        resp = self._rpc("config_get")
        if not resp.get("ok"):
            return
        self._config = resp["config"]
        keys = self._config.get("keys", [])
        self.key_table.setRowCount(len(keys))
        for row, k in enumerate(keys):
            self.key_table.setItem(row, 0, QTableWidgetItem(k["name"]))
            combo = QComboBox()
            combo.addItem("(native)", 255)
            for i, name in enumerate(KEY_NAMES):
                if name != "?":
                    combo.addItem(name, i)
            idx = combo.findData(k["map_id"])
            if idx < 0:
                combo.addItem(k.get("map_name", str(k["map_id"])), k["map_id"])
                idx = combo.count() - 1
            combo.setCurrentIndex(max(0, idx))
            self.key_table.setCellWidget(row, 1, combo)
            turbo = QSpinBox()
            turbo.setRange(0, 255)
            turbo.setValue(int(k.get("turbo", 0)))
            self.key_table.setCellWidget(row, 2, turbo)
            self.key_table.setItem(row, 3, QTableWidgetItem("yes" if k.get("remapped") else ""))
            self.key_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, k["id"])
        self._load_sticks_from_config()
        self._load_motor_from_config()

    def _load_sticks_from_config(self) -> None:
        if not self._config:
            return
        self.dz_left.setValue(int(self._config["left_stick"]["zero"]))
        self.dz_right.setValue(int(self._config["right_stick"]["zero"]))
        self.dz_lt.setValue(int(self._config["left_trigger"]["zero"]))
        self.dz_rt.setValue(int(self._config["right_trigger"]["zero"]))

    def _load_motor_from_config(self) -> None:
        if not self._config:
            return
        m = self._config["motor"]
        self.motor_on.setChecked(bool(m["main_switch"]))
        self.motor_l_scale.setValue(int(m["left"]["scale"]))
        self.motor_r_scale.setValue(int(m["right"]["scale"]))

    @Slot()
    def _apply_keys(self) -> None:
        if not self._require_usb_config():
            return
        keys = []
        for row in range(self.key_table.rowCount()):
            kid = self.key_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            combo: QComboBox = self.key_table.cellWidget(row, 1)  # type: ignore[assignment]
            turbo: QSpinBox = self.key_table.cellWidget(row, 2)  # type: ignore[assignment]
            keys.append({"id": int(kid), "map_id": int(combo.currentData()), "turbo": turbo.value()})
        self._rpc("config_set_keys", keys=keys)

    @Slot()
    def _reset_key_native(self) -> None:
        rows = {i.row() for i in self.key_table.selectedIndexes()}
        for row in rows:
            combo: QComboBox = self.key_table.cellWidget(row, 1)  # type: ignore[assignment]
            combo.setCurrentIndex(0)

    @Slot()
    def _load_sticks(self) -> None:
        if not self._require_usb_config():
            return
        resp = self._rpc("config_get")
        if resp.get("ok"):
            self._config = resp["config"]
            self._load_sticks_from_config()

    @Slot()
    def _apply_sticks(self) -> None:
        if not self._require_usb_config():
            return
        self._rpc(
            "config_set_sticks",
            left_stick={"zero": self.dz_left.value()},
            right_stick={"zero": self.dz_right.value()},
            left_trigger={"zero": self.dz_lt.value()},
            right_trigger={"zero": self.dz_rt.value()},
        )

    @Slot()
    def _led_get(self) -> None:
        if not self._require_usb_config():
            return
        resp = self._rpc("led_get")
        if not resp.get("ok"):
            return
        led = resp["led"]
        idx = self.led_mode.findData(led["mode"])
        if idx >= 0:
            self.led_mode.setCurrentIndex(idx)
        self.led_brightness.setValue(int(led["brightness"]))
        c = led.get("color") or [0, 0, 0]
        self._color = QColor(int(c[0]), int(c[1]), int(c[2]))
        self._update_color_btn()

    @Slot()
    def _led_set(self) -> None:
        if not self._require_usb_config():
            return
        self._rpc(
            "led_set",
            mode=int(self.led_mode.currentData()),
            r=self._color.red(),
            g=self._color.green(),
            b=self._color.blue(),
            brightness=self.led_brightness.value(),
            speed=self.led_speed.value(),
        )

    @Slot()
    def _rumble_test(self) -> None:
        if not self._require_usb_config():
            return
        self._rpc(
            "rumble",
            low=self.rumble_lo.value(),
            high=self.rumble_hi.value(),
            duration_ms=1500,
        )
        from PySide6.QtCore import QTimer

        QTimer.singleShot(400, lambda: self._rpc("rumble", low=0, high=0))

    @Slot()
    def _load_motor(self) -> None:
        if not self._require_usb_config():
            return
        resp = self._rpc("config_get")
        if resp.get("ok"):
            self._config = resp["config"]
            self._load_motor_from_config()

    @Slot()
    def _apply_motor(self) -> None:
        if not self._require_usb_config():
            return
        self._rpc(
            "config_set_motor",
            main_switch=self.motor_on.isChecked(),
            left={"scale": self.motor_l_scale.value()},
            right={"scale": self.motor_r_scale.value()},
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Flydigi Space Station Linux")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
