"""Controller art + small UI widgets (SS4 F4 overlay + LED keyframe preview)."""

from __future__ import annotations

import colorsys
import math
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

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


def _svg_pixmap(path: Path, width: int, height: int) -> QPixmap:
    from PySide6.QtGui import QImage
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(path))
    if not renderer.isValid() or width < 1 or height < 1:
        pm = QPixmap(max(1, width), max(1, height))
        pm.fill(Qt.GlobalColor.transparent)
        return pm
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    return QPixmap.fromImage(img)


def logo_pixmap(height: int = 40, _led: QColor | None = None) -> QPixmap:
    """App icon for the title bar / window icon."""
    path = _ASSETS / "vader4pro_app_icon.svg"
    return _svg_pixmap(path, height, height)


def lockup_pixmap(height: int = 56) -> QPixmap:
    """Wide brand lockup (icon + wordmark) — splash / about."""
    path = _ASSETS / "vader4pro_logo_lockup.svg"
    # Source viewBox 1400×520
    width = max(1, int(height * 1400 / 520))
    return _svg_pixmap(path, width, height)


def _norm_axis(v: int) -> float:
    return max(-1.0, min(1.0, v / 32767.0))


class LivePadView(QWidget):
    """SS4 F4 product art + official hotspots (input-overlay style)."""

    hotspot_clicked = Signal(int, str)  # key_id, ss4_name

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        show_hotspots: bool = True,
        follow_input: bool = True,
        show_led: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 180)
        self._show_hotspots = show_hotspots
        self._follow_input = follow_input
        self._show_led = show_led
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

    def _reload_body(self) -> None:
        # Hotspots are absolute px on the SS4 wireframe viewBox (508×421).
        self._body = self._render_wireframe()
        if self._body.isNull():
            self._body = QPixmap(str(_SS4 / "default_product_f4.png"))
        self._led_pts_key = None

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
        needs = self._show_led and (
            self._led_mode
            in (
                LED_STREAMLINED,
                LED_BREATHING,
                LED_GRADIENT,
                LED_FEEDBACK,
            )
            or (self._led_loop_end > self._led_loop_start)
        )
        # Preview can run smooth; pad still gets discrete firmware frames via build_led
        self._anim.setInterval(33)
        if needs and self.isVisible() and not self._anim.isActive():
            self._anim.start()
        elif (not needs or not self.isVisible()) and self._anim.isActive():
            self._anim.stop()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_anim_timer()

    def hideEvent(self, event) -> None:
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
        self._buttons = (
            {str(k).lower() for k, v in btns.items() if v}
            if isinstance(btns, dict)
            else set()
        )
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
        vb = self._cfg.get("viewBox") or {}
        return float(vb.get("width", 508)), float(vb.get("height", 421))

    def _dest(self) -> QRectF:
        """Letterboxed viewBox rect in widget pixels.

        Width/height are integers so the scaled body pixmap and LED/hotspot
        mapping share the exact same coordinate space (float truncation was
        making the V drift on resize).
        """
        vw, vh = self._vb()
        if vw <= 0 or vh <= 0 or self.width() < 1 or self.height() < 1:
            return QRectF()
        scale = min(self.width() / vw, self.height() / vh)
        dw = max(1, int(vw * scale))
        dh = max(1, int(vh * scale))
        # Keep aspect exact to viewBox (fix 1px rounding skew).
        if dw / vw < dh / vh:
            dh = max(1, int(dw * vh / vw))
        else:
            dw = max(1, int(dh * vw / vh))
        x = (self.width() - dw) // 2
        y = (self.height() - dh) // 2
        return QRectF(x, y, dw, dh)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#12141a"))
        dest = self._dest()
        if dest.isEmpty():
            return
        vw, vh = self._vb()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # One transform: body + LED + hotspots all in viewBox space — no relative drift.
        p.save()
        p.setClipRect(dest)
        p.translate(dest.left(), dest.top())
        p.scale(dest.width() / vw, dest.height() / vh)
        if not self._body.isNull():
            p.drawPixmap(QRectF(0, 0, vw, vh), self._body, QRectF(self._body.rect()))
        else:
            p.setPen(QColor("#aaa"))
            p.drawText(
                QRectF(0, 0, vw, vh),
                int(Qt.AlignmentFlag.AlignCenter),
                "Controller preview unavailable",
            )
        if self._show_led:
            self._paint_led_v(p)
        if self._show_hotspots:
            self._paint_ss4_hotspots_vb(p)
        p.restore()

        if not self._connected:
            p.fillRect(dest, QColor(20, 22, 28, 150))
            p.setPen(QColor("#c8c4bc"))
            f = QFont(self.font())
            f.setPointSize(12)
            p.setFont(f)
            p.drawText(
                dest, int(Qt.AlignmentFlag.AlignCenter), "Connect your Vader 4 Pro"
            )

    def _led_strip_points_vb(self, steps: int = 36) -> list[QPointF]:
        """Polyline in wireframe viewBox coordinates (not widget pixels)."""
        if self._led_pts_key == (0, steps) and len(self._led_pts) == steps + 1:
            return self._led_pts
        path = self._cfg.get("led_path") or []
        if len(path) < 3:
            return []
        a = QPointF(float(path[0][0]), float(path[0][1]))
        b = QPointF(float(path[1][0]), float(path[1][1]))
        c = QPointF(float(path[2][0]), float(path[2][1]))
        half = max(2, steps // 2)
        pts: list[QPointF] = []
        for i in range(half + 1):
            t = i / half
            pts.append(
                QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)
            )
        for i in range(1, half + 1):
            t = i / half
            pts.append(
                QPointF(b.x() + (c.x() - b.x()) * t, b.y() + (c.y() - b.y()) * t)
            )
        self._led_pts = pts
        self._led_pts_key = (0, steps)
        return pts

    @staticmethod
    def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> QColor:
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
        return QColor(int(r * 255), int(g * 255), int(b * 255))

    def _paint_led_v(self, p: QPainter) -> None:
        """Smooth V strip in viewBox space (painter already transformed)."""
        if self._led_mode in (0, LED_OFF, LED_CLOSE) or self._led_brightness <= 0:
            return
        pts = self._led_strip_points_vb()
        if len(pts) < 2:
            return

        bright = self._led_brightness / 100.0
        speed = max(0.05, self._led_speed / 100.0)
        t = time.monotonic()
        width = 7.5  # viewBox px; scales with the shared transform
        n = len(pts) - 1
        base = QColor(self._led)

        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(n):
            u = i / max(1, n - 1)
            if self._led_mode == LED_STREAMLINED:
                col = self._hsv((u + t * (0.12 + speed * 0.45)) % 1.0, 1.0, bright)
            elif self._led_mode == LED_GRADIENT:
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
                    (abs(self._lx) + abs(self._ly) + abs(self._rx) + abs(self._ry))
                    / 60000.0
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

    def _paint_ss4_hotspots_vb(self, p: QPainter) -> None:
        """Hotspots in viewBox space (painter already transformed)."""
        for h in self._cfg.get("hotspots") or []:
            pos = h.get("position") or {}
            size = h.get("size") or {}
            x, y = float(pos.get("x", 0)), float(pos.get("y", 0))
            w, ht = float(size.get("width", 24)), float(size.get("height", 24))
            cx = x + w / 2
            cy = y + ht / 2
            c = QPointF(cx, cy)
            rw, rh = w * 0.5, ht * 0.5
            active = self._hotspot_active(h)
            selected = (
                self._selected_id is not None
                and int(h.get("id", -1)) == self._selected_id
            )
            name = str(h.get("name") or "")

            if name in ("JsLeft", "JsRight"):
                ax = self._lx if name == "JsLeft" else self._rx
                ay = self._ly if name == "JsLeft" else self._ry
                travel = min(rw, rh) * 0.55
                c = QPointF(
                    c.x() + _norm_axis(ax) * travel, c.y() + _norm_axis(ay) * travel
                )

            p.save()
            rot = float(h.get("rotation") or 0)
            if rot:
                p.translate(c)
                p.rotate(rot)
                p.translate(-c)

            analog = name in ("Lt", "Rt")
            if selected:
                p.setPen(QPen(QColor("#ffffff"), 2))
                p.setBrush(QColor(255, 255, 255, 40))
            elif active and not analog:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(
                    QColor(self._led.red(), self._led.green(), self._led.blue(), 200)
                )
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

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        dest = self._dest()
        pt = event.position() if hasattr(event, "position") else event.localPos()
        vb_w, vb_h = self._vb()
        if dest.width() <= 0 or dest.height() <= 0:
            return
        vx = (pt.x() - dest.left()) / dest.width() * vb_w
        vy = (pt.y() - dest.top()) / dest.height() * vb_h
        # Prefer smallest hotspot containing the point (nested face buttons).
        hit: tuple[float, int, str] | None = None
        for h in self._cfg.get("hotspots") or []:
            if not h.get("clickable", True):
                continue
            pos = h.get("position") or {}
            size = h.get("size") or {}
            x, y = float(pos.get("x", 0)), float(pos.get("y", 0))
            w, ht = float(size.get("width", 0)), float(size.get("height", 0))
            if x <= vx <= x + w and y <= vy <= y + ht:
                area = max(1.0, w * ht)
                hid = int(h.get("id", -1))
                name = str(h.get("name") or "")
                if hit is None or area < hit[0]:
                    hit = (area, hid, name)
        if hit is not None:
            _area, hid, name = hit
            if 0 <= hid < 32:
                self._selected_id = hid
            self.hotspot_clicked.emit(hid, name)
            self.update()
        else:
            super().mousePressEvent(event)


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

    def paintEvent(self, _event) -> None:
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
        p.drawText(
            QRectF(14, 12, self.width() - 28, 18),
            int(Qt.AlignmentFlag.AlignLeft),
            self._label,
        )
        p.setPen(QColor("#f2f0eb"))
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(
            QRectF(14, 34, self.width() - 28, 28),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._value,
        )
