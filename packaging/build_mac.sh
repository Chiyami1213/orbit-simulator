#!/usr/bin/env bash
# Build "Orbit Simulator.app" and a drag-to-Applications .dmg.  Must be run ON A MAC:   bash packaging/build_mac.sh
# Output goes to ~/Library/Application Support/Orbit Simulator/build (not into the repository). Nothing is uploaded or released.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="1.0.0"
OUT="$HOME/Library/Application Support/Orbit Simulator/build"
mkdir -p "$OUT/dist" "$OUT/work" "$OUT/installer"

python3 -m pip install -r requirements-dev.txt
python3 packaging/make_icon.py                                   # writes packaging/icon.png (1024 px)

# .icns from the 1024 px PNG
ICONSET="$OUT/work/icon.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" packaging/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z "$((s * 2))" "$((s * 2))" packaging/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o packaging/icon.icns

python3 -m PyInstaller packaging/mathkit.spec --noconfirm --distpath "$OUT/dist" --workpath "$OUT/work"

APP="$OUT/dist/Orbit Simulator.app"
# Ad-hoc signature: required for the app to run on Apple Silicon. It is NOT notarised (that needs a paid Apple Developer ID), so the first launch
# needs right-click > Open (see README).
codesign --force --deep --sign - "$APP"

STAGE="$OUT/work/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"; cp docs/help.html "$STAGE/Help.html"
DMG="$OUT/installer/OrbitSimulator-$VERSION-macOS.dmg"
rm -f "$DMG"
hdiutil create -volname "Orbit Simulator" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Disk image written to: $DMG"
