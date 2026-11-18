#!/usr/bin/env python3
"""Game of Life — Conway's colony on 144 LEDs.

Classic B3/S23 on a 12x12 board that wraps at the edges (a torus — small
worlds need it). Cells are coloured by age: newborns flash bright green,
then age through cyan, blue, purple and pink to red elders, so waves of
generations are visible moving through the colony.

Pads (marked with dim HUD pixels):
  top-left     play/pause (green when running, red when paused)
  top-right    cycle speed: 1 / 2 / 5 / 10 generations per second
  top-centre   load the next preset pattern (glider, LWSS, acorn, ...)
  bottom-left  clear the world
  bottom-right random soup
Every other pad toggles that cell — you can poke the colony live while
it runs. When the world goes still (or extinct) it re-seeds itself after
a few seconds, so it works as a desk object.

life.json (auto-created, hot-reloads): speeds, wrap, autoseed,
stasis_seconds, soup_density.

  python life.py            # emulator at http://127.0.0.1:7777
  python life.py --hw       # real board over BLE
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "life.json"

DEFAULT = {
    "speeds": [1, 2, 5, 10],   # generations per second, cycled by pad
    "speed_index": 2,
    "wrap": True,               # torus edges (false = walls of death)
    "autoseed": True,           # reseed after stasis / extinction
    "stasis_seconds": 6.0,
    "soup_density": 0.28,
}

W = H = 12

# age → colour: green newborns cooling through blue/purple to red elders
AGE_COLORS = (
    (20, 255, 30),
    (0, 235, 150),
    (0, 190, 235),
    (70, 140, 255),
    (150, 90, 255),
    (230, 60, 220),
    (255, 60, 110),
)

PAUSE_PAD = (0, 0)
SPEED_PAD = (11, 0)
PATTERN_PAD = (6, 0)
CLEAR_PAD = (0, 11)
SOUP_PAD = (11, 11)

# presets: (name, cells) — placed centred on the board
PATTERNS = (
    ("glider", ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2))),
    ("blinker", ((0, 0), (1, 0), (2, 0))),
    ("toad", ((1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1))),
    ("beacon", ((0, 0), (1, 0), (0, 1), (3, 2), (2, 3), (3, 3))),
    ("LWSS", ((0, 0), (3, 0), (4, 1), (0, 2), (4, 2), (1, 3), (2, 3), (3, 3), (4, 3))),
    ("pentadecathlon", tuple((x, 1) for x in range(8))),   # 8-in-a-row: settles into it
    ("R-pentomino", ((1, 0), (2, 0), (0, 1), (1, 1), (1, 2))),
    ("acorn", ((1, 0), (3, 1), (0, 2), (1, 2), (4, 2), (5, 2), (6, 2))),
    ("diehard", ((6, 0), (0, 1), (1, 1), (1, 2), (5, 2), (6, 2), (7, 2))),
)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Life(Game):
    fps = 20

    def start(self):
        self._load()
        self.grid = [[0] * W for _ in range(H)]
        self.age = [[0] * W for _ in range(H)]
        self.acc = 0.0
        self.stasis = 0.0
        self.dead_t = 0.0
        self.last_key = None
        self.running = True
        self.pattern_idx = 0
        self.next_check = 0.0
        self.soup()
        log("game of life — top-left pause, top-right speed, top-centre "
            "pattern, bottom-left clear, bottom-right soup; other pads "
            "toggle cells live")

    # -- config --------------------------------------------------------------
    def _load(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        else:
            CONFIG_PATH.write_text(json.dumps(DEFAULT, indent=2) + "\n")
        try:
            self.mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            self.mtime = 0.0

    @property
    def gps(self) -> float:
        speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
        i = min(int(self.cfg.get("speed_index", 2)), len(speeds) - 1)
        return float(speeds[i])

    # -- world ----------------------------------------------------------------
    def soup(self) -> None:
        d = float(self.cfg.get("soup_density", 0.28))
        self.grid = [[1 if random.random() < d else 0 for _ in range(W)] for _ in range(H)]
        self.age = [[0] * W for _ in range(H)]
        self.stasis = 0.0
        self.dead_t = 0.0
        log("random soup")

    def load_pattern(self, idx: int) -> None:
        name, cells = PATTERNS[idx % len(PATTERNS)]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        ox, oy = (W - (max(xs) - min(xs) + 1)) // 2 - min(xs), (H - (max(ys) - min(ys) + 1)) // 2 - min(ys)
        self.grid = [[0] * W for _ in range(H)]
        self.age = [[0] * W for _ in range(H)]
        for x, y in cells:
            self.grid[(y + oy) % H][(x + ox) % W] = 1
        self.stasis = 0.0
        self.dead_t = 0.0
        log(f"pattern -> {name}")

    def clear(self) -> None:
        self.grid = [[0] * W for _ in range(H)]
        self.age = [[0] * W for _ in range(H)]
        self.stasis = 0.0
        self.dead_t = 0.0
        log("world cleared")

    def _neighbours(self, x: int, y: int) -> int:
        wrap = bool(self.cfg.get("wrap", True))
        n = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if wrap:
                    nx, ny = nx % W, ny % H
                elif not (0 <= nx < W and 0 <= ny < H):
                    continue
                n += self.grid[ny][nx]
        return n

    def _step(self) -> None:
        g, a = self.grid, self.age
        new = [[0] * W for _ in range(H)]
        new_age = [[0] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                n = self._neighbours(x, y)
                if g[y][x]:
                    if n in (2, 3):
                        new[y][x] = 1
                        new_age[y][x] = min(a[y][x] + 1, len(AGE_COLORS) - 1)
                elif n == 3:
                    new[y][x] = 1                     # newborn, age 0
        self.grid, self.age = new, new_age

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == PAUSE_PAD:
            self.running = not self.running
            log("paused" if not self.running else "running")
        elif (x, y) == SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 2)) + 1) % len(speeds)
            log(f"speed -> {self.gps:g} generations/s")
        elif (x, y) == PATTERN_PAD:
            self.pattern_idx = (self.pattern_idx + 1) % len(PATTERNS)
            self.load_pattern(self.pattern_idx)
        elif (x, y) == CLEAR_PAD:
            self.clear()
        elif (x, y) == SOUP_PAD:
            self.soup()
        else:
            self.grid[y][x] = 0 if self.grid[y][x] else 1
            if self.grid[y][x]:
                self.age[y][x] = 0
            self.stasis = 0.0

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.acc += dt
            interval = 1.0 / max(0.1, self.gps)
            while self.acc >= interval:
                self.acc -= interval
                self._step()
        key = tuple(tuple(row) for row in self.grid)
        if key == self.last_key:
            self.stasis += dt
        else:
            self.stasis = 0.0
            self.last_key = key
        self.dead_t = 0.0 if any(any(r) for r in self.grid) else self.dead_t + dt
        if bool(self.cfg.get("autoseed", True)):
            if self.dead_t > 2.0:
                log("extinct — reseeding")
                self.soup()
            elif self.stasis > float(self.cfg.get("stasis_seconds", 6.0)) and any(any(r) for r in self.grid):
                log("stasis — sprinkling fresh soup")
                self.soup()
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("life.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        screen.clear((0, 0, 0) if self.running else (3, 6, 14))
        for y in range(H):
            for x in range(W):
                if self.grid[y][x]:
                    screen.set(x, y, AGE_COLORS[min(self.age[y][x], len(AGE_COLORS) - 1)])
        # HUD pads
        screen.set(*PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*SPEED_PAD, (30, 90, 230))
        screen.set(*PATTERN_PAD, (240, 140, 20))
        screen.set(*CLEAR_PAD, (60, 60, 60))
        screen.set(*SOUP_PAD, (190, 60, 230))


if __name__ == "__main__":
    run(Life)