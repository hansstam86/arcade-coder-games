#!/usr/bin/env python3
"""Quantum Walk — a 576-amplitude wavefunction on your desk.

A discrete-time quantum walk: a genuine unitary simulation with complex
amplitudes psi(x, y, direction) evolving on the 12x12 torus. Each
generation applies a coin operator (Hadamard x Hadamard, or the Grover
diffusion coin) and shifts each direction — real superposition, real
interference, no shortcuts. Total probability stays exactly 1.

Rendering maps probability to brightness and quantum phase to hue, so
the interference structure appears as rainbow rings blooming outward
and wrapping around the torus into itself.

Pads (same layout as life / wireworld):
  top-left     play/pause (green when running, red when paused)
  top-right    cycle speed: 1 / 2 / 5 / 10 generations per second
  top-centre   cycle the coin operator: hadamard / grover / ballistic
  bottom-left  reset — fresh walker at the centre
  bottom-right add a walker in superposition at a random site
Every other pad is a MEASUREMENT at that cell: the wavefunction
collapses there and re-blooms from the pixel you pressed.

qwalk.json (auto-created, hot-reloads): speeds, reseed_steps,
brightness, saturation.

  python qwalk.py             # emulator at http://127.0.0.1:7777
  python qwalk.py --hw        # real board over BLE
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
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "qwalk.json"

DEFAULT = {
    "speeds": [1, 2, 5, 10],   # generations per second, cycled by pad
    "speed_index": 2,
    "reseed_steps": 160,        # fresh walker when the old one disperses
    "brightness": 80.0,         # probability -> value scaling
    "saturation": 0.90,
}

W = H = 12
DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))     # left, right, up, down
S2 = 1.0 / math.sqrt(2.0)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --- coins: 4x4 unitaries applied at every site --------------------------------
def coin_hadamard(v):
    """Hadamard on the horizontal pair and on the vertical pair (H x H)."""
    L, R, U, D = v
    return ((L + R) * S2, (L - R) * S2, (U + D) * S2, (U - D) * S2)


def coin_grover(v):
    """Grover diffusion: 2|s><s| - I with |s> the uniform direction state."""
    S = (v[0] + v[1] + v[2] + v[3]) / 2.0
    return (S - v[0], S - v[1], S - v[2], S - v[3])


def coin_identity(v):
    """No coin flip: a ballistic walker in a straight line (classical)."""
    return v


COINS = (
    ("hadamard", coin_hadamard, (1.0, 1.0j, 1.0j, 1.0)),
    ("grover", coin_grover, (1.0, 1.0, 1.0, 1.0)),
    ("ballistic", coin_identity, (0.0, 1.0, 0.0, 0.0)),
)


class QWalk(Game):
    fps = 20

    def start(self):
        self._load()
        self.psi = self._zeros()
        self.steps = 0
        self.acc = 0.0
        self.coin_i = 0
        self.running = True
        self.next_check = 0.0
        self._seed(W // 2, H // 2)
        log("quantum walk — pads: pause, speed, coin, reset, superpose; "
            "any other pad measures the wavefunction there")

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

    # -- quantum state ---------------------------------------------------------
    @staticmethod
    def _zeros():
        return [[[0j] * 4 for _ in range(W)] for _ in range(H)]

    def _seed(self, x: int, y: int) -> None:
        """Localised walker: coin state from the active coin's start vector."""
        self.psi = self._zeros()
        start = COINS[self.coin_i][2]
        n = math.sqrt(sum(abs(a) ** 2 for a in start))
        self.psi[y][x] = [a / n for a in start]
        self.steps = 0

    def total_probability(self) -> float:
        return sum(abs(a) ** 2 for row in self.psi for cell in row for a in cell)

    def _renormalise(self) -> None:
        n = math.sqrt(self.total_probability())
        if n > 0:
            self.psi = [[[a / n for a in cell] for cell in row] for row in self.psi]

    def measure(self, x: int, y: int) -> None:
        """Collapse: observation localises the walker at (x, y)."""
        self._seed(x, y)
        log(f"measurement at ({x},{y}) — wavefunction collapsed")

    def superpose(self) -> None:
        """Add a second walker in superposition at a random site."""
        fresh = self._zeros()
        start = COINS[self.coin_i][2]
        n = math.sqrt(sum(abs(a) ** 2 for a in start))
        x, y = random.randrange(W), random.randrange(H)
        fresh[y][x] = [a / n for a in start]
        s = 1.0 / math.sqrt(2.0)
        self.psi = [[[self.psi[y][x][d] * s + fresh[y][x][d] * s for d in range(4)]
                     for x in range(W)] for y in range(H)]
        self._renormalise()
        log(f"superposition: walker added at ({x},{y})")

    def _step(self) -> None:
        # coin
        coin = COINS[self.coin_i][1]
        coined = [[coin(self.psi[y][x]) for x in range(W)] for y in range(H)]
        # shift
        out = self._zeros()
        for y in range(H):
            for x in range(W):
                v = coined[y][x]
                for d, (dx, dy) in enumerate(DIRS):
                    out[(y + dy) % H][(x + dx) % W][d] += v[d]
        self.psi = out
        self.steps += 1

    # -- input ---------------------------------------------------------------
    PAUSE_PAD = (0, 0)
    SPEED_PAD = (11, 0)
    COIN_PAD = (6, 0)
    RESET_PAD = (0, 11)
    SUPER_PAD = (11, 11)

    def on_press(self, x, y):
        if (x, y) == self.PAUSE_PAD:
            self.running = not self.running
            log("paused" if not self.running else "running")
        elif (x, y) == self.SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 2)) + 1) % len(speeds)
            log(f"speed -> {self.gps:g} generations/s")
        elif (x, y) == self.COIN_PAD:
            self.coin_i = (self.coin_i + 1) % len(COINS)
            log(f"coin -> {COINS[self.coin_i][0]}")
        elif (x, y) == self.RESET_PAD:
            self._seed(W // 2, H // 2)
            log("reset — fresh walker at the centre")
        elif (x, y) == self.SUPER_PAD:
            self.superpose()
        else:
            self.measure(x, y)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.acc += dt
            interval = 1.0 / max(0.1, self.gps)
            while self.acc >= interval:
                self.acc -= interval
                self._step()
                if self.steps >= int(self.cfg.get("reseed_steps", 160)):
                    x, y = random.randrange(W), random.randrange(H)
                    self._seed(x, y)
                    log(f"dispersed — fresh walker at ({x},{y})")
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("qwalk.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        bright = float(self.cfg.get("brightness", 80.0))
        sat = float(self.cfg.get("saturation", 0.9))
        empty = (2, 4, 10) if not self.running else (0, 0, 0)
        for y in range(H):
            for x in range(W):
                cell = self.psi[y][x]
                p = sum(abs(a) ** 2 for a in cell)
                if p < 1e-4:
                    screen.set(x, y, empty)
                    continue
                phase = math.atan2(sum(a.imag for a in cell), sum(a.real for a in cell))
                hue = (phase / (2 * math.pi) + 1.0) % 1.0
                val = min(1.0, (p * bright) ** 0.6)
                r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                screen.set(x, y, (int(r * 255), int(g * 255), int(b * 255)))
        # HUD pads
        screen.set(*self.PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*self.SPEED_PAD, (30, 90, 230))
        screen.set(*self.COIN_PAD, (240, 140, 20))
        screen.set(*self.RESET_PAD, (60, 60, 60))
        screen.set(*self.SUPER_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(QWalk)