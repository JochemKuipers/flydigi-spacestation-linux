"""Locate Flydigi Vader 4 Pro hidraw nodes on Linux."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VID = 0x04B4
PID = 0x2412  # wired + dongle DInput composite


@dataclass(frozen=True)
class HidInterface:
    hidraw: Path
    sysfs: Path
    interface_number: int
    phys: str
    name: str


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _iface_number(device: Path) -> int:
    import re

    # USB interface dirs look like 1-1.4:1.2 — not HID ids like 0003:04B4:2412.0033
    pat = re.compile(r"^[0-9]+-[0-9._-]+:[0-9]+\.([0-9]+)$")
    for parent in [device, *device.parents]:
        m = pat.match(parent.name)
        if m:
            return int(m.group(1))
    return -1


def list_vader4_interfaces(vid: int = VID, pid: int = PID) -> list[HidInterface]:
    out: list[HidInterface] = []
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return out
    needle_v = f"{vid:04X}"
    needle_p = f"{pid:04X}"
    for entry in sorted(root.iterdir()):
        uevent = _read(entry / "device" / "uevent")
        up = uevent.upper()
        if needle_v not in up or needle_p not in up:
            continue
        phys = name = ""
        for line in uevent.splitlines():
            if line.startswith("HID_PHYS="):
                phys = line.split("=", 1)[1]
            elif line.startswith("HID_NAME="):
                name = line.split("=", 1)[1]
        device = (entry / "device").resolve()
        node = Path("/dev") / entry.name
        if not node.exists():
            continue
        out.append(
            HidInterface(
                hidraw=node,
                sysfs=entry,
                interface_number=_iface_number(device),
                phys=phys,
                name=name,
            )
        )
    return out


def find_input_interface(vid: int = VID, pid: int = PID) -> HidInterface | None:
    """Prefer USB interface 2 (extended DInput + IMU)."""
    ifaces = list_vader4_interfaces(vid, pid)
    for i in ifaces:
        if i.interface_number == 2 or i.phys.endswith("/input2"):
            return i
    return None


def find_config_interface(vid: int = VID, pid: int = PID) -> HidInterface | None:
    ifaces = list_vader4_interfaces(vid, pid)
    for i in ifaces:
        if i.interface_number == 3 or i.phys.endswith("/input3"):
            return i
    return None
