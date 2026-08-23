#!/bin/bash
# Install a LaunchAgent so ArcadeOS starts when you log in.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/local.hans.arcadeos.plist"
echo arcadeos_hw.py > "$REPO/launch_target.txt"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.hans.arcadeos</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/open</string><string>$REPO/ArcadeMinesweeper.app</string></array>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "installed — ArcadeOS will start at login (remove with: launchctl unload $PLIST && rm $PLIST)"
