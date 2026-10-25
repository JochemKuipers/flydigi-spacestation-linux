"""Vader 4 Pro (f4) HID OTA — SS3 FmUpgradeSwViewModel.ota_write on USB IF3.

Safety: every flash (default) runs a start-frame dry-run (ACK required) on a
fresh open/close **before** any data cells. That is the gate for unknown /
older pad firmware — not a version allowlist (people on latest do not need
updates; people on older builds do).

Critical: an OTA **start** puts the pad into firmware-update mode. Closing the
hidraw without a **finish** frame leaves it stuck there (Space Station then
offers to switch back to standard mode). Preflight and abort paths must always
send finish after start.
"""

from __future__ import annotations

import json
import os
import select
import struct
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .enumerate import PID, VID, find_config_interface

REPORT_ID = 5
OUT_LEN = 64
IN_LEN = 64
ACK_TIMEOUT = 5.0
PREFLIGHT_TIMEOUT = 2.5

ROOT = Path(__file__).resolve().parents[1]
_FW_NAME = "F4_Telink87_Gamepad_6933_1025.bin"
_FW_REL = Path("archive/firmware/f4/6.9.3.3") / _FW_NAME


def _find_default_bin() -> Path:
    candidates = [
        ROOT / _FW_REL,
        Path("/usr/share/vader-companion/firmware") / _FW_NAME,
        Path("/usr/share/flydigi-vader/firmware") / _FW_NAME,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


DEFAULT_BIN = _find_default_bin()
CATALOG_URL = "https://api.flydigi.com/android/v3/Firmwares/pcNew?type=f4"

# Informational: full write was live-proven on this pad version (not a gate).
PROVEN_PAD_VERSIONS = frozenset({"6.9.3.3"})
# Back-compat alias
TESTED_PAD_VERSIONS = PROVEN_PAD_VERSIONS

ProgressCb = Callable[[int, int], None]  # percent, ota_index
StatusCb = Callable[[str], None]


class OtaPreflightError(RuntimeError):
    """Start-frame dry-run failed — no image bytes were written."""


def crc16_ss3(data: bytes) -> int:
    table = (0, 0xA001)
    crc = 0xFFFF
    for byte in data:
        b = byte
        for _ in range(8):
            crc = (crc >> 1) ^ table[(crc ^ b) & 1]
            b >>= 1
    return crc & 0xFFFF


def load_image(path: Path) -> tuple[bytearray, int, int]:
    raw = path.read_bytes()
    if len(raw) < 28:
        raise ValueError("bin too small")
    size = struct.unpack_from("<I", raw, 24)[0]
    if size < 4 or size > len(raw):
        raise ValueError(f"bad size @24: {size} (file {len(raw)})")
    trailer_crc = struct.unpack_from("<I", raw, size - 4)[0]
    if trailer_crc in (0, 0xFFFFFFFF):
        raise ValueError(f"illegal trailer CRC {trailer_crc:#x}")
    buf = bytearray(size + 16)
    buf[:size] = raw[:size]
    buf[size:] = b"\xff" * 16
    return buf, size, trailer_crc


def fetch_catalog_version(timeout: float = 10.0) -> dict:
    """Return catalog dict with at least ``version`` (and url/name when present)."""
    req = urllib.request.Request(
        CATALOG_URL, headers={"User-Agent": "flydigi-spacestation-linux"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    data = payload.get("data", payload)
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict) or not data.get("version"):
        raise ValueError(f"unexpected catalog payload: {payload!r}")
    return data


def usb_ota_ready() -> Path | None:
    """Return IF3 hidraw path if a USB FFEF OTA channel is present."""
    iface = find_config_interface(VID, PID)
    if iface is None or iface.bus != "usb":
        return None
    return iface.hidraw


def _pack(body: bytes) -> bytes:
    out = bytearray(OUT_LEN)
    out[0] = REPORT_ID
    out[1 : 1 + len(body)] = body
    return bytes(out)


def _wait_report5(fd: int, timeout: float) -> bytes | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], min(0.25, deadline - time.monotonic()))
        if not r:
            continue
        try:
            data = os.read(fd, IN_LEN)
        except BlockingIOError:
            continue
        except OSError:
            return None
        if data and data[0] == REPORT_ID:
            return data
    return None


def _is_fail(data: bytes) -> bool:
    return (
        len(data) >= 7
        and data[0] == 5
        and data[1] == 2
        and data[2] == 3
        and data[3] == 0
        and data[4] == 6
        and data[5] == 0xFF
        and data[6] != 0
    )


def _is_ok(data: bytes) -> bool:
    return (
        len(data) >= 7
        and data[0] == 5
        and data[1] == 2
        and data[2] == 3
        and data[3] == 0
        and data[4] == 6
        and data[5] == 0xFF
        and data[6] == 0
    )


def _drain(fd: int, window: float = 0.15) -> None:
    deadline = time.monotonic() + window
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], 0.05)
        if not r:
            continue
        try:
            os.read(fd, IN_LEN)
        except (BlockingIOError, OSError):
            break


def _finish_body(last_index: int) -> bytes:
    """SS3 OTA finish frame body (after report ID). ``last_index`` is cell index."""
    last = last_index & 0xFFFF
    ones = (0x10000 - last) & 0xFFFF
    return bytes(
        [
            2,
            6,
            0,
            2,
            0xFF,
            last & 0xFF,
            (last >> 8) & 0xFF,
            ones & 0xFF,
            (ones >> 8) & 0xFF,
        ]
    )


def _send_finish(fd: int, last_index: int = 0, *, timeout: float = 1.5) -> bytes | None:
    """Send finish and wait for any report-5 (OK or Fail both end the session)."""
    os.write(fd, _pack(_finish_body(last_index)))
    return _wait_report5(fd, timeout)


def _is_ota_status(data: bytes) -> bool:
    """True if IN looks like SS3 OTA success/fail status (session closed)."""
    return _is_ok(data) or _is_fail(data)


def abort_ota_session(
    hidraw: Path | None = None,
    *,
    last_index: int = 0,
    timeout: float = 1.5,
) -> bool:
    """Best-effort leave firmware-update mode after a hung/incomplete OTA.

    Sends the SS3 finish frame on IF3. Returns True if any report-5 replied.
    Safe to call when unsure whether a session is open.
    """
    path = hidraw or usb_ota_ready()
    if path is None:
        return False
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        _drain(fd)
        ack = _send_finish(fd, last_index, timeout=timeout)
        return ack is not None
    except OSError:
        return False
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def recover_firmware_update_mode(
    hidraw: Path | None = None,
    *,
    timeout: float = 1.5,
) -> str:
    """Leave firmware-update mode via OTA finish. Return status string.

    ``cleared`` — IF3 replied with OTA status (session closed)
    ``replied`` — other report-5 (finish sent; likely ok)
    ``no_reply`` — finish sent, no IN (unplug may still be needed)
    ``unavailable`` — no USB IF3
    """
    path = hidraw or usb_ota_ready()
    if path is None:
        return "unavailable"
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        _drain(fd)
        ack = _send_finish(fd, last_index=0, timeout=timeout)
        if ack is None:
            return "no_reply"
        if _is_ota_status(ack):
            return "cleared"
        return "replied"
    except OSError:
        return "no_reply"
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def looks_like_ota_stuck_error(message: str) -> bool:
    """Heuristic: config/LED RPC failures that often mean update-mode wedge."""
    low = message.lower()
    return any(
        s in low
        for s in (
            "timeout",
            "timed out",
            "no ack",
            "config read",
            "config write",
            "not writable",
            "firmware update",
        )
    )


def preflight_start_ack(
    hidraw: Path | None = None,
    *,
    timeout: float = PREFLIGHT_TIMEOUT,
) -> bytes:
    """Dry-run: OTA start → require report-5 ACK → **finish** (no image bytes).

    Raises ``OtaPreflightError`` if the channel does not ACK start. Always tries
    to send finish afterward so the pad is not left in firmware-update mode.
    """
    path = hidraw or usb_ota_ready()
    if path is None:
        raise OtaPreflightError("USB IF3 (FFEF) not found — use wired DInput")
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    start_ack: bytes | None = None
    try:
        _drain(fd)
        os.write(fd, _pack(bytes([2, 2, 0, 1, 0xFF])))
        start_ack = _wait_report5(fd, timeout)
        if start_ack is None:
            raise OtaPreflightError(
                f"no report-5 ACK to OTA start within {timeout}s — aborting before data"
            )
        if _is_fail(start_ack):
            raise OtaPreflightError(
                f"OTA fail status on start ({start_ack[6]}) — aborting before data"
            )
        return start_ack
    finally:
        # Start alone wedges the pad in update mode; always close the session.
        if start_ack is not None:
            try:
                _send_finish(fd, last_index=0, timeout=min(timeout, 1.5))
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


def flash_image(
    image: bytearray,
    bin_size: int,
    *,
    hidraw: Path | None = None,
    on_progress: ProgressCb | None = None,
    on_status: StatusCb | None = None,
    preflight: bool = True,
    pad_version: str | None = None,
    allow_untested: bool = True,
) -> None:
    """Run full OTA on USB IF3. Raises on failure; preflight runs before any data.

    ``pad_version`` / ``allow_untested`` are kept for call-site compatibility;
    version is not a hard gate (dry-run is).
    """
    del allow_untested  # unused — dry-run is the gate
    path = hidraw
    if path is None:
        path = usb_ota_ready()
        if path is None:
            raise FileNotFoundError("USB IF3 (FFEF) not found — use wired DInput")

    if pad_version and pad_version not in PROVEN_PAD_VERSIONS and on_status:
        on_status(
            f"note: pad {pad_version} not in proven set "
            f"({', '.join(sorted(PROVEN_PAD_VERSIONS))}); relying on dry-run ACK"
        )

    if preflight:
        if on_status:
            on_status("preflight: OTA start+finish dry-run…")
        preflight_start_ack(path)
        if on_status:
            on_status("preflight OK — starting full write")
        # Finish may bounce the OTA iface; re-resolve before the real write.
        time.sleep(0.4)
        if hidraw is None:
            for _ in range(25):
                again = usb_ota_ready()
                if again is not None:
                    path = again
                    break
                time.sleep(0.15)

    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    done_ok = False
    index_out = [0]
    try:
        _flash_fd(
            fd,
            image,
            bin_size,
            on_progress=on_progress,
            on_status=on_status,
            index_out=index_out,
        )
        done_ok = True
    finally:
        if not done_ok:
            try:
                if on_status:
                    on_status("abort: sending OTA finish to leave update mode…")
                _send_finish(
                    fd, last_index=max(0, index_out[0] - 1), timeout=1.5
                )
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


def flash_bin(
    bin_path: Path,
    *,
    hidraw: Path | None = None,
    on_progress: ProgressCb | None = None,
    on_status: StatusCb | None = None,
    preflight: bool = True,
    pad_version: str | None = None,
    allow_untested: bool = True,
) -> tuple[int, int]:
    """Load ``bin_path`` and flash. Returns ``(size, trailer_crc)``."""
    image, size, crc = load_image(bin_path)
    flash_image(
        image,
        size,
        hidraw=hidraw,
        on_progress=on_progress,
        on_status=on_status,
        preflight=preflight,
        pad_version=pad_version,
        allow_untested=allow_untested,
    )
    return size, crc


def _flash_fd(
    fd: int,
    image: bytearray,
    bin_size: int,
    *,
    on_progress: ProgressCb | None,
    on_status: StatusCb | None,
    index_out: list[int] | None = None,
) -> int:
    """Run start→data→finish. Returns last ``ota_index`` (for abort finish)."""
    ota_index = 0
    phase = 2
    if on_status:
        on_status("writing image…")
    _drain(fd)
    os.write(fd, _pack(bytes([2, 2, 0, 1, 0xFF])))
    t0 = time.monotonic()
    last_pct = -1

    def _set_index(n: int) -> None:
        nonlocal ota_index
        ota_index = n
        if index_out is not None:
            index_out[0] = n

    while True:
        ack = _wait_report5(fd, ACK_TIMEOUT)
        if ack is None:
            raise TimeoutError(
                f"no ACK after index={ota_index} ({time.monotonic() - t0:.1f}s)"
            )
        if _is_fail(ack):
            raise RuntimeError(f"OTA Fail status={ack[6]}")
        if _is_ok(ack):
            if on_progress:
                on_progress(100, ota_index)
            return ota_index
        if phase != 2:
            continue

        sendbuf = bytearray(60)
        length = 0
        for col in range(3):
            sendbuf[20 * col] = ota_index & 0xFF
            sendbuf[20 * col + 1] = (ota_index >> 8) & 0xFF
            base = ota_index * 16
            payload = image[base : base + 16]
            if len(payload) < 16:
                payload = payload + bytes(16 - len(payload))
            sendbuf[20 * col + 2 : 20 * col + 18] = payload
            crc = crc16_ss3(bytes(sendbuf[20 * col : 20 * col + 18]))
            sendbuf[20 * col + 18] = crc & 0xFF
            sendbuf[20 * col + 19] = (crc >> 8) & 0xFF
            _set_index(ota_index + 1)
            if ota_index * 16 >= bin_size + 16:
                _set_index(ota_index - 1)
                break
            length = 20 * col + 20

        if length == 0:
            last = (ota_index - 1) & 0xFFFF
            os.write(fd, _pack(_finish_body(last)))
            phase = 0
            for _ in range(40):
                ack2 = _wait_report5(fd, 1.0)
                if ack2 is None:
                    continue
                if _is_ok(ack2):
                    if on_progress:
                        on_progress(100, ota_index)
                    return ota_index
                if _is_fail(ack2):
                    raise RuntimeError(f"OTA Fail on finish status={ack2[6]}")
            if on_progress:
                on_progress(100, ota_index)
            return ota_index

        body = bytearray(3 + length)
        body[0] = 2
        body[1] = length & 0xFF
        body[2] = 0
        body[3:] = sendbuf[:length]
        os.write(fd, _pack(bytes(body)))

        pct = min(100, ota_index * 16 * 100 // bin_size)
        if on_progress and pct != last_pct:
            on_progress(pct, ota_index)
            last_pct = pct
