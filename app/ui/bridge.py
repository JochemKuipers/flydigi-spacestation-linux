"""Daemon ↔ UI bridge (background thread, signals only)."""

from __future__ import annotations

import json
import threading

from PySide6.QtCore import QObject, Signal

from flydigi.ipc import DaemonClient, default_socket_path


class DaemonBridge(QObject):
    status = Signal(str)
    info = Signal(dict)
    report = Signal(dict)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._path = default_socket_path()
        self._client: DaemonClient | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="daemon-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        client = self._client
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def call(self, cmd: str, **kwargs):
        with DaemonClient(self._path) as c:
            return c.request(cmd, **kwargs)

    def _emit(self, signal: Signal, *args) -> bool:
        try:
            signal.emit(*args)
            return True
        except RuntimeError:
            # QObject already deleted (window closing)
            self._stop.set()
            return False

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                client = DaemonClient(self._path)
                client.connect(timeout=1.0)
                self._client = client
            except OSError:
                if not self._emit(self.status, f"Waiting for driver…"):
                    return
                self._stop.wait(1.0)
                continue
            if not self._emit(self.status, "Connected"):
                return
            try:
                info = client.request("info")
                if info.get("ok") and not self._emit(self.info, info["info"]):
                    return
                client.request("subscribe")
                client._sock.settimeout(0.5)  # noqa: SLF001
                while not self._stop.is_set():
                    line = client._readline()  # noqa: SLF001
                    if line is None:
                        continue
                    msg = json.loads(line)
                    if msg.get("event") == "report":
                        # strip bulky raw if present; keep UI payload small
                        if not self._emit(self.report, msg):
                            return
            except Exception as exc:  # noqa: BLE001
                if not self._stop.is_set():
                    self._emit(self.status, f"Driver disconnected ({exc})")
            finally:
                self._client = None
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass
            self._stop.wait(0.5)
