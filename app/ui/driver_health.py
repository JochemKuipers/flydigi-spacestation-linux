"""Detect whether flydigi-vader4d is installed and reachable."""

from __future__ import annotations

import subprocess
from pathlib import Path

from flydigi.ipc import DaemonClient, default_socket_path

_UNIT_USER = Path.home() / ".config/systemd/user/flydigi-vader4d.service"
_UNIT_SYSTEM = (
    Path("/usr/lib/systemd/user/flydigi-vader4d.service"),
    Path("/usr/lib/systemd/system/flydigi-vader4d.service"),
)
_UDEV_PATHS = (
    Path("/usr/lib/udev/rules.d/99-flydigi-vader4.rules"),
    Path("/etc/udev/rules.d/99-flydigi-vader4.rules"),
)
_INSTALL_HINT = (
    "Install the driver package for your distro (flydigi-vader4d),\n"
    "or from this repo:\n"
    "  ./scripts/install-driver.sh\n\n"
    "Or start it in a terminal:\n"
    "  flydigi-vader4d\n"
    "  # or: python3 driver/flydigi_vader4d.py"
)


def unit_installed() -> bool:
    if _UNIT_USER.is_file():
        return True
    return any(p.is_file() for p in _UNIT_SYSTEM)


def udev_installed() -> bool:
    return any(p.is_file() for p in _UDEV_PATHS)


def systemd_active() -> bool | None:
    """True/False if systemctl answers; None if systemctl unavailable."""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "flydigi-vader4d.service"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout.strip() == "active"


def socket_alive() -> bool:
    client = DaemonClient(default_socket_path())
    try:
        client.connect(timeout=0.35)
        resp = client.request("ping")
        return bool(resp.get("ok"))
    except OSError:
        return False
    finally:
        client.close()


def describe(*, assume_down: bool = False) -> tuple[str, str | None]:
    """Return ``(status_bar_text, popup_message_or_None)``."""
    if not assume_down and socket_alive():
        return "Driver ready", None

    installed = unit_installed() or udev_installed()
    active = systemd_active()

    if active is True:
        return (
            "Driver not responding",
            (
                "The controller driver is enabled but not responding.\n\n"
                "Try:\n"
                "  systemctl --user restart flydigi-vader4d.service\n\n"
                "Or run it in a terminal to see errors:\n"
                "  flydigi-vader4d"
            ),
        )

    if installed or active is False:
        return (
            "Driver installed — not running",
            (
                "The controller driver is installed but not running.\n\n"
                "Start it with:\n"
                "  systemctl --user start flydigi-vader4d.service\n\n"
                "Or:\n"
                "  flydigi-vader4d"
            ),
        )

    return (
        "Driver not installed",
        "The controller driver isn’t installed on this system.\n\n" + _INSTALL_HINT,
    )
