#!/usr/bin/env bash
# Install udev rules + user systemd unit for flydigi-vader4d on CachyOS/Arch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RULES_SRC="$ROOT/udev/99-flydigi-vader4.rules"
UNIT_DST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/flydigi-vader4d.service"

echo "Installing udev rules (pkexec)…"
pkexec bash -c "install -m 0644 '$RULES_SRC' /etc/udev/rules.d/99-flydigi-vader4.rules && udevadm control --reload-rules && udevadm trigger"

mkdir -p "$(dirname "$UNIT_DST")"
cat >"$UNIT_DST" <<EOF
[Unit]
Description=Flydigi Vader 4 Pro DInput userspace driver
After=systemd-udevd.service

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 $ROOT/driver/flydigi_vader4d.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now flydigi-vader4d.service
echo "Installed. Status:"
systemctl --user status flydigi-vader4d.service --no-pager || true
echo
echo "Re-plug the controller (or: sudo udevadm trigger). Then: evtest  # pick 'Flydigi Vader 4 Pro'"
