#!/usr/bin/env bash
# Build a Vader Companion AppImage (x86_64).
# Requires: python3, pip, wget/curl; downloads appimagetool if missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/VaderCompanion.AppDir"
ARCH="${ARCH:-x86_64}"

rm -rf "$BUILD"
mkdir -p "$APPDIR"

echo "==> Staging companion into AppDir (bundled flydigi)"
python3 "$ROOT/packaging/stage.py" companion --bundle-flydigi --out "$APPDIR"

# AppImage runtime expects usr/ under AppDir (already staged that way).
mkdir -p "$APPDIR/usr/share/metainfo"
cat >"$APPDIR/vader-companion.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vader Companion
Exec=vader-companion
Icon=vader-companion
Categories=Utility;Settings;
Terminal=false
EOF
cp -f "$APPDIR/usr/share/icons/hicolor/scalable/apps/vader-companion.svg" \
  "$APPDIR/vader-companion.svg"

# Bundle a venv of runtime deps into the AppDir.
echo "==> Installing Python deps into AppDir"
python3 -m venv "$APPDIR/usr/venv"
"$APPDIR/usr/venv/bin/pip" install -q --upgrade pip
"$APPDIR/usr/venv/bin/pip" install -q "PySide6>=6.5" "evdev>=1.6"

# AppRun: prefer AppDir site-packages + venv.
cat >"$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$HERE/usr/venv/bin:${PATH:-}"
export PYTHONPATH="$HERE/usr/lib/python3/dist-packages:$HERE/usr/lib/python3.*/site-packages:${PYTHONPATH:-}"
# Pick the staged site-packages for this interpreter.
PYVER="$("$HERE/usr/venv/bin/python3" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
for cand in \
  "$HERE/usr/lib/python${PYVER}/site-packages" \
  "$HERE/usr/lib/python${PYVER}/dist-packages"
do
  if [ -d "$cand" ]; then
    export PYTHONPATH="$cand:${PYTHONPATH}"
    break
  fi
done
exec "$HERE/usr/venv/bin/python3" -m app.vader_companion "$@"
EOF
chmod 755 "$APPDIR/AppRun"

# Rewrite wrapper to use venv python via AppRun only; keep usr/bin for desktop.
cat >"$APPDIR/usr/bin/vader-companion" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")/../.."
exec "$HERE/AppRun" "$@"
EOF
chmod 755 "$APPDIR/usr/bin/vader-companion"

TOOL="$BUILD/appimagetool"
if [[ ! -x "$TOOL" ]]; then
  echo "==> Fetching appimagetool"
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  curl -fsSL "$URL" -o "$TOOL"
  chmod +x "$TOOL"
fi

OUT="$ROOT/dist/Vader_Companion-${VERSION}-${ARCH}.AppImage"
mkdir -p "$ROOT/dist"
echo "==> Packing $OUT"
ARCH="$ARCH" "$TOOL" "$APPDIR" "$OUT"
echo "Built $OUT"
echo "Note: the driver (flydigi-vader4d) is a separate system package and is not bundled."
