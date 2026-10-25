"""Structured Vader 4 Pro manual — curated from the official image PDF."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_ASSETS = Path(__file__).resolve().parent / "assets"
_MANUAL_DIR = _ASSETS / "manual"


@lru_cache(maxsize=1)
def load_manual() -> dict[str, Any]:
    path = _MANUAL_DIR / "content.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _pdf_path(data: dict[str, Any]) -> Path:
    rel = data.get("pdf") or "../vader4_pro_manual.pdf"
    return (_MANUAL_DIR / rel).resolve()


class ManualView(QWidget):
    """Sectioned manual with a link back to the official Flydigi PDF / site."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = load_manual()
        self._sections: list[dict[str, Any]] = list(self._data.get("sections") or [])

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)

        self._nav = QListWidget()
        self._nav.setObjectName("ManualNav")
        self._nav.setFixedWidth(168)
        self._nav.setSpacing(2)
        for sec in self._sections:
            QListWidgetItem(str(sec.get("title") or sec.get("id")), self._nav)

        self._stack = QStackedWidget()
        for sec in self._sections:
            self._stack.addWidget(self._build_section(sec))

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        if self._nav.count():
            self._nav.setCurrentRow(0)

        body.addWidget(self._nav)
        body.addWidget(self._stack, stretch=1)
        root.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        official = QPushButton("Official manual online")
        official.setObjectName("Primary")
        official.clicked.connect(self._open_official)
        pdf_btn = QPushButton("Open bundled PDF")
        pdf_btn.clicked.connect(self._open_pdf)
        tip = QLabel(
            "Extracted from Flydigi’s PDF — online copy wins if anything disagrees."
        )
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        footer.addWidget(official)
        footer.addWidget(pdf_btn)
        footer.addWidget(tip, stretch=1)
        root.addLayout(footer)

    def _open_official(self) -> None:
        url = str(self._data.get("official_url") or self._data.get("qr_url") or "")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _open_pdf(self) -> None:
        pdf = _pdf_path(self._data)
        if pdf.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf)))

    def _build_section(self, sec: dict[str, Any]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        page.setObjectName("ManualPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 0, 12, 16)
        lay.setSpacing(12)

        for block in sec.get("blocks") or []:
            w = self._block_widget(block)
            if w is not None:
                lay.addWidget(w)
        lay.addStretch(1)

        scroll.setWidget(page)
        return scroll

    def _block_widget(self, block: dict[str, Any]) -> QWidget | None:
        kind = str(block.get("type") or "")
        if kind == "heading":
            lab = QLabel(str(block.get("text") or ""))
            lab.setObjectName("ManualHeading")
            lab.setWordWrap(True)
            return lab
        if kind == "para":
            lab = QLabel(str(block.get("text") or ""))
            lab.setObjectName("ManualBody")
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return lab
        if kind == "note":
            card = QFrame()
            card.setObjectName("ManualNote")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            title = QLabel("Note")
            title.setObjectName("ManualNoteTitle")
            body = QLabel(str(block.get("text") or ""))
            body.setObjectName("ManualBody")
            body.setWordWrap(True)
            cl.addWidget(title)
            cl.addWidget(body)
            return card
        if kind == "bullets":
            items = block.get("items") or []
            lab = QLabel("\n".join(f"• {x}" for x in items))
            lab.setObjectName("ManualBody")
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return lab
        if kind == "steps":
            card = QFrame()
            card.setObjectName("ManualCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(8)
            for i, step in enumerate(block.get("items") or [], start=1):
                row = QHBoxLayout()
                num = QLabel(str(i))
                num.setObjectName("ManualStepNum")
                num.setFixedSize(24, 24)
                num.setAlignment(Qt.AlignmentFlag.AlignCenter)
                text = QLabel(str(step))
                text.setObjectName("ManualBody")
                text.setWordWrap(True)
                row.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
                row.addWidget(text, stretch=1)
                cl.addLayout(row)
            return card
        if kind == "kv":
            card = QFrame()
            card.setObjectName("ManualCard")
            grid = QGridLayout(card)
            grid.setContentsMargins(14, 12, 14, 12)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(8)
            for r, pair in enumerate(block.get("rows") or []):
                if len(pair) < 2:
                    continue
                k = QLabel(str(pair[0]))
                k.setObjectName("ManualKey")
                v = QLabel(str(pair[1]))
                v.setObjectName("ManualBody")
                v.setWordWrap(True)
                grid.addWidget(k, r, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(v, r, 1)
            grid.setColumnStretch(1, 1)
            return card
        if kind == "table":
            card = QFrame()
            card.setObjectName("ManualCard")
            grid = QGridLayout(card)
            grid.setContentsMargins(14, 12, 14, 12)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            headers = list(block.get("headers") or [])
            for c, h in enumerate(headers):
                lab = QLabel(str(h))
                lab.setObjectName("ManualKey")
                grid.addWidget(lab, 0, c)
            for r, row in enumerate(block.get("rows") or [], start=1):
                for c, cell in enumerate(row):
                    lab = QLabel(str(cell))
                    lab.setObjectName("ManualBody")
                    lab.setWordWrap(True)
                    grid.addWidget(lab, r, c)
            return card
        if kind == "cards":
            wrap = QWidget()
            grid = QGridLayout(wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            items = list(block.get("items") or [])
            for i, item in enumerate(items):
                card = QFrame()
                card.setObjectName("ManualCard")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(12, 10, 12, 10)
                t = QLabel(str(item.get("title") or ""))
                t.setObjectName("ManualCardTitle")
                b = QLabel(str(item.get("text") or ""))
                b.setObjectName("ManualBody")
                b.setWordWrap(True)
                cl.addWidget(t)
                cl.addWidget(b)
                grid.addWidget(card, i // 2, i % 2)
            return wrap
        if kind == "qa":
            card = QFrame()
            card.setObjectName("ManualCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            q = QLabel(f"Q: {block.get('q') or ''}")
            q.setObjectName("ManualCardTitle")
            q.setWordWrap(True)
            a = QLabel(f"A: {block.get('a') or ''}")
            a.setObjectName("ManualBody")
            a.setWordWrap(True)
            a.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cl.addWidget(q)
            cl.addWidget(a)
            return card
        if kind == "image":
            src = str(block.get("src") or "")
            path = _MANUAL_DIR / src
            lab = QLabel()
            lab.setObjectName("ManualImage")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            if path.is_file():
                # Native PDF embeds are ~1240px JPEG pages — never upscale past 1× DPR
                pm = QPixmap(str(path))
                dpr = max(1.0, float(lab.devicePixelRatio()))
                max_w = int(min(640, pm.width() / dpr))
                target_w = int(max_w * dpr)
                if pm.width() > target_w:
                    pm = pm.scaledToWidth(
                        target_w, Qt.TransformationMode.SmoothTransformation
                    )
                pm.setDevicePixelRatio(dpr)
                lab.setPixmap(pm)
                lab.setToolTip(str(block.get("alt") or src))
            else:
                lab.setText(str(block.get("alt") or src))
                lab.setObjectName("Muted")
            return lab
        return None
