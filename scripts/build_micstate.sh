#!/bin/bash
# Build bin/micstate — reports whether any audio input device is in use.
# No TCC/entitlements needed (it only reads device state, never captures audio).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin
swiftc -O -target arm64-apple-macosx14.0 micstate.swift -o bin/micstate -framework CoreAudio
echo "built bin/micstate — idle reads: $(./bin/micstate)"
