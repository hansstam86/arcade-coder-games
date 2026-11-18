#!/usr/bin/env python3
"""Reaction–Diffusion — the algorithm that paints leopard spots.

The Gray–Scott model: two chemicals on the 12x12 torus — substrate U
fed everywhere at rate F, activator V multiplying where U and V meet
(u*v*v) and dying off at rate k. Out of that tug-of-war emerge the
patterns of animal coats and coral: self-organising spots that divide
like cells, crawling worms, branching coral — grown, not drawn.

The buttons are the parameter instrument: every pad maps to a point in
the (F, k) plane — x = feed F (0.015 -> 0.075), y = kill k (0.050 ->
0.068). Press around the map and watch the current colony reorganise
into something else. Some corners of the map kill everything; the
colony replants itself a few seconds later.

Pads (same five-corner layout):
  top-left     play/pause (green running, red paused)
  top-right    cycle speed: 20 / 60 / 120 sim steps per second
  top-centre   preset anchor: leopard -> coral -> mitosis -> worms
  bottom-left  replant — fresh random seed blobs
  bottom-right toggle the (F, k) cursor overlay
Any other pad sets (F, k) from its position.

V renders through an organic palette: near-black substrate, teal
membranes, gold nuclei — glowing cells under a microscope.

reaction.json (auto-created, hot-reloads): speeds, F/k ranges,
replant_seconds.

  python reaction.py           # emulator at http://127.0.0.1:7777
  python reaction.py --hw      # real board over BLE
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "reaction.json"

DEFAULT = {
    "speeds": [20, 60, 120],  # sim steps per second
    "speed_index": 1,
    "F_range": [0.015, 0.075],
    "k_range": [0.050, 0.068],
    "replant_seconds": 3.0,
}

DU, DV = 0.08, 0.04            # diffusion rescaled for the 12x12 domain: the
                               # canonical (F, k) map has a ~15-cell pattern
                               # wavelength; lambda = 3*sqrt(Du/F) ~ 4.9 cells
                               # here, so the board fits real spots and worms
                               # (verified by parameter sweep over this grid)
PRESETS = (
    ("leopard", 0.0200, 0.0550),
    ("coral", 0.0545, 0.0620),
    ("mitosis", 0.0360, 0.0649),
    ("worms", 0.0700, 0.0550),
)

# V concentration -> colour: dark substrate, teal membrane, gold nucleus
PALETTE = (
    (0.00, (2, 4, 10)),
    (0.25, (8, 60, 80)),
    (0.50, (0, 190, 160)),
    (0.75, (255, 200, 110)),
    (1.00, (255, 250, 230)),
)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def color_for(v: float):
    v = max(0.0, min(1.0, v))
    for (a, ca), (b, cb) in zip(PALETTE, PALETTE[1:]):
        if v <= b:
            t = (v - a) / max(1e-9, b - a)
            return tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return PALETTE[-1][1]


class Reaction(Game):
    fps = 20

    PAUSE_PAD = (0, 0)
    SPEED_PAD = (11, 0)
    PRESET_PAD = (6, 0)
    REPLANT_PAD = (0, 11)
    CURSOR_PAD = (11, 11)

    def start(self):
        self._load()
        self.rnd = random.Random()
        self.u = [[1.0] * W for _ in range(H)]
        self.v = [[0.0] * W for _ in range(H)]
        self.acc = 0.0
        self.running = True
        self.next_check = 0.0
        self.dead_t = 0.0
        self.preset_i = 0
        self.cursor = False
        self.param_pos = None                     # last pressed (F, k) pad
        name, F, k = PRESETS[0]
        self.F, self.k = F, k
        self.replant()
        log(f"reaction–diffusion — F={F:.4f} k={k:.4f} ({name}). pads set "
            "(F, k); preset / replant / speed on the corners")

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
    def sps(self) -> float:
        speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
        i = min(int(self.cfg.get("speed_index", 1)), len(speeds) - 1)
        return float(speeds[i])

    # -- the chemistry ---------------------------------------------------------
    def set_params(self, x: int, y: int) -> None:
        fx0, fx1 = self.cfg.get("F_range", DEFAULT["F_range"])
        ky0, ky1 = self.cfg.get("k_range", DEFAULT["k_range"])
        self.F = fx0 + (fx1 - fx0) * x / (W - 1)
        self.k = ky0 + (ky1 - ky0) * y / (H - 1)
        self.param_pos = (x, y)
        log(f"F={self.F:.4f} k={self.k:.4f}")

    def replant(self) -> None:
        """Fresh colony: U everywhere, V in random blobs."""
        self.u = [[1.0] * W for _ in range(H)]
        self.v = [[0.0] * W for _ in range(H)]
        for _ in range(6):
            cx, cy = self.rnd.randrange(W), self.rnd.randrange(H)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    self.v[(cy + dy) % H][(cx + dx) % W] = 1.0
        self.dead_t = 0.0
        log("replanted — six fresh blobs")

    @staticmethod
    def _lap(f, x: int, y: int) -> float:
        s = -f[y][x]
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    w = 0.2 if (dx == 0 or dy == 0) else 0.05
                    s += w * f[(y + dy) % H][(x + dx) % W]
        return s

    def _step(self) -> None:
        F, k = self.F, self.k
        u, v = self.u, self.v
        new_u = [[0.0] * W for _ in range(H)]
        new_v = [[0.0] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                uu, vv = u[y][x], v[y][x]
                uvv = uu * vv * vv
                nu = uu + (DU * self._lap(u, x, y) - uvv + F * (1.0 - uu))
                nv = vv + (DV * self._lap(v, x, y) + uvv - (F + k) * vv)
                new_u[y][x] = 0.0 if nu < 0.0 else (1.0 if nu > 1.0 else nu)
                new_v[y][x] = 0.0 if nv < 0.0 else (1.0 if nv > 1.0 else nv)
        self.u, self.v = new_u, new_v

    def alive_cells(self) -> int:
        return sum(1 for y in range(H) for x in range(W) if self.v[y][x] > 0.25)

    def max_v(self) -> float:
        return max(max(row) for row in self.v)

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == self.PAUSE_PAD:
            self.running = not self.running
            log("paused" if not self.running else "running")
        elif (x, y) == self.SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 1)) + 1) % len(speeds)
            log(f"speed -> {self.sps:g} steps/s")
        elif (x, y) == self.PRESET_PAD:
            self.preset_i = (self.preset_i + 1) % len(PRESETS)
            name, F, k = PRESETS[self.preset_i]
            self.F, self.k = F, k
            self.param_pos = None
            log(f"preset -> {name} (F={F:.4f} k={k:.4f})")
        elif (x, y) == self.REPLANT_PAD:
            self.replant()
        elif (x, y) == self.CURSOR_PAD:
            self.cursor = not self.cursor
            log(f"(F, k) cursor {'on' if self.cursor else 'off'}")
        else:
            self.set_params(x, y)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.acc += dt
            interval = 1.0 / max(1.0, self.sps)
            while self.acc >= interval:
                self.acc -= interval
                self._step()
            if self.max_v() < 0.02:                      # colony died at these params
                self.dead_t += dt
                if self.dead_t >= float(self.cfg.get("replant_seconds", 3.0)):
                    log("colony died — hostile (F, k); replanting")
                    self.replant()
            else:
                self.dead_t = 0.0
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("reaction.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        for y in range(H):
            for x in range(W):
                screen.set(x, y, color_for(self.v[y][x]))
        if self.cursor:                                  # (F, k) map overlay
            for x in range(W):                           # faint axes through the
                screen.set(x, 0, (40, 40, 60))            # current parameter point
            for y in range(H):
                screen.set(0, y, (40, 40, 60))
            if self.param_pos:
                px, py = self.param_pos
                screen.set(px, py, (255, 255, 255))
        # HUD pads
        screen.set(*self.PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*self.SPEED_PAD, (30, 90, 230))
        screen.set(*self.PRESET_PAD, (240, 140, 20))
        screen.set(*self.REPLANT_PAD, (60, 60, 60))
        screen.set(*self.CURSOR_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(Reaction)