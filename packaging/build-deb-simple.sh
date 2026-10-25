#!/usr/bin/env bash
# Build .deb packages from staged FHS trees.
# Prefers dpkg-deb; falls back to tar+ar (works on Arch without the dpkg package).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
DIST="$ROOT/dist"
BUILD="$ROOT/build/deb-simple"

rm -rf "$BUILD"
mkdir -p "$DIST" "$BUILD"

pack_deb() {
  local root="$1" out="$2"
  if command -v dpkg-deb >/dev/null; then
    dpkg-deb --root-owner-group --build "$root" "$out"
    return
  fi
  command -v ar >/dev/null || {
    echo "Need dpkg-deb or binutils ar to build .deb files" >&2
    exit 1
  }
  local work
  work="$(mktemp -d)"
  (
    cd "$root"
    tar --owner=0 --group=0 --numeric-owner \
      --exclude='./DEBIAN' -cJf "$work/data.tar.xz" .
    cd DEBIAN
    tar --owner=0 --group=0 --numeric-owner -cJf "$work/control.tar.xz" .
  )
  printf '2.0\n' >"$work/debian-binary"
  rm -f "$out"
  (
    cd "$work"
    ar r "$out" debian-binary control.tar.xz data.tar.xz
  )
  rm -rf "$work"
  echo "built $out (ar fallback)"
}

stage_and_pack() {
  local name="$1" what="$2" depends="$3" desc="$4"
  local stage="$BUILD/stage-$name"
  local root="$BUILD/$name"

  python3 "$ROOT/packaging/stage.py" "$what" --layout dist-packages --out "$stage"
  rm -rf "$root"
  mkdir -p "$root"
  cp -a "$stage"/. "$root"/
  mkdir -p "$root/DEBIAN"
  local installed_size
  installed_size="$(du -sk "$root" | awk '{print $1}')"
  cat >"$root/DEBIAN/control" <<EOF
Package: ${name}
Version: ${VERSION}-1
Section: utils
Priority: optional
Architecture: all
Maintainer: Jochem Kuipers <jochem@localhost>
Installed-Size: ${installed_size}
Depends: ${depends}
Description: ${desc}
EOF
  if [[ "$name" == "flydigi-vader4d" ]]; then
    cat >"$root/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
  if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger || true
  fi
  echo "Enable the driver with: systemctl --user enable --now flydigi-vader4d.service"
fi
EOF
    chmod 755 "$root/DEBIAN/postinst"
  fi
  pack_deb "$root" "$DIST/${name}_${VERSION}-1_all.deb"
}

stage_and_pack flydigi-vader4d driver \
  "python3, python3-evdev, udev" \
  "Userspace DInput driver for Flydigi Vader 4 Pro"

stage_and_pack vader-companion companion \
  "python3, python3-evdev, python3-pyside6.qtwidgets | python3-pyside6, flydigi-vader4d" \
  "Vader Companion for Flydigi Vader 4 Pro"

ls -la "$DIST"/*.deb
