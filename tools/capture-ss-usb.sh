#!/usr/bin/env bash
# Capture Space Station ↔ Vader USB on the **Linux host** while the pad is
# passed into win10 via libvirt hostdev (not SPICE redirect).
#
# SPICE usbredir only shows enumeration inside guest USBPcap — that's why the
# VM Wireshark attempt failed. Host usbmon + hostdev sees the real HID traffic.
#
# Usage (SS4 on this VM blocks the UI until “standard”/XInput):
#   1. Close any SPICE USB redirect of the pad in virt-manager.
#   2. sudo ./tools/capture-ss-usb.sh
#   3. In the VM: let SS switch to standard/XInput → enter app →
#      remap one button → Save/Apply.
#   4. Press Enter here to stop.
# Output default: captures/ss-remap-save.pcap
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/captures/ss-remap-save.pcap}"
DOMAIN=win10
URI=qemu:///system
XML="$(mktemp /tmp/flydigi-hostdev.XXXXXX.xml)"
trap 'rm -f "$XML"' EXIT

find_pad() {
  python3 - <<'PY'
import pathlib, sys
for d in pathlib.Path("/sys/bus/usb/devices").iterdir():
    try:
        vid = (d / "idVendor").read_text().strip()
        pid = (d / "idProduct").read_text().strip()
        bus = int((d / "busnum").read_text())
        dev = int((d / "devnum").read_text())
    except OSError:
        continue
    prod = ""
    try:
        prod = (d / "product").read_text(errors="replace").strip()
    except OSError:
        pass
    ok = vid == "04b4" or (
        vid == "045e" and "VADER" in prod.upper()
    )
    if not ok:
        continue
    print(f"{vid} {pid} {bus} {dev} {prod}")
    sys.exit(0)
sys.exit("no Flydigi/Vader USB device on host")
PY
}

read -r VID PID BUS DEV PROD < <(find_pad)
echo "Found ${VID}:${PID} bus=${BUS} dev=${DEV} (${PROD})"

case "$VID:$PID" in
  04b4:2412) echo "Note: DInput on host — SS may force XInput before the UI opens." ;;
  045e:028e) echo "XInput on host — matches SS “standard mode”; capture Save in the app." ;;
  *) echo "WARNING: unexpected id $VID:$PID" ;;
esac

cat >"$XML" <<EOF
<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x$VID'/>
    <product id='0x$PID'/>
  </source>
</hostdev>
EOF

echo "Attaching to $DOMAIN…"
virsh -c "$URI" attach-device "$DOMAIN" "$XML" --live

mkdir -p "$(dirname "$OUT")"
modprobe usbmon 2>/dev/null || true
MON="/dev/usbmon${BUS}"
if [[ ! -e "$MON" ]]; then
  echo "Missing $MON — need root to load usbmon (modprobe usbmon)."
  exit 1
fi

echo
echo "Capturing $MON → $OUT"
echo "In the VM: allow SS → standard/XInput if it asks, open the app,"
echo "remap one button, Save/Apply. Then press Enter here to stop."
echo

if ! command -v tcpdump >/dev/null; then
  echo "Install tcpdump first:  sudo pacman -S tcpdump"
  virsh -c "$URI" detach-device "$DOMAIN" "$XML" --live || true
  exit 1
fi

# usbmon via tcpdump (link-type USB_LINUX_MMAPPED)
tcpdump -i "usbmon${BUS}" -w "$OUT" &
TCPDUMP_PID=$!
trap 'kill $TCPDUMP_PID 2>/dev/null || true; virsh -c "$URI" detach-device "$DOMAIN" "$XML" --live 2>/dev/null || true; rm -f "$XML"' EXIT

read -r _
kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true

echo "Detaching hostdev…"
virsh -c "$URI" detach-device "$DOMAIN" "$XML" --live || true
echo "Wrote $OUT ($(wc -c <"$OUT") bytes)"
echo "Open with: wireshark '$OUT'   filter hint: usb.transfer_type == 0x01"
