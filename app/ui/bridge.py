"""Daemon ↔ UI bridge (background thread, signals only)."""

from __future__ import annotations

import json
import threading
import time
from contextlib import suppress

from PySide6.QtCore import QObject, Signal

from flydigi.ipc import DaemonClient, default_socket_path

from .driver_health import describe


class DaemonBridge(QObject):
    status = Signal(str)
    info = Signal(dict)
    report = Signal(dict)
    presence = Signal(bool)  # controller plugged/paired (not just daemon socket)
    driver_issue = Signal(str)  # human-readable problem for a one-shot popup
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._path = default_socket_path()
        self._client: DaemonClient | None = None
        self._issue_shown = False
        self._down_since: float | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="daemon-bridge", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        client = self._client
        if client is not None:
            with suppress(OSError):
                client.close()
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

    def _note_down(self, status: str, issue: str | None) -> bool:
        if not self._emit(self.status, status):
            return False
        if issue is None:
            return True
        now = time.monotonic()
        if self._down_since is None:
            self._down_since = now
        # Give a slow start a couple seconds before nagging.
        if not self._issue_shown and now - self._down_since >= 2.0:
            self._issue_shown = True
            return self._emit(self.driver_issue, issue)
        return True

    def _note_ready(self) -> bool:
        self._down_since = None
        self._issue_shown = False
        return self._emit(self.status, "Driver ready")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                client = DaemonClient(self._path)
                client.connect(timeout=1.0)
                self._client = client
            except OSError:
                status, issue = describe(assume_down=True)
                if not self._note_down(status, issue):
                    return
                self._stop.wait(1.0)
                continue
            if not self._note_ready():
                return
            try:
                info = client.request("info")
                if info.get("ok"):
                    payload = info["info"]
                    if not self._emit(self.info, payload):
                        return
                    if payload.get("connected") is False:
                        self._emit(self.presence, False)
                    elif payload.get("connected") is True:
                        self._emit(self.presence, True)
                client.request("subscribe")
                client._sock.settimeout(0.5)
                while not self._stop.is_set():
                    line = client._readline()
                    if line is None:
                        continue
                    msg = json.loads(line)
                    ev = msg.get("event")
                    if ev == "presence":
                        if not self._emit(self.presence, bool(msg.get("connected"))):
                            return
                    elif ev == "report" and not self._emit(self.report, msg):
                        return
            except (OSError, TimeoutError, json.JSONDecodeError, RuntimeError):
                if not self._stop.is_set():
                    status, issue = describe(assume_down=True)
                    if not self._note_down(status, issue):
                        return
                    self._emit(self.presence, False)
            finally:
                self._client = None
                with suppress(OSError):
                    client.close()
            self._stop.wait(0.5)
