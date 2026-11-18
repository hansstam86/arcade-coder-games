#!/usr/bin/env python3
"""Quantum Garden — plant wavefunctions, watch them bloom and decohere.

Every plant is a genuine discrete-time quantum walk: its own complex
amplitudes psi(x, y, direction), its own coin operator (hadamard or
grover), its own hue. Press a pad to sow a seed there and it blooms
outward with phase-hue interference rings; where two flowers overlap
their probability densities add and the bloom washes toward white.

Plants are open quantum systems: past their prime each one undergoes a
continuous weak position measurement toward the spot it was planted —
decoherence pulls the cloud back home, it concentrates into a bright
seed-dot, and the plant dies. An empty garden never stays empty: the
wind carries a new seed in after a few seconds.

Pads (same five-corner layout as life / wireworld / qwalk):
  top-left     play/pause (green running, red paused)
  top-right    cycle speed: 1 / 2 / 5 / 10 generations per second
  top-centre   gust — scatter three seeds at random spots
  bottom-left  clear the garden
  bottom-right sow ENTANGLED TWINS: one wavefunction in two-site
               superposition, blooming as correlated flowers
Every other pad plants a seed at that cell.

Plants die by quantum Zeno: past 70% of its life a flower is measured
so hard it stops moving, and the tightening measurement pins it into a
bright seed-dot before it goes out.

qgarden.json (auto-created, hot-reloads): speeds, brightness,
saturation, prime_steps, lifetime range, max_plants, wind_seconds.

  python qgarden.py           # emulator at http://127.0.0.1:7777
  python qgarden.py --hw      # real board over BLE
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
from qwalk import COINS, DIRS

CONFIG_PATH = Path(__file__).resolve().parent / "qgarden.json"

DEFAULT = {
    "speeds": [1, 2, 5, 10],   # generations per second, cycled by pad
    "speed_index": 2,
    "brightness": 90.0,
    "saturation": 0.90,
    "prime_steps": 26,          # pure unitary bloom before decoherence
    "lifetime_min": 90,         # steps from seed to death
    "lifetime_max": 150,
    "max_plants": 8,
    "wind_seconds": 3.0,        # an empty garden re-seeds after this
}

W = H = 12
R_HOME = 3.5                     # wither measurement keeps this radius around home
GAMMA = 0.80                     # damping per step outside it


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _zeros():
    return [[[0j] * 4 for _ in range(W)] for _ in range(H)]


def _torus_delta(a: int, b: int, n: int) -> int:
    d = abs(a - b)
    return min(d, n - d)


class Plant:
    """One flower: its own unitary walker plus an open-system lifecycle."""

    def __init__(self, x: int, y: int, cfg: dict, rnd: random.Random, twin=None):
        self.cfg = cfg
        self.coin_i = rnd.choice((0, 1))                 # hadamard or grover
        self.hue = rnd.random()
        self.age = 0
        self.prime = int(cfg.get("prime_steps", 26))
        self.lifetime = rnd.randint(int(cfg.get("lifetime_min", 90)),
                                    int(cfg.get("lifetime_max", 150)))
        start = COINS[self.coin_i][2]
        n = math.sqrt(sum(abs(a) ** 2 for a in start))
        self.psi = _zeros()
        if twin is None:
            self.psi[y][x] = [a / n for a in start]
            self.origin = (x, y)
            self.twin = None
        else:
            x2, y2 = twin
            for d in range(4):
                self.psi[y][x][d] = start[d] / n / math.sqrt(2.0)
                self.psi[y2][x2][d] = 1j * start[d] / n / math.sqrt(2.0)
            self.origin = ((x + x2) // 2 % W, (y + y2) // 2 % H)
            self.twin = (x2, y2)

    def _renormalise(self) -> None:
        n = math.sqrt(sum(abs(a) ** 2 for row in self.psi for c in row for a in c))
        if n > 0:
            self.psi = [[[a / n for a in c] for c in row] for row in self.psi]

    def total_probability(self) -> float:
        return sum(abs(a) ** 2 for row in self.psi for c in row for a in c)

    def home_mass(self, r: float = 1.5) -> float:
        """Probability mass within r of home — how far gone to seed it is."""
        ox, oy = self.origin
        inside = 0.0
        for y in range(H):
            for x in range(W):
                dx = _torus_delta(x, ox, W)
                dy = _torus_delta(y, oy, H)
                if dx * dx + dy * dy <= r * r:
                    inside += sum(abs(a) ** 2 for a in self.psi[y][x])
        return inside

    def step(self) -> bool:
        """One generation. Returns False when the plant is dead."""
        span = max(1, self.lifetime - self.prime)
        progress = min(1.0, (self.age - self.prime) / span) if self.age > self.prime else 0.0
        if progress <= 0.7:                             # Zeno: a heavily measured
            coin = COINS[self.coin_i][1]                # flower stops moving
            coined = [[coin(self.psi[y][x]) for x in range(W)] for y in range(H)]
            out = _zeros()
            for y in range(H):
                for x in range(W):
                    v = coined[y][x]
                    for d, (dx, dy) in enumerate(DIRS):
                        out[(y + dy) % H][(x + dx) % W][d] += v[d]
            self.psi = out
        self.age += 1
        if self.age > self.prime:                      # decoherence begins
            r = max(0.5, R_HOME * (1.0 - progress))     # the measurement tightens
            ox, oy = self.origin
            for y in range(H):
                for x in range(W):
                    dx = _torus_delta(x, ox, W)
                    dy = _torus_delta(y, oy, H)
                    if dx * dx + dy * dy > r * r:
                        self.psi[y][x] = [a * GAMMA for a in self.psi[y][x]]
            self._renormalise()
        return self.age < self.lifetime


class QGarden(Game):
    fps = 20

    PAUSE_PAD = (0, 0)
    SPEED_PAD = (11, 0)
    GUST_PAD = (6, 0)
    CLEAR_PAD = (0, 11)
    TWINS_PAD = (11, 11)

    def start(self):
        self._load()
        self.rnd = random.Random()
        self.plants: list[Plant] = []
        self.acc = 0.0
        self.running = True
        self.next_check = 0.0
        self.last_wind = time.monotonic()
        a = self._plant(2, 2)
        b = self._plant(9, 8)
        if a:
            log(f"seed at (2,2) — {COINS[a.coin_i][0]}, lifetime {a.lifetime}")
        if b:
            log(f"seed at (9,8) — {COINS[b.coin_i][0]}, lifetime {b.lifetime}")
        log("quantum garden — pads: pause, speed, gust, clear, entangled "
            "twins; any other pad plants a seed")

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

    # -- garden ----------------------------------------------------------------
    def _plant(self, x: int, y: int, twin=None) -> Plant | None:
        if len(self.plants) >= int(self.cfg.get("max_plants", 8)):
            return None
        p = Plant(x, y, self.cfg, self.rnd, twin=twin)
        self.plants.append(p)
        self.last_wind = time.monotonic()
        return p

    def plant(self, x: int, y: int, twin=None) -> None:
        p = self._plant(x, y, twin=twin)
        if p is None:
            log(f"({x},{y}) — the garden is full")
            return
        if p.twin is None:
            log(f"seed at ({x},{y}) — {COINS[p.coin_i][0]}, lifetime {p.lifetime}")
        else:
            log(f"entangled twins at ({x},{y}) and {p.twin} — "
                f"{COINS[p.coin_i][0]}, lifetime {p.lifetime}")

    def gust(self) -> None:
        for _ in range(3):
            self._plant(self.rnd.randrange(W), self.rnd.randrange(H))
        log("gust — three seeds scattered")

    def _wind(self) -> None:
        if (not self.plants
                and time.monotonic() - self.last_wind > float(self.cfg.get("wind_seconds", 3.0))):
            x, y = self.rnd.randrange(W), self.rnd.randrange(H)
            self.plant(x, y)

    def _step(self) -> None:
        self.plants = [p for p in self.plants if p.step()]

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == self.PAUSE_PAD:
            self.running = not self.running
            log("paused" if not self.running else "running")
        elif (x, y) == self.SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 2)) + 1) % len(speeds)
            log(f"speed -> {self.gps:g} generations/s")
        elif (x, y) == self.GUST_PAD:
            self.gust()
        elif (x, y) == self.CLEAR_PAD:
            self.plants = []
            self.last_wind = time.monotonic()
            log("garden cleared")
        elif (x, y) == self.TWINS_PAD:
            x2, y2 = (x + 5) % W, (y + 5) % H
            self.plant(x, y, twin=(x2, y2))
        else:
            self.plant(x, y)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.acc += dt
            interval = 1.0 / max(0.1, self.gps)
            while self.acc >= interval:
                self.acc -= interval
                self._step()
            self._wind()
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("qgarden.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        bright = float(self.cfg.get("brightness", 90.0))
        sat = float(self.cfg.get("saturation", 0.9))
        empty = (2, 4, 10) if not self.running else (0, 0, 0)
        screen.clear(empty)
        add = [[None] * W for _ in range(H)]
        for plant in self.plants:
            for y in range(H):
                for x in range(W):
                    cell = plant.psi[y][x]
                    p = sum(abs(a) ** 2 for a in cell)
                    if p < 1e-4:
                        continue
                    phase = math.atan2(sum(a.imag for a in cell), sum(a.real for a in cell))
                    hue = (phase / (2 * math.pi) + plant.hue) % 1.0
                    val = min(1.0, (p * bright) ** 0.6)
                    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                    rgb = (int(r * 255), int(g * 255), int(b * 255))
                    if add[y][x] is None:
                        add[y][x] = rgb
                    else:                                   # densities overlap -> wash to white
                        add[y][x] = tuple(min(255, a + b) for a, b in zip(add[y][x], rgb))
        for y in range(H):
            for x in range(W):
                if add[y][x] is not None:
                    screen.set(x, y, add[y][x])
        # HUD pads
        screen.set(*self.PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*self.SPEED_PAD, (30, 90, 230))
        screen.set(*self.GUST_PAD, (240, 140, 20))
        screen.set(*self.CLEAR_PAD, (60, 60, 60))
        screen.set(*self.TWINS_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(QGarden)