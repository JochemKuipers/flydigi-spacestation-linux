"""Unix-socket control plane for flydigi-vader4d.

Newline-delimited JSON. One request → one response (except `subscribe` which
also streams `event` frames until disconnect).
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any, Iterator

SOCKET_NAME = "flydigi-vader4d.sock"


def default_socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / SOCKET_NAME
    return Path(f"/tmp/flydigi-vader4d-{os.getuid()}.sock")


class DaemonClient:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_socket_path()
        self._sock: socket.socket | None = None
        self._buf = b""

    def connect(self, timeout: float = 2.0) -> None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(self.path))
        self._sock = s

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> DaemonClient:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, cmd: str, **kwargs: Any) -> dict[str, Any]:
        if self._sock is None:
            self.connect()
        assert self._sock is not None
        payload = {"cmd": cmd, **kwargs}
        self._sock.sendall((json.dumps(payload) + "\n").encode())
        while True:
            line = self._readline()
            if line is None:
                raise ConnectionError("daemon closed connection")
            msg = json.loads(line)
            if msg.get("event"):
                # skip streamed events during request/response
                continue
            return msg

    def subscribe(self) -> Iterator[dict[str, Any]]:
        """Enable report streaming; yield event dicts (and ignore acks)."""
        resp = self.request("subscribe")
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "subscribe failed"))
        assert self._sock is not None
        self._sock.settimeout(None)
        while True:
            line = self._readline()
            if line is None:
                return
            msg = json.loads(line)
            if msg.get("event"):
                yield msg

    def _readline(self) -> str | None:
        assert self._sock is not None
        while b"\n" not in self._buf:
            try:
                chunk = self._sock.recv(4096)
            except TimeoutError:
                return None
            if not chunk:
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode()
