#!/usr/bin/env python3
"""Userspace DInput driver for Flydigi Vader 4 Pro.

Reads hidraw interface 2 (report 0x04 / magic 0xFE), republishes a uinput
gamepad (Flydigi VID/PID — no Xbox spoofing), and exposes a Unix-socket
control plane so the companion app can send IF2 commands without fighting
for exclusive hidraw access.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evdev import AbsInfo, UInput, ecodes

from flydigi.dinput_proto import (
    DInputDevice,
    DeviceInfo,
    LedConfig,
    encode_led_config,
    off_led,
    steady_led,
)
from flydigi.enumerate import VID, PID, find_input_interface, list_vader4_interfaces
from flydigi.gamepad_config import decode_gamepad_config, encode_gamepad_config
from flydigi.ipc import default_socket_path
from flydigi.v1_report import V1Report, parse_v1_report

BTN_MAP = {
    "a": ecodes.BTN_SOUTH,
    "b": ecodes.BTN_EAST,
    "x": ecodes.BTN_NORTH,
    "y": ecodes.BTN_WEST,
    "lb": ecodes.BTN_TL,
    "rb": ecodes.BTN_TR,
    "select": ecodes.BTN_SELECT,
    "start": ecodes.BTN_START,
    "guide": ecodes.BTN_MODE,
    "ls": ecodes.BTN_THUMBL,
    "rs": ecodes.BTN_THUMBR,
    "c": ecodes.BTN_C,
    "z": ecodes.BTN_Z,
    "m1": ecodes.BTN_TRIGGER_HAPPY1,
    "m2": ecodes.BTN_TRIGGER_HAPPY2,
    "m3": ecodes.BTN_TRIGGER_HAPPY3,
    "m4": ecodes.BTN_TRIGGER_HAPPY4,
}

CAP = {
    ecodes.EV_KEY: list(BTN_MAP.values()),
    ecodes.EV_ABS: [
        (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Y, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_RX, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_RY, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
        (ecodes.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
}


def wait_for_device(timeout: float | None = None):
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        iface = find_input_interface()
        if iface is not None:
            return iface
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Vader 4 Pro IF2 hidraw not found")
        time.sleep(0.5)


def _info_dict(info: DeviceInfo) -> dict[str, Any]:
    return {
        "device_id": info.device_id,
        "firmware": info.firmware_version,
        "battery": info.battery_level,
        "battery_raw": info.battery,
        "cpu_type": info.cpu_type,
        "connection_type": info.connection_type,
        "motion_sensor_type": info.motion_sensor_type,
        "mac": info.device_mac.hex(),
    }


def _report_dict(rep: V1Report) -> dict[str, Any]:
    return {
        "event": "report",
        "lx": rep.lx,
        "ly": rep.ly,
        "rx": rep.rx,
        "ry": rep.ry,
        "lt": rep.lt,
        "rt": rep.rt,
        "hat_x": rep.hat_x,
        "hat_y": rep.hat_y,
        "hat": rep.hat,
        "buttons": {k: v for k, v in rep.buttons.items() if v},
        "accel": list(rep.accel),
        "gyro": list(rep.gyro),
    }


def _led_dict(cfg: LedConfig) -> dict[str, Any]:
    color = cfg.groups[0][0] if cfg.groups and cfg.groups[0] else (0, 0, 0)
    return {
        "mode": cfg.led_mode,
        "brightness": cfg.light_scale,
        "loop_time": cfg.loop_time,
        "rgb_num": cfg.rgb_num,
        "color": list(color),
    }


class Daemon:
    def __init__(self, sock_path: Path) -> None:
        self.sock_path = sock_path
        self.stop = False
        self.dev: DInputDevice | None = None
        self.ui: UInput | None = None
        self._last: dict[str, object] = {}
        self._info: DeviceInfo | None = None
        self._clients: list[socket.socket] = []
        self._subscribers: set[socket.socket] = set()
        self._client_bufs: dict[socket.socket, bytearray] = {}
        self._lock = threading.Lock()
        self._listen: socket.socket | None = None
        self._cfg_raw: bytes | None = None
        self._led_raw: bytes | None = None

    def _publish_uinput(self, report: V1Report) -> None:
        ui = self.ui
        if ui is None:
            return
        last = self._last
        for name, code in BTN_MAP.items():
            val = 1 if report.buttons[name] else 0
            key = f"b:{name}"
            if last.get(key) != val:
                ui.write(ecodes.EV_KEY, code, val)
                last[key] = val
        for abs_code, value, key in (
            (ecodes.ABS_X, report.lx, "lx"),
            (ecodes.ABS_Y, report.ly, "ly"),
            (ecodes.ABS_RX, report.rx, "rx"),
            (ecodes.ABS_RY, report.ry, "ry"),
            (ecodes.ABS_Z, report.lt, "lt"),
            (ecodes.ABS_RZ, report.rt, "rt"),
            (ecodes.ABS_HAT0X, report.hat_x, "hx"),
            (ecodes.ABS_HAT0Y, report.hat_y, "hy"),
        ):
            if last.get(key) != value:
                ui.write(ecodes.EV_ABS, abs_code, value)
                last[key] = value
        ui.syn()

    def _broadcast_report(self, report: V1Report) -> None:
        if not self._subscribers:
            return
        line = (json.dumps(_report_dict(report)) + "\n").encode()
        dead: list[socket.socket] = []
        for c in list(self._subscribers):
            try:
                c.sendall(line)
            except OSError:
                dead.append(c)
        for c in dead:
            self._drop_client(c)

    def _drop_client(self, c: socket.socket) -> None:
        self._subscribers.discard(c)
        if c in self._clients:
            self._clients.remove(c)
        self._client_bufs.pop(c, None)
        try:
            c.close()
        except OSError:
            pass

    def _reply(self, c: socket.socket, obj: dict[str, Any]) -> None:
        try:
            c.sendall((json.dumps(obj) + "\n").encode())
        except OSError:
            self._drop_client(c)

    def _handle_cmd(self, c: socket.socket, msg: dict[str, Any]) -> None:
        cmd = msg.get("cmd")
        try:
            if cmd == "ping":
                self._reply(c, {"ok": True, "pong": True})
            elif cmd == "subscribe":
                self._subscribers.add(c)
                self._reply(c, {"ok": True})
            elif cmd == "unsubscribe":
                self._subscribers.discard(c)
                self._reply(c, {"ok": True})
            elif cmd == "info":
                self._reply(c, self._cmd_info())
            elif cmd == "rumble":
                self._reply(c, self._cmd_rumble(msg))
            elif cmd == "led_get":
                self._reply(c, self._cmd_led_get())
            elif cmd == "led_set":
                self._reply(c, self._cmd_led_set(msg))
            elif cmd == "config_get":
                self._reply(c, self._cmd_config_get())
            elif cmd == "config_set_sticks":
                self._reply(c, self._cmd_config_set_sticks(msg))
            elif cmd == "config_set_keys":
                self._reply(c, self._cmd_config_set_keys(msg))
            elif cmd == "config_set_motor":
                self._reply(c, self._cmd_config_set_motor(msg))
            else:
                self._reply(c, {"ok": False, "error": f"unknown cmd: {cmd}"})
        except Exception as exc:  # noqa: BLE001 — surface to client
            self._reply(c, {"ok": False, "error": str(exc)})

    def _require_dev(self) -> DInputDevice:
        if self.dev is None:
            raise RuntimeError("device not connected")
        return self.dev

    def _on_sideband(self, msg: object) -> None:
        if isinstance(msg, V1Report):
            self._publish_uinput(msg)
            self._broadcast_report(msg)

    def _cmd_info(self) -> dict[str, Any]:
        dev = self._require_dev()
        self._info = dev.wait_device_info(timeout=2.0, on_report=self._on_sideband)
        return {"ok": True, "info": _info_dict(self._info)}

    def _cmd_rumble(self, msg: dict[str, Any]) -> dict[str, Any]:
        low = int(msg.get("low", 0))
        high = int(msg.get("high", 0))
        self._require_dev().rumble(low, high)
        return {"ok": True}

    def _cmd_led_get(self) -> dict[str, Any]:
        dev = self._require_dev()
        led = dev.wait_led_config(timeout=4.0, on_report=self._on_sideband)
        self._led_raw = encode_led_config(led)
        return {"ok": True, "led": _led_dict(led)}

    def _cmd_led_set(self, msg: dict[str, Any]) -> dict[str, Any]:
        mode = int(msg.get("mode", LedConfig.MODE_STEADY))
        brightness = int(msg.get("brightness", 80))
        r = int(msg.get("r", 0))
        g = int(msg.get("g", 0))
        b = int(msg.get("b", 0))
        if mode == LedConfig.MODE_OFF:
            cfg = off_led(brightness)
        else:
            cfg = steady_led(r, g, b, brightness)
            cfg.led_mode = mode
            if mode == LedConfig.MODE_STREAMLINED:
                cfg.loop_end = 5
                cfg.loop_time = max(0, min(100, 100 - int(msg.get("speed", 50))))
            elif mode == LedConfig.MODE_BREATHING:
                cfg.loop_end = 5
                cfg.loop_time = max(0, min(100, 100 - int(msg.get("speed", 40))))
        self._require_dev().write_led_config(cfg)
        return {"ok": True, "led": _led_dict(cfg)}

    def _fetch_config(self):
        dev = self._require_dev()
        self._cfg_raw = None
        dev.request_gamepad_config()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            msg = dev.pump(0.1)
            if isinstance(msg, V1Report):
                self._publish_uinput(msg)
                self._broadcast_report(msg)
                continue
            if isinstance(msg, tuple) and msg[0] == "config":
                self._cfg_raw = msg[1]
                break
            if isinstance(msg, DeviceInfo):
                self._info = msg
        if self._cfg_raw is None:
            raise TimeoutError("config read timeout")
        return decode_gamepad_config(self._cfg_raw)

    def _write_config(self, cfg) -> None:
        from flydigi.dinput_proto import gamepad_config_parcels

        data = encode_gamepad_config(cfg)
        self._cfg_raw = data
        for chunk in gamepad_config_parcels(data, 0):
            self._require_dev().write_raw(chunk)
            time.sleep(0.02)

    def _cmd_config_get(self) -> dict[str, Any]:
        cfg = self._fetch_config()
        return {
            "ok": True,
            "config": {
                "version": cfg.version,
                "keys": [
                    {
                        "id": k.key_id,
                        "name": k.name,
                        "map_id": k.map_id,
                        "map_name": KEY_NAMES_SAFE(k.map_id),
                        "turbo": k.turbo,
                        "remapped": k.is_remapped,
                    }
                    for k in cfg.keys
                    if k.name not in ("?",)
                ],
                "left_stick": cfg.left_stick.__dict__,
                "right_stick": cfg.right_stick.__dict__,
                "left_trigger": cfg.left_trigger.__dict__,
                "right_trigger": cfg.right_trigger.__dict__,
                "motion": cfg.motion.__dict__,
                "motor": {
                    "main_switch": cfg.motor.main_switch,
                    "left": cfg.motor.left.__dict__,
                    "right": cfg.motor.right.__dict__,
                },
            },
        }

    def _cmd_config_set_sticks(self, msg: dict[str, Any]) -> dict[str, Any]:
        cfg = self._fetch_config()
        for side, attr in (("left_stick", "left_stick"), ("right_stick", "right_stick"),
                           ("left_trigger", "left_trigger"), ("right_trigger", "right_trigger")):
            patch = msg.get(side)
            if not patch:
                continue
            curve = getattr(cfg, attr)
            for field in ("type", "zero", "p0x", "p0y", "p1x", "p1y", "end"):
                if field in patch:
                    setattr(curve, field, int(patch[field]))
        self._write_config(cfg)
        return {"ok": True}

    def _cmd_config_set_keys(self, msg: dict[str, Any]) -> dict[str, Any]:
        cfg = self._fetch_config()
        for item in msg.get("keys", []):
            kid = int(item["id"])
            if 0 <= kid < len(cfg.keys):
                if "map_id" in item:
                    cfg.keys[kid].map_id = int(item["map_id"])
                if "turbo" in item:
                    cfg.keys[kid].turbo = int(item["turbo"])
                if "turbo_type" in item:
                    cfg.keys[kid].turbo_type = int(item["turbo_type"])
        self._write_config(cfg)
        return {"ok": True}

    def _cmd_config_set_motor(self, msg: dict[str, Any]) -> dict[str, Any]:
        cfg = self._fetch_config()
        if "main_switch" in msg:
            cfg.motor.main_switch = bool(msg["main_switch"])
        for side in ("left", "right"):
            patch = msg.get(side)
            if not patch:
                continue
            motor = getattr(cfg.motor, side)
            for field in ("type", "min", "max", "scale"):
                if field in patch:
                    setattr(motor, field, int(patch[field]))
        self._write_config(cfg)
        return {"ok": True}

    def _setup_socket(self) -> None:
        if self.sock_path.exists():
            self.sock_path.unlink()
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(str(self.sock_path))
        s.listen(8)
        s.setblocking(False)
        os.chmod(self.sock_path, 0o660)
        self._listen = s
        print(f"flydigi-vader4d: control socket {self.sock_path}", flush=True)

    def _accept(self) -> None:
        assert self._listen is not None
        while True:
            try:
                c, _ = self._listen.accept()
            except BlockingIOError:
                break
            c.setblocking(False)
            self._clients.append(c)
            self._client_bufs[c] = bytearray()

    def _service_clients(self) -> None:
        for c in list(self._clients):
            try:
                data = c.recv(4096)
            except BlockingIOError:
                continue
            except OSError:
                self._drop_client(c)
                continue
            if not data:
                self._drop_client(c)
                continue
            buf = self._client_bufs.setdefault(c, bytearray())
            buf.extend(data)
            while b"\n" in buf:
                line, rest = bytes(buf).split(b"\n", 1)
                buf[:] = rest
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode())
                except json.JSONDecodeError:
                    self._reply(c, {"ok": False, "error": "invalid json"})
                    continue
                self._handle_cmd(c, msg)

    def open_device(self) -> None:
        iface = wait_for_device()
        print(f"flydigi-vader4d: using {iface.hidraw} (iface {iface.interface_number})", flush=True)
        if self.dev:
            self.dev.close()
        self.dev = DInputDevice(iface.hidraw)
        self._info = None
        self._last.clear()
        if self.ui is None:
            self.ui = UInput(
                CAP,
                name="Flydigi Vader 4 Pro",
                vendor=VID,
                product=PID,
                version=0x0111,
                bustype=ecodes.BUS_USB,
            )
        # Best-effort identity probe (non-blocking path continues if it fails)
        try:
            self._info = self.dev.wait_device_info(timeout=1.5)
            print(
                f"flydigi-vader4d: device_id={self._info.device_id} "
                f"fw={self._info.firmware_version} batt={self._info.battery_level}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"flydigi-vader4d: info probe skipped ({exc})", flush=True)

    def run(self) -> int:
        def _stop(*_a: object) -> None:
            self.stop = True

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        self._setup_socket()
        print("flydigi-vader4d: waiting for 04b4:2412 interface 2…", flush=True)
        self.open_device()

        try:
            while not self.stop:
                assert self.dev is not None and self._listen is not None
                fds = [self.dev.fileno(), self._listen.fileno(), *[c.fileno() for c in self._clients]]
                try:
                    r, _, _ = select.select(fds, [], [], 1.0)
                except (ValueError, OSError):
                    # stale fd after disconnect
                    time.sleep(0.1)
                    continue

                if self._listen.fileno() in r:
                    self._accept()

                client_ready = {c for c in self._clients if c.fileno() in r}
                if client_ready:
                    # temporarily only service those; _service_clients reads all nonblocking
                    self._service_clients()

                if self.dev.fileno() in r:
                    try:
                        data = os.read(self.dev.fileno(), 64)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        print(f"flydigi-vader4d: read error {exc}, reconnecting…", flush=True)
                        self._reconnect()
                        continue
                    msg = self.dev._dispatch(data)
                    if isinstance(msg, V1Report):
                        self._publish_uinput(msg)
                        self._broadcast_report(msg)
                    elif isinstance(msg, DeviceInfo):
                        self._info = msg
                    elif isinstance(msg, tuple) and msg[0] == "config":
                        self._cfg_raw = msg[1]
                    elif isinstance(msg, tuple) and msg[0] == "led":
                        self._led_raw = msg[1]
                elif not r:
                    # idle: check hot-unplug
                    if self.dev and not self.dev.path.exists():
                        print("flydigi-vader4d: device gone, waiting…", flush=True)
                        self._reconnect()
        finally:
            self._cleanup()
        return 0

    def _reconnect(self) -> None:
        if self.dev:
            try:
                self.dev.close()
            except OSError:
                pass
            self.dev = None
        self.open_device()

    def _cleanup(self) -> None:
        for c in list(self._clients):
            self._drop_client(c)
        if self._listen:
            try:
                self._listen.close()
            except OSError:
                pass
        if self.sock_path.exists():
            try:
                self.sock_path.unlink()
            except OSError:
                pass
        if self.ui:
            self.ui.close()
            self.ui = None
        if self.dev:
            self.dev.close()
            self.dev = None


def KEY_NAMES_SAFE(map_id: int) -> str:
    from flydigi.gamepad_config import KEY_NAMES

    if map_id == 255:
        return "(native)"
    if 0 <= map_id < len(KEY_NAMES):
        return KEY_NAMES[map_id]
    return f"#{map_id}"


def run(once_list: bool = False, sock_path: Path | None = None) -> int:
    if once_list:
        for i in list_vader4_interfaces():
            print(
                f"{i.hidraw} bus={i.bus} iface={i.interface_number} "
                f"phys={i.phys} name={i.name}"
            )
        return 0

    path = sock_path or default_socket_path()
    return Daemon(path).run()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true", help="List matching hidraw nodes and exit")
    p.add_argument(
        "--socket",
        type=Path,
        default=None,
        help=f"Unix socket path (default: {default_socket_path()})",
    )
    args = p.parse_args()
    raise SystemExit(run(once_list=args.list, sock_path=args.socket))


if __name__ == "__main__":
    main()
