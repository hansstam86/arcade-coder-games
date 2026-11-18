#!/usr/bin/env python3
"""Wireworld — a Turing-complete circuit sandbox on 144 LEDs.

Wireworld cellular automaton: copper wire (amber) carries electrons —
a bright cyan head with a red tail — one cell per generation. Copper
fires when exactly 1 or 2 of its neighbours are heads, so pulses travel
along wires, round corners and through junctions you draw.

Pads (same layout as the game of life):
  top-left     play/pause (green when running, red when paused)
  top-right    cycle speed: 1 / 2 / 5 / 10 generations per second
  top-centre   load the next preset circuit (clock ring, twin rings, ...)
  bottom-left  clear the board
  bottom-right cycle the brush: copper / electron head / erase
Every other pad paints with the current brush — draw wires, inject
electrons into a running circuit, erase mistakes, all live.

wireworld.json (auto-created, hot-reloads): speeds, wrap (torus edges).

  python wireworld.py            # emulator at http://127.0.0.1:7777
  python wireworld.py --hw       # real board over BLE
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "wireworld.json"

DEFAULT = {
    "speeds": [1, 2, 5, 10],   # generations per second, cycled by pad
    "speed_index": 2,
    "wrap": True,               # torus edges (false = the void)
}

W = H = 12

EMPTY, COPPER, HEAD, TAIL = 0, 1, 2, 3
COLORS = {
    COPPER: (170, 100, 18),
    HEAD: (0, 230, 255),
    TAIL: (235, 50, 10),
}
BRUSHES = (COPPER, HEAD, EMPTY)      # cycled by the brush pad
BRUSH_COLOR = {COPPER: (170, 100, 18), HEAD: (0, 230, 255), EMPTY: (60, 60, 60)}

PAUSE_PAD = (0, 0)
SPEED_PAD = (11, 0)
PATTERN_PAD = (6, 0)
CLEAR_PAD = (0, 11)
BRUSH_PAD = (11, 11)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _ring(x0: int, y0: int, x1: int, y1: int) -> dict:
    """A closed wire loop (ordered box perimeter) with one pulse on it.

    The pulse is seeded mid-edge: cells[0] is a corner, and a head+tail
    pair seeded there re-ignites (the fresh copper tail sits diagonal to
    the head's next position and fires a backward pulse). cells[1..2] sit
    on the straight top edge where head/tail propagate cleanly.
    """
    cells = ([(x, y0) for x in range(x0, x1)]
             + [(x1, y) for y in range(y0, y1)]
             + [(x, y1) for x in range(x1, x0, -1)]
             + [(x0, y) for y in range(y1, y0, -1)])
    world = {c: COPPER for c in cells}
    world[cells[2]] = HEAD
    world[cells[1]] = TAIL
    return world


def _line(y: int, pulse_x: int) -> dict:
    """A full-width wire (a closed loop when wrap is on) with one pulse."""
    world = {(x, y): COPPER for x in range(W)}
    world[(pulse_x, y)] = HEAD
    world[((pulse_x - 1) % W, y)] = TAIL
    return world


def _zigzag() -> dict:
    """A snake wire carrying a single pulse from end to end."""
    path = ([(x, 1) for x in range(1, 11)]
            + [(10, y) for y in range(2, 6)]
            + [(x, 5) for x in range(9, 0, -1)]
            + [(1, y) for y in range(6, 10)]
            + [(x, 9) for x in range(2, 11)])
    world = {c: COPPER for c in path}
    world[path[0]] = TAIL
    world[path[1]] = HEAD
    return world


PRESETS = (
    ("clock ring", _ring(2, 2, 9, 9)),
    ("twin rings", {**_ring(1, 1, 10, 10), **_ring(4, 4, 7, 7)}),
    ("data bus", {**_line(2, 1), **_line(5, 4), **_line(8, 7), **_line(10, 10)}),
    ("zigzag", _zigzag()),
)


class Wireworld(Game):
    fps = 20

    def start(self):
        self._load()
        self.grid = [[EMPTY] * W for _ in range(H)]
        self.acc = 0.0
        self.running = True
        self.brush = COPPER
        self.pattern_idx = 0
        self.next_check = 0.0
        self.load_pattern(0)
        log("wireworld — top-left pause, top-right speed, top-centre "
            "preset circuit, bottom-left clear, bottom-right brush "
            "(copper/electron/erase); other pads paint live")

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
    def load_pattern(self, idx: int) -> None:
        name, world = PRESETS[idx % len(PRESETS)]
        self.grid = [[EMPTY] * W for _ in range(H)]
        for (x, y), state in world.items():
            self.grid[y][x] = state
        log(f"circuit -> {name}")

    def clear(self) -> None:
        self.grid = [[EMPTY] * W for _ in range(H)]
        log("board cleared")

    def _neighbour_heads(self, x: int, y: int) -> int:
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
                n += 1 if self.grid[ny][nx] == HEAD else 0
        return n

    def _step(self) -> None:
        g = self.grid
        new = [[EMPTY] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                s = g[y][x]
                if s == HEAD:
                    new[y][x] = TAIL
                elif s == TAIL:
                    new[y][x] = COPPER
                elif s == COPPER:
                    new[y][x] = HEAD if self._neighbour_heads(x, y) in (1, 2) else COPPER
        self.grid = new

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
            self.pattern_idx = (self.pattern_idx + 1) % len(PRESETS)
            self.load_pattern(self.pattern_idx)
        elif (x, y) == CLEAR_PAD:
            self.clear()
        elif (x, y) == BRUSH_PAD:
            self.brush = BRUSHES[(BRUSHES.index(self.brush) + 1) % len(BRUSHES)]
            names = {COPPER: "copper", HEAD: "electron", EMPTY: "erase"}
            log(f"brush -> {names[self.brush]}")
        else:
            self.grid[y][x] = self.brush

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.acc += dt
            interval = 1.0 / max(0.1, self.gps)
            while self.acc >= interval:
                self.acc -= interval
                self._step()
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("wireworld.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        screen.clear((0, 0, 0) if self.running else (3, 6, 14))
        for y in range(H):
            for x in range(W):
                s = self.grid[y][x]
                if s:
                    screen.set(x, y, COLORS[s])
        # HUD pads
        screen.set(*PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*SPEED_PAD, (30, 90, 230))
        screen.set(*PATTERN_PAD, (240, 140, 20))
        screen.set(*CLEAR_PAD, (60, 60, 60))
        screen.set(*BRUSH_PAD, BRUSH_COLOR[self.brush])


if __name__ == "__main__":
    run(Wireworld)