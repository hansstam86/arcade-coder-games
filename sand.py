#!/usr/bin/env python3
"""Falling Sand — a little physics sandbox for the Arcade Coder.

Pick an element from the bottom row and tap the play area to drop it, then
watch it come alive:

  * sand  falls and piles into slopes, and sinks through water
  * water falls, flows sideways and finds its level
  * stone is a solid, immovable wall
  * wood  is solid but flammable
  * fire  climbs, burns any wood it touches, and is put out by water

Bottom row = palette (sand, water, stone, wood, fire) + eraser + clear.

  python sand.py              # emulator
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = 12
BOTTOM = 10                       # rows 0..10 simulate; row 11 is the palette
EMPTY, SAND, WATER, STONE, WOOD, FIRE = 0, 1, 2, 3, 4, 5
PALETTE = [SAND, WATER, STONE, WOOD, FIRE]
ERASE_X, CLEAR_X = 10, 11
FIRE_LIFE = 22

COLORS = {
    SAND: (230, 200, 110), WATER: (30, 110, 255), STONE: (120, 120, 132),
    WOOD: (140, 90, 40), FIRE: (255, 120, 0),
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Sand(Game):
    fps = 18

    def start(self):
        self.g = [[EMPTY] * W for _ in range(12)]
        self.fire = [[0] * W for _ in range(12)]
        self.cur = SAND
        self.flip = False
        self.busy = False
        log("falling sand — pick an element, tap to drop")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if y == 11:                                   # palette row
            if x < len(PALETTE):
                self.cur = PALETTE[x]
            elif x == ERASE_X:
                self.cur = EMPTY
            elif x == CLEAR_X:
                self.g = [[EMPTY] * W for _ in range(12)]
                self.fire = [[0] * W for _ in range(12)]
            return
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):   # small brush
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny <= BOTTOM:
                self.g[ny][nx] = self.cur
                self.fire[ny][nx] = FIRE_LIFE if self.cur == FIRE else 0

    # -- physics -------------------------------------------------------------
    def _swap(self, x, y, nx, ny, moved):
        self.g[y][x], self.g[ny][nx] = self.g[ny][nx], self.g[y][x]
        self.fire[y][x], self.fire[ny][nx] = self.fire[ny][nx], self.fire[y][x]
        moved[ny][nx] = moved[y][x] = True

    def update(self, dt):
        g, fire = self.g, self.fire
        moved = [[False] * W for _ in range(12)]
        self.flip = not self.flip
        for y in range(BOTTOM, -1, -1):
            xr = range(W) if self.flip else range(W - 1, -1, -1)
            for x in xr:
                if moved[y][x]:
                    continue
                e = g[y][x]
                if e == SAND:
                    self._grain(x, y, moved, sink=True)
                elif e == WATER:
                    self._water(x, y, moved)
                elif e == FIRE:
                    self._fire(x, y, moved)

    def _grain(self, x, y, moved, sink):
        if y >= BOTTOM:
            return
        order = [0]
        order += [-1, 1] if self.flip else [1, -1]
        for k, dx in enumerate((0,) + tuple(order[1:])):
            nx, ny = x + dx, y + 1
            if not (0 <= nx < W):
                continue
            below = self.g[ny][nx]
            if below == EMPTY:
                self._swap(x, y, nx, ny, moved); return
            if sink and below == WATER and not moved[ny][nx]:      # sand sinks
                self._swap(x, y, nx, ny, moved); return

    def _water(self, x, y, moved):
        # straight down / diagonals first
        if y < BOTTOM:
            for dx in [0] + ([-1, 1] if self.flip else [1, -1]):
                nx = x + dx
                if not (0 <= nx < W):
                    continue
                b = self.g[y + 1][nx]
                if b == EMPTY:
                    self._swap(x, y, nx, y + 1, moved); return
                if b == FIRE:                        # pour water onto fire -> doused
                    self.g[y + 1][nx] = WATER; self.fire[y + 1][nx] = 0
                    self.g[y][x] = EMPTY
                    moved[y + 1][nx] = moved[y][x] = True
                    return
        # then flow sideways to find its level
        for dx in ([-1, 1] if self.flip else [1, -1]):
            nx = x + dx
            if 0 <= nx < W and self.g[y][nx] == EMPTY and not moved[y][nx]:
                self._swap(x, y, nx, y, moved); return

    def _fire(self, x, y, moved):
        g, fire = self.g, self.fire
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < W and 0 <= ny < 12):
                continue
            if g[ny][nx] == WATER:                    # doused
                g[y][x] = EMPTY; fire[y][x] = 0; return
            if g[ny][nx] == WOOD and random.random() < 0.28:
                g[ny][nx] = FIRE; fire[ny][nx] = FIRE_LIFE
        fire[y][x] -= 1
        if fire[y][x] <= 0:
            g[y][x] = EMPTY; return
        if y > 0 and g[y - 1][x] == EMPTY and random.random() < 0.4:   # flames rise
            self._swap(x, y, x, y - 1, moved)

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        for y in range(11):
            for x in range(W):
                e = self.g[y][x]
                if e == EMPTY:
                    screen.set(x, y, (2, 2, 6))
                elif e == FIRE:
                    f = self.fire[y][x] / FIRE_LIFE
                    flick = 0.7 + 0.3 * random.random()
                    screen.set(x, y, (255, int((60 + 140 * f) * flick), int(20 * f)))
                elif e == WATER:
                    sh = 0.85 + 0.15 * (0.5 + 0.5 * __import__("math").sin(now * 3 + x + y))
                    screen.set(x, y, tuple(int(c * sh) for c in COLORS[WATER]))
                else:
                    screen.set(x, y, COLORS[e])
        # palette
        for i, e in enumerate(PALETTE):
            c = COLORS[e]
            screen.set(i, 11, tuple(min(255, int(v * 1.3)) for v in c) if e == self.cur else c)
        screen.set(ERASE_X, 11, (200, 200, 200) if self.cur == EMPTY else (60, 60, 60))
        screen.set(CLEAR_X, 11, (150, 20, 20))


if __name__ == "__main__":
    run(Sand)
