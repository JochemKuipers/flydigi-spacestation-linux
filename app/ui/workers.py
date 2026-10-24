"""Background work. Catalog uses a main-thread QObject + stdlib thread (no moveToThread)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from flydigi.ota import fetch_catalog_version, flash_bin


class CatalogFetcher(QObject):
    """Lives on the GUI thread; network runs in a daemon thread; signals are queued."""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def start(self) -> None:
        if self._busy:
            return
        self._busy = True

        def work() -> None:
            try:
                data = fetch_catalog_version()
                self.finished_ok.emit(data)
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(str(exc))
            finally:
                self._busy = False

        threading.Thread(target=work, name="catalog-fetch", daemon=True).start()


class OtaWorker(QObject):
    progress = Signal(int)
    status = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, bin_path: Path, *, pad_version: str | None) -> None:
        super().__init__()
        self._bin = bin_path
        self._pad_version = pad_version

    @Slot()
    def run(self) -> None:
        try:
            flash_bin(
                self._bin,
                on_progress=lambda pct, _i: self.progress.emit(pct),
                on_status=self.status.emit,
                preflight=True,
                pad_version=self._pad_version,
            )
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def start_ota_thread(
    parent: QObject,
    worker: OtaWorker,
) -> QThread:
    """Own the thread on ``parent``; keep ``worker`` referenced by caller."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    worker.finished_ok.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    return thread
