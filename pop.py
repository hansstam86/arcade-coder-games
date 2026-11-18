#!/usr/bin/env python3
"""Pop! — SameGame on 144 buttons. Press a cluster, watch it burst and rain.

Classic rules: press any group of 2 or more orthogonally-connected
same-coloured cells and the whole group pops, scoring (n-2)^2.
Everything above falls — one animated cell at a time, with dim motion
trails, so the collapse is half the show. Press a lone tile and it
blinks "nope" at you.

When no groups remain the board dims and the run ends; clear every
last tile for a PERFECT CLEAR (+1000) and a rainbow sweep. Any press
starts a fresh board.

Fully turn-based — the hardware's frame pace cannot hurt it.

pop.json (auto-created, hot-reloads): colors, flash_seconds,
fall_step.

  python pop.py                # emulator at http://127.0.0.1:7777
  python pop.py --hw           # real board over BLE
"""

from __future__ import annotations

import colorsys
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "pop.json"

DEFAULT = {
    "colors": 5,
    "flash_seconds": 0.35,      # the pop burst
    "fall_step": 0.06,          # seconds per gravity micro-step
}

COLORS = (
    (255, 60, 80),              # candy red
    (255, 190, 40),              # gold
    (80, 230, 70),               # lime
    (50, 220, 255),              # cyan
    (200, 70, 255),              # magenta
)
EMPTY = 0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Pop(Game):
    fps = 20

    def start(self):
        self._load()
        self.t = 0.0
        self.rnd = random.Random()
        self.next_check = 0.0
        self.new_game()
        log("pop! — press any cluster of 2+ to pop it; clear the board "
            "for a perfect clear")

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

    # -- game --------------------------------------------------------------------
    def new_game(self) -> None:
        n = max(2, min(len(COLORS), int(self.cfg.get("colors", 5))))
        self.grid = [[self.rnd.randrange(1, n + 1) for _ in range(W)]
                     for _ in range(H)]
        self.state = "play"
        self.score = 0
        self.popped: list[tuple[int, int]] = []
        self.pop_until = 0.0
        self.nope_cell = None
        self.nope_until = 0.0
        self.ghosts: dict[tuple[int, int], int] = {}
        self.fall_acc = 0.0

    def _flood(self, x: int, y: int) -> list:
        """Orthogonally-connected group of the same colour (empty-aware)."""
        color = self.grid[y][x]
        if color == EMPTY:
            return []
        seen = {(x, y)}
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen:
                    if self.grid[ny][nx] == color:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
        return list(seen)

    def has_moves(self) -> bool:
        for y in range(H):
            for x in range(W):
                c = self.grid[y][x]
                if c == EMPTY:
                    continue
                if x + 1 < W and self.grid[y][x + 1] == c:
                    return True
                if y + 1 < H and self.grid[y + 1][x] == c:
                    return True
        return False

    def _gravity_step(self) -> bool:
        """One micro-step of gravity: every floating tile drops one cell."""
        moved = False
        self.ghosts = {}
        for x in range(W):
            for y in range(H - 2, -1, -1):
                c = self.grid[y][x]
                if c != EMPTY and self.grid[y + 1][x] == EMPTY:
                    self.grid[y + 1][x] = c
                    self.grid[y][x] = EMPTY
                    self.ghosts[(x, y)] = c
                    moved = True
        return moved

    def _settle(self) -> None:
        if not self.has_moves():
            remaining = sum(1 for row in self.grid for c in row if c != EMPTY)
            if remaining == 0:
                self.score += 1000
                self.state = "cleared"
                log(f"PERFECT CLEAR! +1000 — score {self.score}")
            else:
                self.state = "over"
                log(f"game over — {remaining} tiles left, score {self.score}")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if self.state in ("over", "cleared"):
            self.new_game()
            return
        if self.state != "play":
            return
        color = self.grid[y][x]
        if color == EMPTY:
            return
        group = self._flood(x, y)
        if len(group) < 2:
            self.nope_cell = (x, y, color)
            self.nope_until = self.t + 0.6
            log("nope — that tile has no neighbours")
            return
        gain = (len(group) - 2) ** 2
        self.score += gain
        self.popped = [(gx, gy, color) for gx, gy in group]
        for gx, gy, _c in self.popped:
            self.grid[gy][gx] = EMPTY
        self.pop_until = self.t + float(self.cfg.get("flash_seconds", 0.35))
        self.state = "popping"
        log(f"pop! {len(group)} tiles +{gain} — score {self.score}")

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        if self.state == "popping" and self.t >= self.pop_until:
            self.state = "falling"
            self.fall_acc = 0.0
        elif self.state == "falling":
            self.fall_acc += dt
            step = float(self.cfg.get("fall_step", 0.06))
            while self.fall_acc >= step and self.state == "falling":
                self.fall_acc -= step
                if not self._gravity_step():
                    self.state = "play"
                    self._settle()
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("pop.json reloaded")
            except OSError:
                pass

    def _tile_color(self, c: int, dim: float = 1.0):
        return tuple(int(v * dim) for v in COLORS[c - 1])

    def draw(self, screen):
        screen.clear((0, 0, 0))
        over = self.state == "over"
        dim = 0.45 if over else 1.0
        # the rain trail left by the last gravity micro-step
        for (x, y), c in self.ghosts.items():
            screen.set(x, y, self._tile_color(c, 0.22))
        # settled tiles (animated dim in over, rainbow everywhere on a perfect clear)
        for y in range(H):
            for x in range(W):
                if self.state == "cleared":              # celebrate the emptiness itself
                    hue = ((x + y) / 24.0 + self.t * 0.25) % 1.0
                    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
                    screen.set(x, y, (int(r * 255), int(g * 255), int(b * 255)))
                    continue
                c = self.grid[y][x]
                if c == EMPTY:
                    continue
                screen.set(x, y, self._tile_color(c, dim))
        # the burst: white flash fading back to colour as it vanishes
        if self.state == "popping":
            flash = max(0.0, (self.pop_until - self.t)
                       / max(1e-9, float(self.cfg.get("flash_seconds", 0.35))))
            for (px_, py_, c) in self.popped:
                base = COLORS[c - 1]
                col = tuple(int(b + (255 - b) * flash) for b in base)
                screen.set(px_, py_, col)
        # the "nope" blink on a lone tile
        if self.nope_cell and self.t < self.nope_until:
            nx, ny, c = self.nope_cell
            blink = 0.35 + 0.4 * (1 if int(self.t * 8) % 2 else 0)
            screen.set(nx, ny, self._tile_color(c, blink))
        if over:                                        # slow red border, the run is done
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            col = (int(200 * pulse), 30, 30)
            for x in range(W):
                screen.set(x, 0, col)
                screen.set(x, H - 1, col)
            for y in range(H):
                screen.set(0, y, col)
                screen.set(W - 1, y, col)


if __name__ == "__main__":
    run(Pop)