#!/usr/bin/env python3
"""AeroFocus — the board as a directional focus pad for AeroSpace / Omachy.

The whole 12×12 is a D-pad. Tap a side to move window focus that way
(aerospace focus left/right/up/down); tap the centre to toggle mode between
FOCUS (cyan — move the highlight) and MOVE (orange — drag the focused window,
aerospace move …). After each action it flashes the name of the app you
landed on, so you always know where focus went.

  python aerofocus.py         # emulator (needs AeroSpace installed)
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
from marquee import render_columns

W = H = 12
AERO = shutil.which("aerospace") or "/opt/homebrew/bin/aerospace"

# Arrow triangles (cells) pointing outward from centre.
UP    = [(5, 1), (6, 1), (4, 2), (5, 2), (6, 2), (7, 2), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3)]
DOWN  = [(x, 11 - y) for (x, y) in UP]
LEFT  = [(y, x) for (x, y) in UP]
RIGHT = [(11 - y, x) for (x, y) in UP]
ARROWS = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT}
CENTER = [(5, 5), (6, 5), (5, 6), (6, 6)]

MODE_COL = {"focus": (0, 200, 255), "move": (255, 140, 0)}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _aero(*args):
    try:
        out = subprocess.run([AERO, *args], capture_output=True, text=True, timeout=3)
        return out.stdout.strip()
    except Exception:
        return ""


class AeroFocus(Game):
    fps = 20

    def start(self):
        self.ok = Path(AERO).exists()
        self.mode = "focus"
        self.flash_dir = None
        self.flash_until = 0.0
        self.cap_cols = []             # scrolling "you landed here" caption
        self.cap_off = 0.0
        self.busy = False
        log(f"aerofocus — D-pad ({'ready' if self.ok else 'aerospace not found'}, mode={self.mode})")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if not self.ok:
            return
        if 4 <= x <= 7 and 4 <= y <= 7:                 # centre = toggle mode
            self.mode = "move" if self.mode == "focus" else "focus"
            self._caption(self.mode.upper())
            log(f"aerofocus mode -> {self.mode}")
            return
        dx, dy = x - 5.5, y - 5.5
        if abs(dx) >= abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"
        self.flash_dir = direction
        self.flash_until = time.monotonic() + 0.22
        threading.Thread(target=self._act, args=(direction,), daemon=True).start()

    def _act(self, direction):
        _aero(self.mode, direction)                     # focus <dir> or move <dir>
        app = _aero("list-windows", "--focused", "--format", "%{app-name}")
        self._caption(app or direction.upper())
        log(f"aerofocus {self.mode} {direction} -> {app!r}")

    def _caption(self, text):
        self.cap_cols = render_columns(f" {text} ")
        self.cap_off = 12.0                             # start off the right edge

    def update(self, dt):
        if self.cap_cols:
            self.cap_off -= dt * 15.0                   # scroll left
            if self.cap_off < -len(self.cap_cols):
                self.cap_cols = []

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        if not self.ok:
            for x in range(W):
                screen.set(x, 5, (40, 0, 0)); screen.set(x, 6, (40, 0, 0))
            return

        # scrolling caption takes over the middle band for readability
        if self.cap_cols:
            base = int(self.cap_off)
            col = MODE_COL[self.mode]
            for i, bits in enumerate(self.cap_cols):
                cx = base + i
                if 0 <= cx < W:
                    for r in range(5):
                        if bits[r]:
                            screen.set(cx, 3 + r, col)
            return

        base = MODE_COL[self.mode]
        dim = tuple(int(c * 0.35) for c in base)
        for d, cells in ARROWS.items():
            hot = d == self.flash_dir and now < self.flash_until
            col = (255, 255, 255) if hot else dim
            for (cx, cy) in cells:
                screen.set(cx, cy, col)
        for (cx, cy) in CENTER:                          # centre shows current mode
            screen.set(cx, cy, base)


if __name__ == "__main__":
    run(AeroFocus)
