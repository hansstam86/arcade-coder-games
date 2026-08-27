#!/usr/bin/env python3
"""LayoutCtl — AeroSpace / Omachy layout controls on the board.

A 2×3 grid of the six common AeroSpace layout actions. Tap a tile to run it
on the focused workspace; the tile flashes white to confirm.

  ┌ TILES ─┬ STACK ─┐   tiles⇄  · accordion⇄
  ├ FLOAT ─┼ FULL  ─┤   float⇄  · fullscreen
  └ FLAT  ─┴ EQ    ─┘   flatten  · balance-sizes

  python layoutctl.py         # emulator (needs AeroSpace installed)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12
AERO = shutil.which("aerospace") or "/opt/homebrew/bin/aerospace"

# each icon is a list of (dx, dy) lit cells inside a 6-wide × 4-tall tile
I_TILES = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3),
           (3, 0), (3, 1), (3, 2), (3, 3), (4, 0), (4, 1), (4, 2), (4, 3)]
I_STACK = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (1, 1), (2, 1), (3, 1), (4, 1),
           (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (1, 3), (2, 3), (3, 3), (4, 3)]
I_FLOAT = [(2, 0), (3, 0), (4, 0), (2, 1), (3, 1), (4, 1),
           (3, 2), (4, 2), (5, 2), (3, 3), (4, 3), (5, 3)]
I_FULL  = [(x, 0) for x in range(6)] + [(x, 3) for x in range(6)] + \
          [(0, 1), (0, 2), (5, 1), (5, 2)]
I_FLAT  = [(0, 0), (1, 0), (3, 0), (4, 0),
           (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3)]
I_EQ    = [(1, 0), (1, 1), (1, 2), (1, 3), (4, 0), (4, 1), (4, 2), (4, 3), (2, 3), (3, 3)]

#            name        aerospace args                              colour        icon
ACTIONS = [
    ("TILES",   ["layout", "tiles", "horizontal", "vertical"],     (0, 200, 180),  I_TILES),
    ("STACK",   ["layout", "accordion", "horizontal", "vertical"], (170, 80, 255), I_STACK),
    ("FLOAT",   ["layout", "floating", "tiling"],                  (255, 210, 0),  I_FLOAT),
    ("FULL",    ["fullscreen"],                                    (255, 60, 60),  I_FULL),
    ("FLATTEN", ["flatten-workspace-tree"],                        (0, 150, 255),  I_FLAT),
    ("EQ",      ["balance-sizes"],                                 (0, 220, 90),   I_EQ),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _aero(args):
    try:
        subprocess.run([AERO, *args], capture_output=True, text=True, timeout=3)
    except Exception:
        pass


class LayoutCtl(Game):
    fps = 20

    def start(self):
        self.ok = Path(AERO).exists()
        self.flash_idx = None
        self.flash_until = 0.0
        self.busy = False
        log(f"layout — AeroSpace layout deck ({'ready' if self.ok else 'aerospace not found'})")

    def on_press(self, x, y):
        if not self.ok:
            return
        idx = (y // 4) * 2 + (0 if x < 6 else 1)
        if idx >= len(ACTIONS):
            return
        name, args, _col, _icon = ACTIONS[idx]
        self.flash_idx = idx
        self.flash_until = time.monotonic() + 0.3
        threading.Thread(target=lambda: _aero(args), daemon=True).start()
        log(f"layout -> {name} ({' '.join(args)})")

    def update(self, dt):
        pass

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        if not self.ok:
            for x in range(W):
                screen.set(x, 5, (40, 0, 0)); screen.set(x, 6, (40, 0, 0))
            return
        for idx, (name, args, col, icon) in enumerate(ACTIONS):
            ox, oy = (idx % 2) * 6, (idx // 2) * 4
            hot = idx == self.flash_idx and now < self.flash_until
            bg = (30, 30, 30) if hot else tuple(int(c * 0.14) for c in col)
            for dy in range(4):
                for dx in range(6):
                    screen.set(ox + dx, oy + dy, bg)
            ink = (255, 255, 255) if hot else col
            for (dx, dy) in icon:
                screen.set(ox + dx, oy + dy, ink)


if __name__ == "__main__":
    run(LayoutCtl)
