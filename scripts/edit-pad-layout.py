#!/usr/bin/env python3
"""Click-to-place hotspot editor for Vader 4 Pro overlay art.

Usage:
  python3 scripts/edit-pad-layout.py            # front
  python3 scripts/edit-pad-layout.py --face back

Controls:
  Left click     place / move the selected control
  Scroll / [ ]   previous / next control
  Click name     in the list to select
  S              save layout JSON
  R              reload JSON from disk
  1 / 2          switch front / back
  Esc / Q        quit (prompts if unsaved)

Output: app/ui/assets/pad_layout.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "ui" / "assets"
LAYOUT_PATH = ASSETS / "pad_layout.json"

# Logical controls the live UI understands (order = editor cycle order).
# Only things you can actually see/click on the front product photo.
# (Triggers aren't visible top-down — live UI can infer LT/RT meters near lb/rb.)
FRONT_KEYS = [
    "ls",
    "rs",
    "dpad",
    "y",
    "x",
    "b",
    "a",
    "c",
    "z",
    "select",
    "start",
    "guide",
    "lb",
    "rb",
    "led_l",
    "led_apex",
    "led_r",
]
BACK_KEYS = ["m1", "m2", "m3", "m4", "mode"]

DEFAULTS = {
    "version": 1,
    "front": {
        "image": "vader4_front.png",
        "width": 1000,
        "height": 708,
        "stick_travel": 36,
        "points": {},
    },
    "back": {
        "image": "vader4_back.png",
        "width": 1000,
        "height": 680,
        "points": {},
    },
}


def load_layout() -> dict:
    if LAYOUT_PATH.is_file():
        data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
        # merge missing shells
        for face in ("front", "back"):
            data.setdefault(face, DEFAULTS[face].copy())
            data[face].setdefault("points", {})
            data[face].setdefault("image", DEFAULTS[face]["image"])
        return data
    return json.loads(json.dumps(DEFAULTS))


def save_layout(data: dict) -> None:
    LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class Canvas(QWidget):
    def __init__(self, on_place) -> None:
        super().__init__()
        self._on_place = on_place
        self._pm = QPixmap()
        self._points: dict[str, list[float]] = {}
        self._active = ""
        self._keys: list[str] = []
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self._hover: QPointF | None = None

    def set_face(self, pixmap: QPixmap, points: dict, keys: list[str], active: str) -> None:
        self._pm = pixmap
        self._points = points
        self._keys = keys
        self._active = active
        self.update()
        self.updateGeometry()

    def set_active(self, key: str) -> None:
        self._active = key
        self.update()

    def sizeHint(self):  # noqa: N802
        if self._pm.isNull():
            return super().sizeHint()
        return self._pm.size()

    def _dest(self) -> QRectF:
        if self._pm.isNull():
            return QRectF(self.rect())
        iw, ih = self._pm.width(), self._pm.height()
        scale = min(self.width() / iw, self.height() / ih)
        dw, dh = iw * scale, ih * scale
        return QRectF((self.width() - dw) / 2, (self.height() - dh) / 2, dw, dh)

    def _to_image(self, pos) -> tuple[float, float] | None:
        dest = self._dest()
        if not dest.contains(pos):
            return None
        x = (pos.x() - dest.left()) / dest.width() * self._pm.width()
        y = (pos.y() - dest.top()) / dest.height() * self._pm.height()
        return x, y

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._active:
            return
        pt = self._to_image(event.position())
        if pt is None:
            return
        self._on_place(self._active, pt[0], pt[1])

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._hover = event.position()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#12141a"))
        if self._pm.isNull():
            p.setPen(QColor("#aaa"))
            p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), "Missing body PNG")
            return
        dest = self._dest()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(dest.toRect(), self._pm)

        scale = dest.width() / self._pm.width()
        font = QFont(self.font())
        font.setPointSize(9)
        p.setFont(font)

        for key, xy in self._points.items():
            if key not in self._keys:
                continue
            cx = dest.left() + xy[0] * scale
            cy = dest.top() + xy[1] * scale
            active = key == self._active
            color = QColor("#4cff8a") if active else QColor("#ffcc33")
            r = 10 if active else 7
            p.setPen(QPen(color, 2))
            p.setBrush(QColor(color.red(), color.green(), color.blue(), 60))
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(color)
            p.drawText(int(cx + r + 3), int(cy + 4), key)

        if self._hover is not None:
            img = self._to_image(self._hover)
            if img is not None:
                p.setPen(QColor("#8899aa"))
                p.drawText(8, self.height() - 10, f"{img[0]:.0f}, {img[1]:.0f}   active={self._active or '—'}")


class Editor(QMainWindow):
    def __init__(self, face: str = "front") -> None:
        super().__init__()
        self.setWindowTitle("Vader 4 Pro — pad layout editor")
        self.resize(1100, 780)
        self._data = load_layout()
        self._face = face if face in ("front", "back") else "front"
        self._dirty = False
        self._pix: dict[str, QPixmap] = {}

        root = QWidget()
        self.setCentralWidget(root)
        row = QHBoxLayout(root)

        self.canvas = Canvas(self._place)
        row.addWidget(self.canvas, stretch=1)

        side = QVBoxLayout()
        self.face_label = QLabel()
        self.face_label.setObjectName("Muted")
        side.addWidget(self.face_label)

        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._select)
        side.addWidget(self.list, stretch=1)

        hint = QLabel(
            "Click the image to place the selected control.\n"
            "[ ] or scroll list · S save · R reload · 1/2 face"
        )
        hint.setWordWrap(True)
        side.addWidget(hint)

        btn_row = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._reload)
        front_btn = QPushButton("Front")
        front_btn.clicked.connect(lambda: self._set_face("front"))
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self._set_face("back"))
        for b in (save, reload_btn, front_btn, back_btn):
            btn_row.addWidget(b)
        side.addLayout(btn_row)
        row.addLayout(side)

        QShortcut(QKeySequence("S"), self, activated=self._save)
        QShortcut(QKeySequence("R"), self, activated=self._reload)
        QShortcut(QKeySequence("1"), self, activated=lambda: self._set_face("front"))
        QShortcut(QKeySequence("2"), self, activated=lambda: self._set_face("back"))
        QShortcut(QKeySequence("["), self, activated=lambda: self._cycle(-1))
        QShortcut(QKeySequence("]"), self, activated=lambda: self._cycle(1))
        QShortcut(QKeySequence("Q"), self, activated=self.close)
        QShortcut(QKeySequence("Esc"), self, activated=self.close)

        self._set_face(self._face)

    def _keys(self) -> list[str]:
        return FRONT_KEYS if self._face == "front" else BACK_KEYS

    def _face_data(self) -> dict:
        return self._data[self._face]

    def _load_pix(self, face: str) -> QPixmap:
        if face in self._pix:
            return self._pix[face]
        path = ASSETS / self._data[face]["image"]
        pm = QPixmap(str(path))
        if pm.isNull():
            QMessageBox.warning(self, "Missing image", f"No file at:\n{path}")
        else:
            self._data[face]["width"] = pm.width()
            self._data[face]["height"] = pm.height()
        self._pix[face] = pm
        return pm

    def _set_face(self, face: str) -> None:
        self._face = face
        keys = self._keys()
        self.list.blockSignals(True)
        self.list.clear()
        pts = self._face_data()["points"]
        for k in keys:
            mark = "●" if k in pts else "○"
            QListWidgetItem(f"{mark}  {k}", self.list)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.face_label.setText(f"Editing: {face}  →  {LAYOUT_PATH.name}")
        self._refresh_canvas()

    def _refresh_canvas(self) -> None:
        active = self.list.currentItem().text().split()[-1] if self.list.currentItem() else ""
        self.canvas.set_face(
            self._load_pix(self._face),
            self._face_data()["points"],
            self._keys(),
            active,
        )
        # refresh bullets
        pts = self._face_data()["points"]
        for i, k in enumerate(self._keys()):
            mark = "●" if k in pts else "○"
            self.list.item(i).setText(f"{mark}  {k}")

    def _select(self, text: str) -> None:
        if not text:
            return
        key = text.split()[-1]
        self.canvas.set_active(key)

    def _cycle(self, delta: int) -> None:
        n = self.list.count()
        if not n:
            return
        self.list.setCurrentRow((self.list.currentRow() + delta) % n)

    def _place(self, key: str, x: float, y: float) -> None:
        self._face_data()["points"][key] = [round(x, 1), round(y, 1)]
        self._dirty = True
        self._refresh_canvas()
        # auto-advance
        keys = self._keys()
        if key in keys:
            idx = keys.index(key)
            if idx + 1 < len(keys):
                self.list.setCurrentRow(idx + 1)

    def _save(self) -> None:
        save_layout(self._data)
        self._dirty = False
        self.statusBar().showMessage(f"Saved {LAYOUT_PATH}", 3000)
        print(f"saved {LAYOUT_PATH}")

    def _reload(self) -> None:
        self._data = load_layout()
        self._pix.clear()
        self._dirty = False
        self._set_face(self._face)
        self.statusBar().showMessage("Reloaded", 2000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._dirty:
            r = QMessageBox.question(
                self,
                "Unsaved changes",
                "Save before quitting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if r == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if r == QMessageBox.StandardButton.Save:
                self._save()
        super().closeEvent(event)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--face", choices=("front", "back"), default="front")
    args = ap.parse_args()
    app = QApplication(sys.argv)
    w = Editor(face=args.face)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
