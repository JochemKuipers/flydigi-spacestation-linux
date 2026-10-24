from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

_QSS = Path(__file__).with_name("theme.qss")


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_QSS.read_text(encoding="utf-8"))
