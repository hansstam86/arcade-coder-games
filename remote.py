#!/usr/bin/env python3
"""Remote — an AI-controlled canvas for the Arcade Coder.

ArcadeOS's dashboard `POST /paint` pushes a 12x12 frame here, so an external
agent (e.g. NanoClaw / Claude on the Mac mini) can draw anything on the board.
Frames can be sent as 12 rows of a colour-letter alphabet (easy for an AI to
author, like ASCII art) or as raw [r,g,b] pixels.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12

# single-letter palette so an agent can paint with plain text
PALETTE = {
    ".": (0, 0, 0), " ": (0, 0, 0), "-": (0, 0, 0),
    "r": (255, 30, 30), "g": (0, 220, 60), "b": (0, 90, 255), "y": (255, 220, 0),
    "o": (255, 120, 0), "c": (0, 220, 220), "m": (255, 0, 150), "p": (150, 0, 255),
    "w": (255, 255, 255), "k": (255, 120, 180), "n": (150, 80, 30), "a": (110, 110, 120),
    "d": (40, 40, 50),
}

_frame = [(0, 0, 0)] * 144


def set_rows(rows) -> None:
    global _frame
    f = [(0, 0, 0)] * 144
    for y, row in enumerate(list(rows)[:H]):
        for x, ch in enumerate(str(row)[:W]):
            f[y * W + x] = PALETTE.get(ch.lower(), (0, 0, 0))
    _frame = f


def set_pixels(px) -> None:
    global _frame
    f = [(0, 0, 0)] * 144
    for i, p in enumerate(list(px)[:144]):
        try:
            f[i] = (int(p[0]) & 255, int(p[1]) & 255, int(p[2]) & 255)
        except Exception:
            pass
    _frame = f


class Remote(Game):
    fps = 10

    def start(self):
        self.busy = True          # hold whatever the agent painted

    def draw(self, screen):
        screen.px = list(_frame)


if __name__ == "__main__":
    run(Remote)
