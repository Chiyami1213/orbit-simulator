#!/usr/bin/env bash
# Build "OrbSim.app" and a drag-to-Applications .dmg.  Must be run ON A MAC:   bash packaging/build_mac.sh
# Output goes to the project's release/ folder (git-ignored): release/OrbSim.app and release/OrbSim-<version>-macOS.dmg. Nothing is uploaded or released.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="1.0.0"
REL="$PWD/release"; OUT="${TMPDIR:-/tmp}/orbsim_build"
mkdir -p "$REL" "$OUT/work"

python3 -m pip install -r requirements-dev.txt
python3 packaging/make_icon.py                                   # writes assets/icons/icon.png (1024 px)

# .icns from the 1024 px PNG
ICONSET="$OUT/work/icon.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" assets/icons/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z "$((s * 2))" "$((s * 2))" assets/icons/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o assets/icons/icon.icns

python3 -m PyInstaller packaging/mathkit.spec --noconfirm --distpath "$REL" --workpath "$OUT/work"

APP="$REL/OrbSim.app"
# Ad-hoc signature: required for the app to run on Apple Silicon. It is NOT notarised (that needs a paid Apple Developer ID), so the first launch
# needs right-click > Open (see README).
codesign --force --deep --sign - "$APP"

STAGE="$OUT/work/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"; cp docs/help.html "$STAGE/Help.html"
DMG="$REL/OrbSim-$VERSION-macOS.dmg"
rm -f "$DMG"
hdiutil create -volname "OrbSim" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Disk image written to: $DMG"
