#!/usr/bin/env python3
"""Doodle pad — free-draw on the Arcade Coder.

Tap any pad in the drawing area (rows 0–10) to paint it with the current
colour. The bottom row is the toolbar:

  cols 0–9  : the colour palette (tap to pick; the active one pulses)
  col 10    : eraser (paint black)
  col 11    : clear the whole canvas

Your drawing persists to doodle.json, so it's still there next time.

  python doodle.py            # emulator
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "doodle.json"
W = H = 12
TOOL_ROW = 11

PALETTE = [
    (255, 255, 255), (255, 40, 40), (255, 140, 0), (255, 230, 0),
    (0, 220, 60), (0, 220, 220), (0, 120, 255), (150, 0, 255),
    (255, 0, 150), (150, 80, 30),
]
ERASE_X = 10
CLEAR_X = 11


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Doodle(Game):
    fps = 8

    def start(self):
        self.canvas = [[(0, 0, 0)] * W for _ in range(H)]
        self.color_idx = 0
        self.erasing = False
        self.busy = True             # keep the art on screen; don't idle away
        self.dirty = False
        self.last_save = time.monotonic()
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text())
                px = data.get("canvas")
                if isinstance(px, list) and len(px) == H:
                    self.canvas = [[tuple(c) for c in row] for row in px]
                self.color_idx = int(data.get("color", 0)) % len(PALETTE)
            except Exception:
                pass
        log("doodle ready — tap to draw; bottom row = palette / eraser / clear")

    # -- persistence ---------------------------------------------------------
    def _save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(
                {"canvas": self.canvas, "color": self.color_idx}) + "\n")
            self.dirty = False
            self.last_save = time.monotonic()
        except Exception:
            pass

    def stop(self) -> None:
        if self.dirty:
            self._save()

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if y == TOOL_ROW:                       # toolbar
            if x < len(PALETTE):
                self.color_idx = x
                self.erasing = False
            elif x == ERASE_X:
                self.erasing = True
            elif x == CLEAR_X:
                self.canvas = [[(0, 0, 0)] * W for _ in range(H)]
                self.dirty = True
            return
        self.canvas[y][x] = (0, 0, 0) if self.erasing else PALETTE[self.color_idx]
        self.dirty = True

    def update(self, dt):
        if self.dirty and time.monotonic() - self.last_save > 1.5:
            self._save()

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        for y in range(TOOL_ROW):               # the canvas (rows 0..10)
            for x in range(W):
                screen.set(x, y, self.canvas[y][x])
        pulse = 0.55 + 0.45 * abs((now * 1.5) % 2 - 1)
        for x, c in enumerate(PALETTE):         # palette swatches
            sel = (not self.erasing) and x == self.color_idx
            screen.set(x, TOOL_ROW, tuple(min(255, int(v * pulse + 60)) for v in c)
                       if sel else c)
        # eraser: dark, pulses when active
        e = int(90 * pulse) if self.erasing else 40
        screen.set(ERASE_X, TOOL_ROW, (e, e, e))
        # clear: a red button
        screen.set(CLEAR_X, TOOL_ROW, (150, 20, 20))


if __name__ == "__main__":
    run(Doodle)
