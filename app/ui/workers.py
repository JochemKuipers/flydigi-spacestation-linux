"""Background work. Catalog / RPC use a main-thread QObject + stdlib thread."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from flydigi.ipc import DaemonClient
from flydigi.ota import (
    fetch_catalog_version,
    flash_bin,
    looks_like_ota_stuck_error,
    recover_firmware_update_mode,
    usb_ota_ready,
)


class BackgroundRpc(QObject):
    """Run a callable off the GUI thread; deliver result via queued signals."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def run(self, fn: Callable[[], Any], *, name: str = "bg-rpc") -> None:
        if self._busy:
            return
        self._busy = True

        def work() -> None:
            try:
                self.finished_ok.emit(fn())
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(str(exc))
            finally:
                self._busy = False

        threading.Thread(target=work, name=name, daemon=True).start()


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


def check_firmware_update_stuck() -> dict[str, Any]:
    """Return ``{stuck: bool, detail: str}`` — USB IF3 + config timeout heuristic."""
    if usb_ota_ready() is None:
        return {"stuck": False, "detail": "no IF3"}
    try:
        with DaemonClient() as c:
            resp = c.request("config_get", refresh=True)
    except OSError as exc:
        err = str(exc)
        return {
            "stuck": looks_like_ota_stuck_error(err),
            "detail": err,
        }
    if resp.get("ok"):
        return {"stuck": False, "detail": "config ok"}
    err = str(resp.get("error") or "config failed")
    return {"stuck": looks_like_ota_stuck_error(err), "detail": err}


class OtaRecoverWorker(QObject):
    finished_ok = Signal(str)  # recover_firmware_update_mode status
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self.finished_ok.emit(recover_firmware_update_mode())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def start_ota_recover_thread(parent: QObject, worker: OtaRecoverWorker) -> QThread:
    thread = QThread(parent)
    worker.moveToThread(thread)
    worker.finished_ok.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    return thread
