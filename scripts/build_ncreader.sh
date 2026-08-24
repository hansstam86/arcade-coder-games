#!/bin/bash
# Build NCReader.app — the notification-center reader. macOS ties Full Disk
# Access to the accessing binary's BUNDLE identity, and honours it only when
# the app is launched via LaunchServices (`open`), which ArcadeOS does. The
# deployment target must be <= the running macOS or LaunchServices rejects it.
set -euo pipefail
cd "$(dirname "$0")/.."
APP=NCReader.app
mkdir -p "$APP/Contents/MacOS"
swiftc -O -target arm64-apple-macosx14.0 ncread.swift -o "$APP/Contents/MacOS/ncread" -lsqlite3
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>NCReader</string>
  <key>CFBundleIdentifier</key><string>local.hans.arcade-ncreader</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>ncread</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
</dict>
</plist>
PL
codesign --force --deep -s - "$APP"
echo "Built $APP. Grant it Full Disk Access (System Settings > Privacy & Security"
echo "> Full Disk Access > +, add $(pwd)/$APP), then relaunch ArcadeOS."
