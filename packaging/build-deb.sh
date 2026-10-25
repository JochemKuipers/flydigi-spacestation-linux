#!/usr/bin/env bash
# Build .deb packages from a clean tree (requires dpkg-dev / debhelper).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/deb"
VERSION="$(cat "$ROOT/VERSION")"
NAME="flydigi-vader_${VERSION}"

rm -rf "$BUILD"
mkdir -p "$BUILD/$NAME"
# Copy sources (exclude heavy/irrelevant trees).
rsync -a --delete \
  --exclude '.git' --exclude 'build' --exclude 'dist' --exclude 'vendor' \
  --exclude '.wine*' --exclude 'captures' --exclude '__pycache__' \
  --exclude '*.egg-info' --exclude '.ruff_cache' \
  "$ROOT/" "$BUILD/$NAME/"

# Debian expects ./debian at the package root.
rm -rf "$BUILD/$NAME/debian"
cp -a "$ROOT/packaging/debian" "$BUILD/$NAME/debian"
chmod 755 "$BUILD/$NAME/debian/rules"
chmod 755 "$BUILD/$NAME/debian/flydigi-vader4d.postinst"

cd "$BUILD/$NAME"
dpkg-buildpackage -us -uc -b
mkdir -p "$ROOT/dist"
cp -a "$BUILD"/flydigi-vader4d_*.deb "$BUILD"/vader-companion_*.deb "$ROOT/dist/" 2>/dev/null \
  || cp -a "$BUILD"/*.deb "$ROOT/dist/"
ls -la "$ROOT/dist"/*.deb
