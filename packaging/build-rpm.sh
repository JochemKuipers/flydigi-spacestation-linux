#!/usr/bin/env bash
# Build .rpm packages (requires rpmbuild).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
BUILD="$ROOT/build/rpm"
NAME="flydigi-spacestation-linux"

rm -rf "$BUILD"
mkdir -p "$BUILD"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

# Upstream tarball expected by the spec (%autosetup -n flydigi-spacestation-linux-%{version}).
tar -C "$ROOT/.." -czf "$BUILD/SOURCES/${NAME}-${VERSION}.tar.gz" \
  --transform "s#^$(basename "$ROOT")#${NAME}-${VERSION}#" \
  --exclude='.git' --exclude='build' --exclude='dist' --exclude='vendor' \
  --exclude='.wine*' --exclude='captures' --exclude='__pycache__' \
  --exclude='*.egg-info' --exclude='.ruff_cache' \
  "$(basename "$ROOT")"

cp "$ROOT/packaging/rpm/flydigi-vader.spec" "$BUILD/SPECS/"
# Sync version into spec if VERSION file changed.
sed -i "s/^Version:.*/Version:        ${VERSION}/" "$BUILD/SPECS/flydigi-vader.spec"

rpmbuild --define "_topdir $BUILD" -bb "$BUILD/SPECS/flydigi-vader.spec"
mkdir -p "$ROOT/dist"
find "$BUILD/RPMS" -name '*.rpm' -exec cp -a {} "$ROOT/dist/" \;
ls -la "$ROOT/dist"/*.rpm
