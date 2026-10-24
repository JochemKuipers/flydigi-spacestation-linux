"""Controller art + small UI widgets (SS4 F4 overlay + LED keyframe preview)."""

from __future__ import annotations

import colorsys
import math
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QLabel, QWidget

from flydigi.dinput_proto import build_led
from flydigi.ss4_f4 import assets_dir, load_device_config, report_name

from .labels import overlay_label

# Match flydigi.dinput_proto.LedConfig modes (Close/off is 6 in SS)
LED_OFF = 6
LED_STREAMLINED = 1  # Flow — moving rainbow
LED_BREATHING = 2
LED_GRADIENT = 3  # 2-color fade
LED_FEEDBACK = 4
LED_STEADY = 5
LED_CLOSE = 6

_ASSETS = Path(__file__).resolve().parent / "assets"
_SS4 = assets_dir()


def logo_pixmap(height: int = 36, led: QColor | None = None) -> QPixmap:
    """Title-bar glyph from the SS4 F4 product art."""
    src = QPixmap(str(_SS4 / "default_product_f4.png"))
    if src.isNull():
        src = QPixmap(str(_ASSETS / "vader4_front.png"))
    if src.isNull():
        pm = QPixmap(height, height)
        pm.fill(Qt.GlobalColor.transparent)
        return pm
    w, h = src.width(), src.height()
    crop = src.copy(int(w * 0.28), int(h * 0.02), int(w * 0.44), int(h * 0.35))
    out_w = int(height * crop.width() / max(1, crop.height()))
    pm = crop.scaled(
        out_w, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    if led is not None:
        painted = QPixmap(pm)
        p = QPainter(painted)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(led), max(2.0, height * 0.08))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        mid = pm.width() / 2
        p.drawPolyline(
            QPolygonF(
                [
                    QPointF(mid - height * 0.35, height * 0.25),
                    QPointF(mid, height * 0.75),
                    QPointF(mid + height * 0.35, height * 0.25),
                ]
            )
        )
        p.end()
        return painted
    return pm


def _norm_axis(v: int) -> float:
    return max(-1.0, min(1.0, v / 32767.0))


class LivePadView(QWidget):
    """SS4 F4 product art + official hotspots (input-overlay style)."""

    hotspot_clicked = Signal(int, str)  # key_id, ss4_name

    def __init__(
        self,
        face: str = "front",
        parent: QWidget | None = None,
        *,
        show_hotspots: bool = True,
        follow_input: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 300)
        self._face = face
        self._show_hotspots = show_hotspots
        self._follow_input = follow_input
        self._lx = self._ly = self._rx = self._ry = 0
        self._lt = self._rt = 0
        self._buttons: set[str] = set()
        self._hat = (0, 0)
        self._connected = False
        self._led = QColor("#4c8dff")
        self._led_mode = LED_STEADY
        self._led_brightness = 80
        self._led_speed = 50
        self._led_cfg_groups: list[list[tuple[int, int, int]]] = []
        self._led_loop_start = 0
        self._led_loop_end = 0
        self._led_loop_time = 50
        self._cfg = load_device_config()
        self._body = QPixmap()
        self._body_scaled = QPixmap()
        self._body_scaled_key: tuple[int, int] | None = None
        self._led_pts_key: tuple[int, int] | None = None
        self._led_pts: list[QPointF] = []
        self._selected_id: int | None = None
        self._anim = QTimer(self)
        self._anim.setInterval(33)  # ~30fps smooth preview (SS-style)
        self._anim.timeout.connect(self.update)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._reload_body()
        self._rebuild_led_frames()
        self._sync_anim_timer()

    def reload_layout(self) -> None:
        load_device_config.cache_clear()
        self._cfg = load_device_config()
        self._reload_body()
        self.update()

    def set_face(self, face: str) -> None:
        # SS4 F4 overlay is front-only; back keeps legacy photo if present
        if face not in ("front", "back"):
            return
        self._face = face
        self._reload_body()
        self.update()

    def _reload_body(self) -> None:
        self._body_scaled = QPixmap()
        self._body_scaled_key = None
        if self._face == "back":
            path = _ASSETS / "vader4_back.png"
            self._body = QPixmap(str(path))
            return
        # SS4 hotspots are absolute px on the wireframe SVG viewBox (508×421),
        # not on default_product_f4.png — same pairing as DeviceWireframe in SS4.
        self._body = self._render_wireframe()
        if self._body.isNull():
            # last resort: photo (hotspots will be wrong)
            self._body = QPixmap(str(_SS4 / "default_product_f4.png"))

    def _render_wireframe(self) -> QPixmap:
        from PySide6.QtGui import QImage
        from PySide6.QtSvg import QSvgRenderer

        vb = self._cfg.get("viewBox") or {}
        w = int(vb.get("width", 508))
        h = int(vb.get("height", 421))
        svg_path = _SS4 / "device_wireframe_f4.svg"
        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return QPixmap()
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("#12141a"))
        painter = QPainter(img)
        renderer.render(painter, QRectF(0, 0, w, h))
        painter.end()
        return QPixmap.fromImage(img)

    def set_led_color(self, color: QColor) -> None:
        self._led = QColor(color)
        self._rebuild_led_frames()
        self.update()

    def set_led_state(
        self,
        *,
        mode: int | None = None,
        color: QColor | None = None,
        brightness: int | None = None,
        speed: int | None = None,
        colors: list | None = None,
        groups: list | None = None,
        loop_start: int | None = None,
        loop_end: int | None = None,
        loop_time: int | None = None,
    ) -> None:
        if mode is not None:
            self._led_mode = int(mode)
        if color is not None:
            self._led = QColor(color)
        if brightness is not None:
            self._led_brightness = max(0, min(100, int(brightness)))
        if speed is not None:
            self._led_speed = max(0, min(100, int(speed)))
        if groups is not None:
            self._led_cfg_groups = [
                [tuple(int(x) for x in unit[:3]) for unit in (g or [])]  # type: ignore[misc]
                for g in groups
            ]
            if loop_start is not None:
                self._led_loop_start = int(loop_start)
            if loop_end is not None:
                self._led_loop_end = int(loop_end)
            if loop_time is not None:
                self._led_loop_time = max(1, int(loop_time))
        else:
            self._rebuild_led_frames()
        self._sync_anim_timer()
        self.update()

    def _rebuild_led_frames(self) -> None:
        cfg = build_led(
            self._led_mode,
            r=self._led.red(),
            g=self._led.green(),
            b=self._led.blue(),
            brightness=self._led_brightness,
            speed=self._led_speed,
        )
        self._led_cfg_groups = cfg.groups
        self._led_loop_start = cfg.loop_start
        self._led_loop_end = cfg.loop_end
        self._led_loop_time = max(1, cfg.loop_time)

    def _sync_anim_timer(self) -> None:
        needs = self._led_mode in (
            LED_STREAMLINED,
            LED_BREATHING,
            LED_GRADIENT,
            LED_FEEDBACK,
        ) or (self._led_loop_end > self._led_loop_start)
        # Preview can run smooth; pad still gets discrete firmware frames via build_led
        self._anim.setInterval(33)
        if needs and self.isVisible() and not self._anim.isActive():
            self._anim.start()
        elif (not needs or not self.isVisible()) and self._anim.isActive():
            self._anim.stop()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_anim_timer()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._anim.isActive():
            self._anim.stop()

    def set_connected(self, ok: bool) -> None:
        self._connected = ok
        self.update()

    def set_selected_key(self, key_id: int | None) -> None:
        self._selected_id = key_id
        self.update()

    def set_report(self, rep: dict) -> None:
        if not self._follow_input:
            return
        self._lx = int(rep.get("lx", 0))
        self._ly = int(rep.get("ly", 0))
        self._rx = int(rep.get("rx", 0))
        self._ry = int(rep.get("ry", 0))
        self._lt = int(rep.get("lt", 0))
        self._rt = int(rep.get("rt", 0))
        self._hat = (int(rep.get("hat_x", 0)), int(rep.get("hat_y", 0)))
        btns = rep.get("buttons") or {}
        self._buttons = {str(k).lower() for k, v in btns.items() if v} if isinstance(btns, dict) else set()
        hx, hy = self._hat
        if hy < 0:
            self._buttons.add("hat_up")
        if hy > 0:
            self._buttons.add("hat_down")
        if hx > 0:
            self._buttons.add("hat_right")
        if hx < 0:
            self._buttons.add("hat_left")
        self._connected = True
        # Input overlay only — LED animation has its own timer
        if self._show_hotspots and self.isVisible():
            self.update()

    def _vb(self) -> tuple[float, float]:
        if self._face == "back" and not self._body.isNull():
            return float(self._body.width()), float(self._body.height())
        vb = self._cfg.get("viewBox") or {}
        return float(vb.get("width", 508)), float(vb.get("height", 421))

    def _dest(self) -> QRectF:
        vw, vh = self._vb()
        scale = min(self.width() / vw, self.height() / vh)
        dw, dh = vw * scale, vh * scale
        return QRectF((self.width() - dw) / 2, (self.height() - dh) / 2, dw, dh)

    def _map_vb(self, x: float, y: float, dest: QRectF) -> QPointF:
        """Map wireframe viewBox px → widget (1:1 with SS4 absolute hotspot layout)."""
        vw, vh = self._vb()
        return QPointF(dest.left() + x / vw * dest.width(), dest.top() + y / vh * dest.height())

    def _r(self, dest: QRectF, n: float) -> float:
        return n * dest.width() / self._vb()[0]

    def _scaled_body(self, dest: QRectF) -> QPixmap:
        key = (int(dest.width()), int(dest.height()))
        if self._body_scaled_key == key and not self._body_scaled.isNull():
            return self._body_scaled
        if self._body.isNull() or key[0] < 1 or key[1] < 1:
            return QPixmap()
        self._body_scaled = self._body.scaled(
            key[0],
            key[1],
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._body_scaled_key = key
        return self._body_scaled

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#12141a"))
        dest = self._dest()
        body = self._scaled_body(dest)
        if not body.isNull():
            p.drawPixmap(dest.topLeft(), body)
        else:
            p.setPen(QColor("#aaa"))
            p.drawText(dest, int(Qt.AlignmentFlag.AlignCenter), "Missing SS4 F4 product art")

        if self._face == "front":
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setClipRect(dest)
            self._paint_led_v(p, dest)
            if self._show_hotspots:
                self._paint_ss4_hotspots(p, dest)
            p.setClipping(False)

        if not self._connected:
            p.fillRect(dest, QColor(20, 22, 28, 150))
            p.setPen(QColor("#c8c4bc"))
            f = QFont(self.font())
            f.setPointSize(12)
            p.setFont(f)
            p.drawText(dest, int(Qt.AlignmentFlag.AlignCenter), "Connect your Vader 4 Pro")

    def _led_strip_points(self, dest: QRectF, steps: int = 36) -> list[QPointF]:
        """Dense polyline along the V — continuous light bar, not discrete LEDs."""
        key = (int(dest.width()), int(dest.height()))
        if self._led_pts_key == key and len(self._led_pts) == steps + 1:
            return self._led_pts
        path = self._cfg.get("led_path") or []
        if len(path) < 3:
            return []
        a = self._map_vb(float(path[0][0]), float(path[0][1]), dest)
        b = self._map_vb(float(path[1][0]), float(path[1][1]), dest)
        c = self._map_vb(float(path[2][0]), float(path[2][1]), dest)
        half = max(2, steps // 2)
        pts: list[QPointF] = []
        for i in range(half + 1):
            t = i / half
            pts.append(QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t))
        for i in range(1, half + 1):
            t = i / half
            pts.append(QPointF(b.x() + (c.x() - b.x()) * t, b.y() + (c.y() - b.y()) * t))
        self._led_pts = pts
        self._led_pts_key = key
        return pts

    @staticmethod
    def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> QColor:
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
        return QColor(int(r * 255), int(g * 255), int(b * 255))

    def _paint_led_v(self, p: QPainter, dest: QRectF) -> None:
        """Smooth continuous V strip (preview). Pad still uses firmware keyframes."""
        if self._led_mode in (0, LED_OFF, LED_CLOSE) or self._led_brightness <= 0:
            return
        pts = self._led_strip_points(dest)
        if len(pts) < 2:
            return

        bright = self._led_brightness / 100.0
        speed = max(0.05, self._led_speed / 100.0)
        t = time.monotonic()
        width = max(4.0, self._r(dest, 7.5))
        n = len(pts) - 1
        base = QColor(self._led)

        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(n):
            u = i / max(1, n - 1)
            if self._led_mode == LED_STREAMLINED:
                # Flow: moving rainbow chase (matches SS ledUnits table on the pad)
                col = self._hsv((u + t * (0.12 + speed * 0.45)) % 1.0, 1.0, bright)
            elif self._led_mode == LED_GRADIENT:
                # Gradient: fade between color and complement
                pulse = 0.5 + 0.5 * math.sin(t * (1.0 + speed * 2.5))
                c2 = QColor(255 - base.red(), 255 - base.green(), 255 - base.blue())
                col = QColor(
                    int((base.red() * (1 - pulse) + c2.red() * pulse) * bright),
                    int((base.green() * (1 - pulse) + c2.green() * pulse) * bright),
                    int((base.blue() * (1 - pulse) + c2.blue() * pulse) * bright),
                )
            elif self._led_mode == LED_BREATHING:
                pulse = 0.22 + 0.78 * (0.5 + 0.5 * math.sin(t * (1.1 + speed * 3.2)))
                col = QColor(
                    int(base.red() * pulse * bright),
                    int(base.green() * pulse * bright),
                    int(base.blue() * pulse * bright),
                )
            elif self._led_mode == LED_FEEDBACK:
                energy = min(
                    1.0,
                    (abs(self._lx) + abs(self._ly) + abs(self._rx) + abs(self._ry)) / 60000.0
                    + (0.35 if self._buttons else 0.0)
                    + self._lt / 400.0
                    + self._rt / 400.0,
                )
                k = 0.18 + 0.82 * energy
                col = QColor(
                    int(base.red() * k * bright),
                    int(base.green() * k * bright),
                    int(base.blue() * k * bright),
                )
            else:
                col = QColor(
                    int(base.red() * bright),
                    int(base.green() * bright),
                    int(base.blue() * bright),
                )
            pen = QPen(col, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(pts[i], pts[i + 1])

    def _hotspot_active(self, h: dict) -> bool:
        name = str(h.get("name") or "")
        rep = report_name(name)
        if not rep:
            return False
        if rep == "lt":
            return self._lt > 8
        if rep == "rt":
            return self._rt > 8
        if name == "Thl":
            return "ls" in self._buttons
        if name == "Thr":
            return "rs" in self._buttons
        return rep in self._buttons

    def _paint_ss4_hotspots(self, p: QPainter, dest: QRectF) -> None:
        for h in self._cfg.get("hotspots") or []:
            pos = h.get("position") or {}
            size = h.get("size") or {}
            x, y = float(pos.get("x", 0)), float(pos.get("y", 0))
            w, ht = float(size.get("width", 24)), float(size.get("height", 24))
            # SS4: left/top/width/height in viewBox px on the wireframe
            cx = x + w / 2
            cy = y + ht / 2
            c = self._map_vb(cx, cy, dest)
            rw = self._r(dest, w * 0.5)
            rh = self._r(dest, ht * 0.5)
            active = self._hotspot_active(h)
            selected = self._selected_id is not None and int(h.get("id", -1)) == self._selected_id
            name = str(h.get("name") or "")

            if name in ("JsLeft", "JsRight"):
                ax = self._lx if name == "JsLeft" else self._rx
                ay = self._ly if name == "JsLeft" else self._ry
                travel = min(rw, rh) * 0.55
                c = QPointF(c.x() + _norm_axis(ax) * travel, c.y() + _norm_axis(ay) * travel)

            p.save()
            rot = float(h.get("rotation") or 0)
            if rot:
                p.translate(c)
                p.rotate(rot)
                p.translate(-c)

            # LT/RT use analog fill only — skip solid “pressed” background
            analog = name in ("Lt", "Rt")
            if selected:
                p.setPen(QPen(QColor("#ffffff"), 2))
                p.setBrush(QColor(255, 255, 255, 40))
            elif active and not analog:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self._led.red(), self._led.green(), self._led.blue(), 200))
            else:
                p.setPen(QPen(QColor(255, 255, 255, 35), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)

            shape = h.get("shape") or "circle"
            box = QRectF(c.x() - rw, c.y() - rh, rw * 2, rh * 2)
            if shape == "circle":
                p.drawEllipse(c, rw, rh)
            else:
                p.drawRoundedRect(box, 4, 4)

            if name == "Lt" and self._lt > 0:
                self._trigger_fill(p, box, self._lt / 255.0)
            elif name == "Rt" and self._rt > 0:
                self._trigger_fill(p, box, self._rt / 255.0)

            text = overlay_label(name)
            if text:
                p.setPen(QColor("#e8e6e1"))
                f = QFont(self.font())
                # Fit single word inside the hotspot; Select/Start are long thin rotated pills
                if name in ("Select", "Start"):
                    f.setPointSizeF(max(6.0, min(9.0, rh * 1.1)))
                    f.setBold(True)
                elif len(text) <= 2:
                    f.setPointSizeF(max(7.0, min(11.0, min(rw, rh) * 0.85)))
                    f.setBold(True)
                else:
                    f.setPointSizeF(max(6.0, min(9.0, min(rw, rh) * 0.55)))
                p.setFont(f)
                p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)
            p.restore()

    def _trigger_fill(self, p: QPainter, box: QRectF, amt: float) -> None:
        """Fill the whole trigger hotspot from the bottom up."""
        amt = max(0.0, min(1.0, amt))
        if amt <= 0.01:
            return
        h = box.height() * amt
        fill = QRectF(box.left(), box.bottom() - h, box.width(), h)
        p.setPen(Qt.PenStyle.NoPen)
        col = QColor(self._led)
        col.setAlpha(210)
        p.setBrush(col)
        p.setClipRect(box)
        p.drawRoundedRect(fill, 4, 4)
        p.setClipping(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._face != "front" or event.button() != Qt.MouseButton.LeftButton:
            return
        dest = self._dest()
        pt = event.position() if hasattr(event, "position") else event.localPos()
        vb_w, vb_h = self._vb()
        if dest.width() <= 0 or dest.height() <= 0:
            return
        vx = (pt.x() - dest.left()) / dest.width() * vb_w
        vy = (pt.y() - dest.top()) / dest.height() * vb_h
        for h in self._cfg.get("hotspots") or []:
            if not h.get("clickable", True):
                continue
            pos = h.get("position") or {}
            size = h.get("size") or {}
            x, y = float(pos.get("x", 0)), float(pos.get("y", 0))
            w, ht = float(size.get("width", 0)), float(size.get("height", 0))
            if x <= vx <= x + w and y <= vy <= y + ht:
                hid = int(h.get("id", -1))
                name = str(h.get("name") or "")
                self._selected_id = hid if hid < 32 else self._selected_id
                self.hotspot_clicked.emit(hid, name)
                self.update()
                break


class StatChip(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._value = "—"
        self.setMinimumHeight(72)
        self.setMinimumWidth(120)

    def set_value(self, value: str) -> None:
        self._value = value
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor("#343842"), 1))
        p.setBrush(QColor("#1e2128"))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor("#9a958c"))
        f = QFont(self.font())
        f.setPointSize(10)
        p.setFont(f)
        p.drawText(QRectF(14, 12, self.width() - 28, 18), int(Qt.AlignmentFlag.AlignLeft), self._label)
        p.setPen(QColor("#f2f0eb"))
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(
            QRectF(14, 34, self.width() - 28, 28),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._value,
        )


class ManualView(QWidget):
    """Official Vader 4 Pro manual (bundled PDF)."""

    MANUAL_URL = "https://shops.flydigi.com/pages/flydigi-vader-4-pro-gaming-controller-user-manual"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        tip = QLabel(
            "Official Flydigi Vader 4 Pro manual. "
            f'<a href="{self.MANUAL_URL}">Open on flydigi.com</a>'
        )
        tip.setObjectName("Muted")
        tip.setOpenExternalLinks(True)
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self._doc = QPdfDocument(self)
        pdf = _ASSETS / "vader4_pro_manual.pdf"
        if pdf.is_file():
            self._doc.load(str(pdf))
        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        lay.addWidget(self._view, stretch=1)

        row = QHBoxLayout()
        open_btn = QPushButton("Open PDF externally")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf))))
        web_btn = QPushButton("Manual on website")
        web_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.MANUAL_URL)))
        row.addWidget(open_btn)
        row.addWidget(web_btn)
        row.addStretch()
        lay.addLayout(row)
