#!/bin/bash
# Sync the Python sources into docs/py for the GitHub Pages web IDE.
# Examples get their local sys.path shim stripped (the IDE sets paths itself).
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p docs/py/arcadecoder docs/py/examples
cp arcadecoder/__init__.py arcadecoder/runner.py arcadecoder/protocol.py docs/py/arcadecoder/
cp arcade.py minesweeper.py whackamole.py docs/py/

for f in chase snake; do
  sed '/^import sys$/d; /^from pathlib import Path$/d; /^sys\.path\.insert/d' \
    "examples/$f.py" > "docs/py/examples/$f.py"
done
sed '/^import sys$/d; /^from pathlib import Path$/d; /^sys\.path\.insert/d' \
  examples/full_arcade.py > docs/py/examples/full_arcade.py

cp deck_editor.html docs/deck.html
cp deck.json docs/deck_sample.json
cp kopads_editor.html docs/kopads.html
cp kopads.json docs/kopads_sample.json
cp arcadeos_dashboard.html docs/arcadeos.html

echo "synced $(ls docs/py docs/py/arcadecoder docs/py/examples | wc -l | tr -d ' ') files into docs/py"
