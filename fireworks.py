#!/usr/bin/env python3
"""Fireworks — a particle firework show for the Arcade Coder.

Rockets streak up from the bottom and burst into showers of coloured sparks
that arc, fall and fade, leaving glowing trails. It runs on its own as a
continuous show; tap anywhere to launch an extra rocket from that spot.

  python fireworks.py         # emulator
"""

from __future__ import annotations

import colorsys
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12
GRAV = 14.0          # spark gravity (px/s^2)
MAX_SPARKS = 130


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, max(0.0, min(1.0, v)))
    return (r * 255, g * 255, b * 255)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Fireworks(Game):
    fps = 24

    def start(self):
        self.fade = [[0.0, 0.0, 0.0] for _ in range(144)]
        self.rockets = []       # [x, y, vy, color, target_y]
        self.sparks = []        # [x, y, vx, vy, color, life, maxlife]
        self.stars = [(random.randrange(W), random.randrange(5)) for _ in range(6)]
        self.next_launch = 0.0
        self.busy = True        # keep the show going
        self.last = time.monotonic()
        log("fireworks — enjoy the show (tap to launch)")

    def _launch(self, x=None, big=False):
        x = random.uniform(2, W - 2) if x is None else max(1, min(W - 2, x))
        hue = random.random()
        self.rockets.append([x, float(H - 1), -random.uniform(9, 12),
                             hue, random.uniform(1.5, 5.0)])
        if big:
            self.rockets[-1][2] = -13          # a bit higher/faster on a tap

    def _burst(self, x, y, hue):
        n = random.choice((14, 18, 22))
        style = random.choice(("burst", "ring", "willow"))
        base = random.uniform(3, 6) if style != "willow" else random.uniform(2, 3.5)
        for i in range(n):
            a = (i / n) * 6.2832 if style == "ring" else random.uniform(0, 6.2832)
            sp = base if style == "ring" else base * random.uniform(0.5, 1.0)
            vy = math.sin(a) * sp + (1.5 if style == "willow" else 0)
            h = (hue + random.uniform(-0.06, 0.06)) % 1.0
            life = random.uniform(0.7, 1.3) * (1.5 if style == "willow" else 1.0)
            self.sparks.append([x, y, math.cos(a) * sp, vy, h, life, life])
        # bright flash at the centre
        self.sparks.append([x, y, 0.0, 0.0, hue, 0.12, 0.12])

    def on_press(self, x, y):
        self._launch(x, big=True)

    def update(self, dt):
        now = time.monotonic()
        dt = min(0.08, now - self.last)
        self.last = now
        if now >= self.next_launch:
            self._launch()
            self.next_launch = now + random.uniform(1.1, 2.4)
        for r in self.rockets[:]:
            r[1] += r[2] * dt
            r[2] += 6 * dt                     # gravity slows the ascent
            if r[1] <= r[4] or r[2] >= -1.5:   # reached apex -> explode
                self._burst(r[0], r[1], r[3])
                self.rockets.remove(r)
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += GRAV * dt
            s[5] -= dt
        self.sparks = [s for s in self.sparks if s[5] > 0 and s[1] < H + 1]
        if len(self.sparks) > MAX_SPARKS:
            self.sparks = self.sparks[-MAX_SPARKS:]

    # -- render --------------------------------------------------------------
    def _add(self, x, y, col, k=1.0):
        xi, yi = int(x), int(y)
        if 0 <= xi < W and 0 <= yi < H:
            f = self.fade[yi * W + xi]
            f[0] += col[0] * k; f[1] += col[1] * k; f[2] += col[2] * k

    def draw(self, screen):
        for f in self.fade:                    # decay for glowing trails
            f[0] *= 0.74; f[1] *= 0.74; f[2] *= 0.74
        for r in self.rockets:                 # rising rocket + tail
            self._add(r[0], r[1], (255, 240, 200), 1.0)
            self._add(r[0], r[1] + 1, (180, 120, 40), 0.5)
        for s in self.sparks:                  # sparks, brighter when young
            frac = s[5] / s[6]
            col = hsv(s[4], 0.9 - 0.3 * (1 - frac), 1.0)
            self._add(s[0], s[1], col, 0.6 + 0.4 * frac)
        for sx, sy in self.stars:              # faint background stars
            self._add(sx, sy, (40, 40, 70), 1.0)
        for i in range(144):
            f = self.fade[i]
            screen.set(i % W, i // W, (min(255, int(f[0])) or 2,
                                      min(255, int(f[1])) or 2,
                                      min(255, int(f[2])) or 10))


if __name__ == "__main__":
    run(Fireworks)
