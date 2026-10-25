#!/usr/bin/env bash
# Dev install: udev rules + user systemd unit for flydigi-vader4d.
# Prefer distro packages when available — see packaging/README.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RULES_SRC="$ROOT/udev/99-flydigi-vader4.rules"
UNIT_SRC="$ROOT/packaging/systemd/flydigi-vader4d.service"
UNIT_DST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/flydigi-vader4d.service"

echo "Installing udev rules (pkexec)…"
pkexec bash -c "install -m 0644 '$RULES_SRC' /etc/udev/rules.d/99-flydigi-vader4.rules && udevadm control --reload-rules && udevadm trigger"

mkdir -p "$(dirname "$UNIT_DST")"
# Point ExecStart at this checkout’s driver.
sed "s|^ExecStart=.*|ExecStart=/usr/bin/python3 $ROOT/driver/flydigi_vader4d.py|" \
  "$UNIT_SRC" >"$UNIT_DST"
# Keep WorkingDirectory for relative imports when not installed as a package.
if ! grep -q '^WorkingDirectory=' "$UNIT_DST"; then
  sed -i "/^\[Service\]/a WorkingDirectory=$ROOT" "$UNIT_DST"
fi

systemctl --user daemon-reload
systemctl --user enable --now flydigi-vader4d.service
echo "Installed. Status:"
systemctl --user status flydigi-vader4d.service --no-pager || true
echo
echo "Re-plug the controller (or: sudo udevadm trigger). Then: evtest  # pick 'Flydigi Vader 4 Pro'"
