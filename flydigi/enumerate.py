"""Locate Flydigi Vader 4 Pro hidraw nodes on Linux."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VID = 0x04B4
PID = 0x2412  # wired + 2.4G dongle DInput composite

# Additional (vid, pid) pairs to probe. Bluetooth DInput identity is unverified
# on this pad; when paired, BlueZ usually exposes hidraw with HID_NAME containing
# "Flydigi" — see list_vader4_interfaces(match_name=True).
EXTRA_IDS: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class HidInterface:
    hidraw: Path
    sysfs: Path
    interface_number: int
    phys: str
    name: str
    bus: str  # "usb" | "bluetooth" | "other"


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


def _bus_from_phys(phys: str) -> str:
    p = phys.lower()
    if p.startswith("usb-") or "/usb" in p:
        return "usb"
    if "bluetooth" in p or p.startswith("00:") or "bluez" in p:
        return "bluetooth"
    return "other"


def list_vader4_interfaces(
    vid: int = VID,
    pid: int = PID,
    *,
    match_name: bool = True,
) -> list[HidInterface]:
    """List matching hidraw nodes.

    Matches USB/dongle VID:PID by default. If ``match_name`` is true, also
    includes hidraw devices whose HID_NAME contains \"Flydigi\" and \"VADER\"
    (covers Bluetooth once paired, before we lock a BT VID:PID).
    """
    out: list[HidInterface] = []
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return out
    id_needles = {(f"{vid:04X}", f"{pid:04X}")}
    for ev, ep in EXTRA_IDS:
        id_needles.add((f"{ev:04X}", f"{ep:04X}"))

    seen: set[Path] = set()
    for entry in sorted(root.iterdir()):
        uevent = _read(entry / "device" / "uevent")
        up = uevent.upper()
        phys = name = ""
        for line in uevent.splitlines():
            if line.startswith("HID_PHYS="):
                phys = line.split("=", 1)[1]
            elif line.startswith("HID_NAME="):
                name = line.split("=", 1)[1]
        id_hit = any(nv in up and np in up for nv, np in id_needles)
        name_hit = match_name and ("FLYDIGI" in name.upper()) and ("VADER" in name.upper())
        if not id_hit and not name_hit:
            continue
        device = (entry / "device").resolve()
        node = Path("/dev") / entry.name
        if not node.exists() or node in seen:
            continue
        seen.add(node)
        out.append(
            HidInterface(
                hidraw=node,
                sysfs=entry,
                interface_number=_iface_number(device),
                phys=phys,
                name=name,
                bus=_bus_from_phys(phys),
            )
        )
    return out


def find_input_interface(vid: int = VID, pid: int = PID) -> HidInterface | None:
    """Prefer USB interface 2 (extended DInput + IMU)."""
    ifaces = list_vader4_interfaces(vid, pid)
    for i in ifaces:
        if i.interface_number == 2 or i.phys.endswith("/input2"):
            return i
    # Bluetooth often exposes a single aggregated hidraw (layout TBD).
    bt = [i for i in ifaces if i.bus == "bluetooth"]
    if len(bt) == 1:
        return bt[0]
    return None


def find_config_interface(vid: int = VID, pid: int = PID) -> HidInterface | None:
    ifaces = list_vader4_interfaces(vid, pid)
    for i in ifaces:
        if i.interface_number == 3 or i.phys.endswith("/input3"):
            return i
    return None
