"""Flydigi Vader companion — product UI shell."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from flydigi.dinput_proto import build_led
from flydigi.ota import DEFAULT_BIN, usb_ota_ready

from .bridge import DaemonBridge
from .buttons import ButtonsPage
from .feel import FeelPage
from .manual import ManualView
from .widgets import LivePadView, StatChip, logo_pixmap
from .workers import CatalogFetcher, OtaWorker, start_ota_thread

LED_MODES = [
    (6, "Off"),  # SS Close
    (1, "Flow (rainbow)"),  # official moving rainbow
    (2, "Breathing"),
    (3, "Gradient"),  # 2-color fade, not rainbow
    (4, "Feedback"),
    (5, "Steady"),
]

# Modes where a single picked color is meaningful (Flow uses fixed SS rainbow)
_COLOR_MODES = {2, 3, 4, 5}

NAV = ("Overview", "Lighting", "Feel", "Buttons", "Firmware", "Manual")


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def _page(title: str, lead: str) -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("Page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(14)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    lead_l = QLabel(lead)
    lead_l.setObjectName("PageLead")
    lead_l.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(lead_l)
    return w, lay


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vader 4 Pro")
        self.setWindowIcon(QIcon(logo_pixmap(128)))
        self.resize(1100, 740)
        self._color = QColor(76, 141, 255)
        self._transport = "unknown"
        self._fw_busy = False
        self._fw_pad_version: str | None = None
        self._ota_worker: OtaWorker | None = None
        # Sliders fire valueChanged on every tick — debounce preview + pad write.
        self._led_preview_timer = QTimer(self)
        self._led_preview_timer.setSingleShot(True)
        self._led_preview_timer.setInterval(50)
        self._led_preview_timer.timeout.connect(self._push_led_preview)
        self._led_timer = QTimer(self)
        self._led_timer.setSingleShot(True)
        self._led_timer.setInterval(100)
        self._led_timer.timeout.connect(self._led_apply_now)

        self._catalog = CatalogFetcher(self)
        self._catalog.finished_ok.connect(self._fw_catalog_ok)
        self._catalog.failed.connect(self._fw_catalog_fail)

        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_top())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        for name in NAV:
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav)
        body.addWidget(self.nav)

        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")
        self.feel_page = FeelPage(self._rpc)
        self.buttons_page = ButtonsPage(self._rpc)
        self.pages.addWidget(self._build_overview())
        self.pages.addWidget(self._build_lighting())
        self.pages.addWidget(self.feel_page)
        self.pages.addWidget(self.buttons_page)
        self.pages.addWidget(self._build_firmware())
        self.pages.addWidget(self._build_manual())
        body.addWidget(self.pages, stretch=1)
        outer.addLayout(body, stretch=1)
        self.setCentralWidget(root)

        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage(
            "Start the driver if nothing connects: python3 driver/flydigi_vader4d.py"
        )

        self._bridge = DaemonBridge()
        self._bridge.status.connect(self._on_status)
        self._bridge.info.connect(self._on_info)
        self._bridge.report.connect(self._on_report)
        self._bridge.error.connect(lambda m: QMessageBox.warning(self, "Error", m))
        self._bridge.start()

    def closeEvent(self, event) -> None:
        self._bridge.stop()
        super().closeEvent(event)

    def _on_nav(self, row: int) -> None:
        if row >= 0:
            self.pages.setCurrentIndex(row)

    def _build_top(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 20, 8)
        self.logo = QLabel()
        self.logo.setPixmap(logo_pixmap(44))
        self.logo.setFixedSize(44, 44)
        self.logo.setScaledContents(False)
        row.addWidget(self.logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Vader 4 Pro")
        title.setObjectName("AppTitle")
        sub = QLabel("Controller companion for Linux")
        sub.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(sub)
        row.addLayout(titles)
        row.addStretch()
        self.conn_badge = QLabel("Offline")
        self.conn_badge.setObjectName("ConnBadge")
        self.conn_badge.setProperty("state", "down")
        row.addWidget(self.conn_badge)
        return bar

    def _set_conn(self, up: bool, text: str) -> None:
        self.conn_badge.setText(text)
        self.conn_badge.setProperty("state", "up" if up else "down")
        self.conn_badge.style().unpolish(self.conn_badge)
        self.conn_badge.style().polish(self.conn_badge)

    def _build_overview(self) -> QWidget:
        w, lay = _page(
            "Your controller",
            "Watch sticks and buttons live. Use USB or the dongle for lighting and button maps.",
        )
        row = QHBoxLayout()
        row.setSpacing(14)
        self.chip_battery = StatChip("Battery")
        self.chip_fw = StatChip("Firmware")
        self.chip_link = StatChip("Connection")
        self.chip_status = StatChip("Status")
        for c in (self.chip_battery, self.chip_fw, self.chip_link, self.chip_status):
            row.addWidget(c)
        lay.addLayout(row)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        pad_card = _card()
        pad_l = QVBoxLayout(pad_card)
        pad_l.setContentsMargins(12, 12, 12, 12)
        self.live_pad = LivePadView(show_led=False)
        self.live_pad.setMinimumSize(420, 280)
        pad_l.addWidget(self.live_pad, stretch=1)
        mid.addWidget(pad_card, stretch=3)

        info_card = _card()
        info_l = QVBoxLayout(info_card)
        info_l.setContentsMargins(18, 18, 18, 18)
        it = QLabel("About this pad")
        it.setObjectName("CardTitle")
        info_l.addWidget(it)
        self.detail_name = QLabel("—")
        self.detail_name.setObjectName("Value")
        self.detail_mac = QLabel("")
        self.detail_mac.setObjectName("Muted")
        self.detail_note = QLabel("")
        self.detail_note.setObjectName("Muted")
        self.detail_note.setWordWrap(True)
        info_l.addWidget(self.detail_name)
        info_l.addWidget(self.detail_mac)
        info_l.addSpacing(8)
        info_l.addWidget(self.detail_note)
        info_l.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Primary")
        refresh.clicked.connect(self._refresh_all)
        info_l.addWidget(refresh)
        mid.addWidget(info_card, stretch=2)
        lay.addLayout(mid, stretch=1)
        return w

    def _build_lighting(self) -> QWidget:
        w, lay = _page(
            "Lighting",
            "Changes apply as you move the controls. Needs USB or the wireless dongle.",
        )
        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.setAlignment(Qt.AlignmentFlag.AlignTop)

        prev = _card()
        pl = QVBoxLayout(prev)
        pl.setContentsMargins(12, 12, 12, 12)
        # Lighting canvas: wireframe + LED only (no hotspot/input churn)
        self.led_preview = LivePadView(
            show_hotspots=False, follow_input=False, show_led=True
        )
        self.led_preview.setMinimumSize(360, 280)
        self.led_preview.set_connected(True)
        pl.addWidget(self.led_preview)
        cols.addWidget(prev, stretch=3)

        card = _card()
        # Don't stretch the short form to the preview height — that was the empty slab
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        form = QFormLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.led_mode = QComboBox()
        for value, name in LED_MODES:
            self.led_mode.addItem(name, value)
        # Default to Flow — official moving rainbow (SS NewLedTypeDto Id=1)
        self.led_mode.setCurrentIndex(1)
        self.led_brightness = QSlider(Qt.Orientation.Horizontal)
        self.led_brightness.setRange(0, 100)
        self.led_brightness.setValue(80)
        self.led_speed = QSlider(Qt.Orientation.Horizontal)
        self.led_speed.setRange(0, 100)
        self.led_speed.setValue(50)
        self.color_btn = QPushButton("Choose color")
        self.color_btn.setObjectName("ColorSwatch")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_hint = QLabel("")
        self.color_hint.setObjectName("Muted")
        self.color_hint.setWordWrap(True)
        form.addRow("Mode", self.led_mode)
        form.addRow("Brightness", self.led_brightness)
        form.addRow("Animation speed", self.led_speed)
        form.addRow("Color", self.color_btn)
        form.addRow(self.color_hint)
        hint = QLabel(
            "Preview animates the mode. USB / dongle required to write to the pad."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        cols.addWidget(card, stretch=2, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(cols, stretch=1)

        self.led_mode.currentIndexChanged.connect(
            lambda _i: self._led_schedule(preview_now=True)
        )
        self.led_brightness.valueChanged.connect(
            lambda _v: self._led_schedule(preview_now=False)
        )
        self.led_speed.valueChanged.connect(
            lambda _v: self._led_schedule(preview_now=False)
        )
        self._update_color_btn()
        self._push_led_preview()
        return w

    def _build_firmware(self) -> QWidget:
        w, lay = _page(
            "Firmware",
            "Updates need USB or the dongle. A quick handshake runs first; if it fails, nothing is written.",
        )
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.setSpacing(8)
        self.fw_pad_label = QLabel("On this controller: —")
        self.fw_pad_label.setObjectName("Value")
        self.fw_catalog_label = QLabel("Latest online: —")
        self.fw_catalog_label.setObjectName("Muted")
        self.fw_image_label = QLabel(f"Update file: {DEFAULT_BIN.name}")
        self.fw_image_label.setObjectName("Muted")
        cl.addWidget(self.fw_pad_label)
        cl.addWidget(self.fw_catalog_label)
        cl.addWidget(self.fw_image_label)
        lay.addWidget(card)
        row = QHBoxLayout()
        self.fw_check_btn = QPushButton("Check for updates")
        self.fw_check_btn.clicked.connect(self._fw_check_catalog)
        self.fw_flash_btn = QPushButton("Install update…")
        self.fw_flash_btn.setObjectName("Danger")
        self.fw_flash_btn.clicked.connect(self._fw_flash)
        row.addWidget(self.fw_check_btn)
        row.addWidget(self.fw_flash_btn)
        row.addStretch()
        lay.addLayout(row)
        self.fw_progress = QProgressBar()
        self.fw_progress.setRange(0, 100)
        lay.addWidget(self.fw_progress)
        self.fw_status = QLabel("")
        self.fw_status.setObjectName("Muted")
        self.fw_status.setWordWrap(True)
        lay.addWidget(self.fw_status)
        lay.addStretch()
        return w

    def _build_manual(self) -> QWidget:
        w, lay = _page(
            "Manual",
            "Force sticks, pairing, specs, and Q&A — structured from Flydigi’s official PDF.",
        )
        lay.addWidget(ManualView(), stretch=1)
        return w

    def _rpc(self, cmd: str, **kwargs) -> dict:
        try:
            resp = self._bridge.call(cmd, **kwargs)
        except FileNotFoundError as exc:
            QMessageBox.warning(
                self,
                "Not connected",
                "Cannot reach the driver (socket missing).\n"
                "Is flydigi-vader4d running?",
            )
            return {"ok": False, "error": str(exc)}
        except (ConnectionError, TimeoutError, OSError) as exc:
            QMessageBox.warning(
                self,
                "Driver busy",
                f"The driver didn’t finish that request:\n{exc}",
            )
            return {"ok": False, "error": str(exc)}
        if not resp.get("ok"):
            QMessageBox.warning(self, "That didn’t work", resp.get("error", "unknown"))
        return resp

    # —— firmware ——
    @Slot()
    def _fw_check_catalog(self) -> None:
        if self._catalog.busy:
            return
        self.fw_status.setText("Checking…")
        self.fw_check_btn.setEnabled(False)
        self._catalog.start()

    @Slot(dict)
    def _fw_catalog_ok(self, cat: dict) -> None:
        self.fw_check_btn.setEnabled(True)
        ver = cat.get("version", "?")
        self.fw_catalog_label.setText(f"Latest online: {ver}")
        pad = self._fw_pad_version
        if pad and pad == ver:
            self.fw_status.setText(
                "You’re on the latest version. You can still reinstall it."
            )
        elif pad:
            self.fw_status.setText(f"Update available: {pad} → {ver}")
        else:
            self.fw_status.setText("Online check OK.")

    @Slot(str)
    def _fw_catalog_fail(self, msg: str) -> None:
        self.fw_check_btn.setEnabled(True)
        self.fw_catalog_label.setText("Latest online: couldn’t reach Flydigi")
        self.fw_status.setText(msg)

    @Slot()
    def _fw_flash(self) -> None:
        if self._fw_busy:
            return
        if usb_ota_ready() is None:
            QMessageBox.warning(
                self,
                "Not ready",
                "Plug in USB or the dongle in DInput mode (blue LED).\nBluetooth can’t flash.",
            )
            return
        if not DEFAULT_BIN.is_file():
            QMessageBox.warning(
                self, "Missing file", f"No update file at:\n{DEFAULT_BIN}"
            )
            return
        pad = self._fw_pad_version
        reply = QMessageBox.warning(
            self,
            "Install firmware?",
            f"Controller: {pad or 'unknown'}\nFile: {DEFAULT_BIN.name}\n\nKeep the cable plugged in.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._fw_busy = True
        self.fw_flash_btn.setEnabled(False)
        self.fw_check_btn.setEnabled(False)
        self.fw_progress.setValue(0)
        self.fw_status.setText("Checking connection…")
        worker = OtaWorker(DEFAULT_BIN, pad_version=pad)
        self._ota_worker = worker
        worker.progress.connect(self.fw_progress.setValue)
        worker.status.connect(self.fw_status.setText)
        worker.finished_ok.connect(self._fw_flash_ok)
        worker.failed.connect(self._fw_flash_fail)
        start_ota_thread(self, worker)

    @Slot()
    def _fw_flash_ok(self) -> None:
        self.fw_progress.setValue(100)
        self.fw_status.setText("Update finished.")
        self._fw_busy = False
        self.fw_flash_btn.setEnabled(True)
        self.fw_check_btn.setEnabled(True)

    @Slot(str)
    def _fw_flash_fail(self, msg: str) -> None:
        self.fw_status.setText(f"Update failed: {msg}")
        self._fw_busy = False
        self.fw_flash_btn.setEnabled(True)
        self.fw_check_btn.setEnabled(True)

    # —— lighting ——
    def _led_mode_value(self) -> int:
        return int(self.led_mode.currentData())

    def _push_led_preview(self) -> None:
        mode = self._led_mode_value()
        cfg = build_led(
            mode,
            r=self._color.red(),
            g=self._color.green(),
            b=self._color.blue(),
            brightness=self.led_brightness.value(),
            speed=self.led_speed.value(),
        )
        kwargs = {
            "mode": mode,
            "color": self._color,
            "brightness": self.led_brightness.value(),
            "speed": self.led_speed.value(),
            "groups": cfg.groups,
            "loop_start": cfg.loop_start,
            "loop_end": cfg.loop_end,
            "loop_time": cfg.loop_time,
        }
        self.led_preview.set_led_state(**kwargs)

    def _update_color_btn(self) -> None:
        mode = self._led_mode_value()
        uses_color = mode in _COLOR_MODES
        self.color_btn.setEnabled(uses_color)
        if mode in (0, 6):
            self.color_hint.setText("Lights are off.")
            self.color_btn.setText("—")
            self.color_btn.setStyleSheet("")
        elif mode == 1:
            self.color_hint.setText(
                "Flow uses Space Station’s rainbow chase — color picker unused."
            )
            self.color_btn.setText("rainbow")
            self.color_btn.setStyleSheet(
                "QPushButton#ColorSwatch {"
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #ff0040, stop:0.2 #ffcc00, stop:0.4 #00cc66,"
                "stop:0.6 #00aaff, stop:0.8 #6644ff, stop:1 #ff0040); color:#fff; }"
            )
        elif mode == 3:
            self.color_hint.setText(
                "Gradient fades between your color and its complement."
            )
            fg = "#000" if self._color.lightness() > 140 else "#fff"
            self.color_btn.setStyleSheet(
                f"QPushButton#ColorSwatch {{ background:{self._color.name()}; color:{fg}; }}"
            )
            self.color_btn.setText(self._color.name())
        else:
            self.color_hint.setText("This mode uses the color below.")
            fg = "#000" if self._color.lightness() > 140 else "#fff"
            self.color_btn.setStyleSheet(
                f"QPushButton#ColorSwatch {{ background:{self._color.name()}; color:{fg}; }}"
            )
            self.color_btn.setText(self._color.name())

    def _led_schedule(self, *, preview_now: bool = True) -> None:
        self._update_color_btn()
        if preview_now:
            self._led_preview_timer.stop()
            self._push_led_preview()
        else:
            # Brightness/speed: coalesce rapid slider ticks
            self._led_preview_timer.start()
        self._led_timer.start()

    @Slot()
    def _led_apply_now(self) -> None:
        if self._transport == "bluetooth":
            return
        self._rpc(
            "led_set",
            mode=self._led_mode_value(),
            r=self._color.red(),
            g=self._color.green(),
            b=self._color.blue(),
            brightness=self.led_brightness.value(),
            speed=self.led_speed.value(),
        )

    @Slot()
    def _pick_color(self) -> None:
        if self._led_mode_value() not in _COLOR_MODES:
            return
        c = QColorDialog.getColor(self._color, self, "LED color")
        if c.isValid():
            self._color = c
            self._update_color_btn()
            self._led_schedule(preview_now=True)

    def _sync_led_from_pad(self, *, quiet: bool = True) -> None:
        if self._transport == "bluetooth":
            return
        try:
            resp = self._bridge.call("led_get")
        except OSError:
            return
        if not resp.get("ok"):
            if not quiet:
                QMessageBox.warning(
                    self, "That didn’t work", resp.get("error", "unknown")
                )
            return
        led = resp["led"]
        idx = self.led_mode.findData(led["mode"])
        if idx >= 0:
            self.led_mode.blockSignals(True)
            self.led_mode.setCurrentIndex(idx)
            self.led_mode.blockSignals(False)
        self.led_brightness.blockSignals(True)
        self.led_brightness.setValue(int(led["brightness"]))
        self.led_brightness.blockSignals(False)
        # loop_time is inverted speed on the wire
        if "loop_time" in led:
            self.led_speed.blockSignals(True)
            self.led_speed.setValue(max(0, min(100, 100 - int(led["loop_time"]))))
            self.led_speed.blockSignals(False)
        c = led.get("color") or [0, 0, 0]
        if any(c):
            self._color = QColor(int(c[0]), int(c[1]), int(c[2]))
        self._update_color_btn()
        kwargs = {
            "mode": int(led["mode"]),
            "color": self._color,
            "brightness": int(led["brightness"]),
            "speed": self.led_speed.value(),
            "groups": led.get("groups"),
            "loop_start": led.get("loop_start"),
            "loop_end": led.get("loop_end"),
            "loop_time": led.get("loop_time"),
            "colors": led.get("colors") or [],
        }
        self.led_preview.set_led_state(**kwargs)

    # —— device ——
    @Slot()
    def _refresh_all(self) -> None:
        resp = self._rpc("info")
        if resp.get("ok"):
            self._on_info(resp["info"])
            self._sync_led_from_pad(quiet=False)

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        up = msg.lower().startswith("connected")
        self._set_conn(up, "Connected" if up else "Offline")
        self.chip_status.set_value("Online" if up else "Offline")
        if not up:
            self.live_pad.set_connected(False)
        self.statusBar().showMessage(msg)

    @Slot(dict)
    def _on_info(self, info: dict) -> None:
        transport = info.get("transport") or info.get("connection_type") or ""
        if transport == "bluetooth" or str(info.get("hid", "")).startswith("d7d7"):
            self._transport = "bluetooth"
            link = "Bluetooth"
        else:
            self._transport = "usb"
            link = "USB / dongle"
        fw = info.get("firmware")
        if fw:
            self._fw_pad_version = str(fw)
            self.fw_pad_label.setText(f"On this controller: {fw}")
            self.chip_fw.set_value(str(fw))
        batt = info.get("battery")
        self.chip_battery.set_value(f"{batt}%" if batt is not None else "—")
        self.chip_link.set_value(link)
        self.detail_name.setText(str(info.get("name") or "Vader 4 Pro"))
        mac = info.get("mac")
        self.detail_mac.setText(f"Serial / MAC  {mac}" if mac else "")
        self.feel_page.set_transport(self._transport)
        self.buttons_page.set_transport(self._transport)
        if self._transport == "bluetooth":
            self.detail_note.setText(
                "Playing over Bluetooth. Plug in USB or the dongle to change lighting and button maps."
            )
        else:
            self.detail_note.setText(
                "Ready for lighting, rumble, button maps, and firmware updates."
            )
            # Pull LED once on USB connect so the preview matches the pad.
            QTimer.singleShot(0, self._sync_led_from_pad)

    @Slot(dict)
    def _on_report(self, rep: dict) -> None:
        self.live_pad.set_report(rep)
        if self.feel_page.isVisible():
            self.feel_page.on_report(rep)
        if self.buttons_page.isVisible():
            self.buttons_page.on_report(rep)
