#!/usr/bin/env python3
"""2048 — the merge classic in two sizes, fully turn-based, hardware-proof.

grid: 10 (default) — the long form: a 10x10 grid of one-pixel tiles
fills the display, leaving one column of margin per edge as the
swipe. 100 cells, big enough that you will live to forge 4096s and
8192s — tiles beyond 2048 shimmer with slowly-cycling hues of their
own.

grid: 4 — the classic: a 4x4 grid of 2x2 pixel blocks centred on the
board with 2px swipe margins, tile values as a compact heat palette.

Either way the margins are the swipe: press the left edge to move
left, right edge right, top edge up, bottom edge down (margin corners:
the x edge wins). Presses inside the grid do nothing. After game
over, any swipe starts a fresh game.

Exact classic rules: tiles merge at most once per move, a 4 spawns
with 10% probability, a move that changes nothing does nothing (no
spawn), game over when no move is possible — including a full dead
board that ignores every swipe. Merges flash gold, the spawn white.

twenty48.json (auto-created, hot-reloads; changing grid restarts the
game): grid, four_probability, target.

  python twenty48.py            # emulator at http://127.0.0.1:7777
  python twenty48.py --hw       # real board over BLE
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

CONFIG_PATH = Path(__file__).resolve().parent / "twenty48.json"

DEFAULT = {
    "grid": 10,               # 10 = long-form (1px tiles, 100 cells);
                              #  4 = classic (2x2 tile blocks, 2px margins)
    "four_probability": 0.1,
    "target": 2048,
}

TILE_COLORS = (             # indexed by log2(value) - 1
    (30, 90, 100),          # 2
    (45, 150, 160),         # 4
    (60, 130, 230),         # 8
    (130, 90, 230),         # 16
    (200, 70, 220),         # 32
    (240, 60, 120),         # 64
    (245, 120, 30),         # 128
    (245, 190, 20),         # 256
    (250, 225, 70),         # 512
    (255, 245, 170),        # 1024
    (255, 255, 255),        # 2048
)

GOLD = (255, 200, 60)
WHITE = (255, 255, 255)
HINT = (25, 28, 40)
EMPTY_GUIDE = (7, 9, 16)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _slide(line):
    """Slide toward index 0. Returns (new_line, gained, merged_indices)."""
    tiles = [v for v in line if v]
    out, gained, merged = [], 0, []
    i = 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            gained += tiles[i] * 2
            merged.append(len(out) - 1)
            i += 2
        else:
            out.append(tiles[i])
            i += 1
    out += [0] * (len(line) - len(out))
    return out, gained, merged


class Twenty48(Game):
    fps = 20

    def start(self):
        self._load()
        self.rnd = random.Random()
        self.next_check = 0.0
        self.anim_t = 0.0
        self.flash_t = 0.0
        self.new_game()
        log(f"2048 — {self.N}x{self.N} grid, 1-pixel tiles. swipe on the "
            "edges: left/right margins = left/right, top/bottom = up/down; "
            "grid presses do nothing")

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
        self.N = max(4, min(W, int(self.cfg.get("grid", 10))))
        self.tile = 2 if self.N * 2 <= W - 2 else 1     # classic blocks vs 1px
        self.off = (W - self.N * self.tile) // 2

    # -- the game -----------------------------------------------------------------
    def new_game(self) -> None:
        n = self.N
        self.grid = [[0] * n for _ in range(n)]
        self.score = 0
        self.won = False
        self.state = "play"
        self.merged_cells: list[tuple[int, int]] = []
        self.spawn_cell = None
        self.flash_t = 0.0
        self._spawn()
        self._spawn()
        log("new game")

    def _empty_cells(self):
        return [(x, y) for y in range(self.N) for x in range(self.N)
                if self.grid[y][x] == 0]

    def _spawn(self) -> None:
        empty = self._empty_cells()
        if not empty:
            return
        x, y = self.rnd.choice(empty)
        four = self.rnd.random() < float(self.cfg.get("four_probability", 0.1))
        self.grid[y][x] = 4 if four else 2
        self.spawn_cell = (x, y)

    def _line(self, direction: str, i: int) -> list:
        n, g = self.N, self.grid
        if direction == "left":
            return g[i][:]
        if direction == "right":
            return g[i][::-1]
        if direction == "up":
            return [g[j][i] for j in range(n)]
        return [g[n - 1 - j][i] for j in range(n)]          # down

    def _coord(self, direction: str, i: int, k: int):
        n = self.N
        if direction == "left":
            return (k, i)
        if direction == "right":
            return (n - 1 - k, i)
        if direction == "up":
            return (i, k)
        return (i, n - 1 - k)                                # down

    def _move(self, direction: str) -> None:
        changed = False
        gained = 0
        self.merged_cells = []
        for i in range(self.N):
            line = self._line(direction, i)
            new, g, merged = _slide(line)
            if new != line:
                changed = True
            gained += g
            for k in merged:
                self.merged_cells.append(self._coord(direction, i, k))
            for k, v in enumerate(new):
                x, y = self._coord(direction, i, k)
                self.grid[y][x] = v
        if not changed:
            if not self._empty_cells() and not self._can_move():
                self.state = "over"               # a dead board must still die
                log(f"game over — score {self.score}")
            return
        self.score += gained
        self._spawn()
        self.flash_t = 0.5
        target = int(self.cfg.get("target", 2048))
        if not self.won and any(v >= target for row in self.grid for v in row):
            self.won = True
            log(f"{target}! keep going — score {self.score}")
        if gained:
            log(f"merge +{gained} — score {self.score}")
        if not self._empty_cells() and not self._can_move():
            self.state = "over"
            log(f"game over — score {self.score}")

    def _can_move(self) -> bool:
        for y in range(self.N):
            for x in range(self.N):
                v = self.grid[y][x]
                for dx, dy in ((1, 0), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if nx < self.N and ny < self.N and self.grid[ny][nx] == v:
                        return True
        return False

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        direction = None
        if x < self.off:
            direction = "left"
        elif x >= W - self.off:
            direction = "right"
        elif y < self.off:
            direction = "up"
        elif y >= H - self.off:
            direction = "down"
        if direction is None:
            return                              # presses inside the grid: nothing
        if self.state == "over":
            self.new_game()
            return
        self._move(direction)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        self.anim_t += dt
        self.flash_t = max(0.0, self.flash_t - dt)
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    prev_n = self.N
                    self._load()
                    log("twenty48.json reloaded")
                    if self.N != prev_n:
                        self.new_game()              # grid change needs a fresh board
                        log(f"grid -> {self.N}x{self.N} (tiles {self.tile}px)")
            except OSError:
                pass

    def _tile_color(self, v: int):
        e = v.bit_length() - 2
        if e < len(TILE_COLORS):
            return TILE_COLORS[e]
        # beyond 2048: each exponent shimmers with its own slowly-cycling hue
        hue = (0.5 + 0.13 * (e - len(TILE_COLORS)) + self.anim_t * 0.15) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    def draw(self, screen):
        screen.clear((0, 0, 0))
        over = self.state == "over"
        dim = 0.45 if over else 1.0
        off, tile = self.off, self.tile
        # swipe hints in the margins
        for j in (H // 2 - 1, H // 2):
            for i in range(off):
                screen.set(i, j, HINT)                    # left
                screen.set(W - 1 - i, j, HINT)             # right
        for j in (W // 2 - 1, W // 2):
            for i in range(off):
                screen.set(j, i, HINT)                    # up
                screen.set(j, H - 1 - i, HINT)             # down
        # the grid
        for gy in range(self.N):
            for gx in range(self.N):
                v = self.grid[gy][gx]
                bx, by = off + gx * tile, off + gy * tile
                if v == 0:
                    screen.set(bx, by, EMPTY_GUIDE)
                    continue
                col = self._tile_color(v)
                if over:
                    col = tuple(int(c * dim) for c in col)
                for dy in range(tile):
                    for dx in range(tile):
                        screen.set(bx + dx, by + dy, col)
        # flash feedback: merges gold, the spawn white
        if self.flash_t > 0:
            blink = 0.5 + 0.5 * math.sin(self.flash_t * 30)
            for (x, y) in self.merged_cells:
                base = self._tile_color(self.grid[y][x])
                col = tuple(int(c + (GOLD[c] - c) * blink) for c in range(3))
                for dy in range(tile):
                    for dx in range(tile):
                        screen.set(off + x * tile + dx, off + y * tile + dy, col)
            if self.spawn_cell is not None:
                x, y = self.spawn_cell
                col = tuple(int(c + (WHITE[c] - c) * blink) for c in range(3))
                for dy in range(tile):
                    for dx in range(tile):
                        screen.set(off + x * tile + dx, off + y * tile + dy, col)
        if over:                                                # slow red border
            pulse = 0.5 + 0.5 * math.sin(self.anim_t * 4)
            c = (int(200 * pulse), 30, 30)
            for x in range(W):
                screen.set(x, 0, c)
                screen.set(x, H - 1, c)
            for y in range(H):
                screen.set(0, y, c)
                screen.set(W - 1, y, c)


if __name__ == "__main__":
    run(Twenty48)