#!/usr/bin/env python3
"""Flydigi Space Station (Linux) — Vader 4 Pro companion entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui import MainWindow, apply_theme  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Flydigi Space Station Linux")
    app.setOrganizationName("flydigi-spacestation-linux")
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
