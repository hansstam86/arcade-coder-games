#!/bin/bash
# Build bin/screencap — streams a tiny downsampled screen image (ambilight).
# Needs Screen Recording granted to the app bundle (same as the audio capture).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin
swiftc -O -target arm64-apple-macosx14.0 screencap.swift -o bin/screencap \
  -framework ScreenCaptureKit -framework CoreMedia -framework CoreVideo
echo "built bin/screencap"
