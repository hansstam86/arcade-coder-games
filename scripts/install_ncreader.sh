#!/bin/bash
# Install NCReader as a LaunchAgent so it reads the macOS Notification Center
# and POSTs to the ArcadeOS webhook. Grant Full Disk Access to NCReader.app.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/local.hans.arcade-ncreader.plist"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.hans.arcade-ncreader</string>
  <key>ProgramArguments</key>
  <array><string>$REPO/NCReader.app/Contents/MacOS/ncread</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "NCReader LaunchAgent installed. Now grant Full Disk Access to:"
echo "  $REPO/NCReader.app"
