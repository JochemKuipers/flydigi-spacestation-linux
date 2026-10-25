#!/usr/bin/env python3
"""Vader 4 Pro companion for Linux — app entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.ui import MainWindow, apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vader 4 Pro")
    app.setOrganizationName("flydigi")
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
