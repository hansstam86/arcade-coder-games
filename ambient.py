#!/usr/bin/env python3
"""Ambient mode — the Arcade Coder as a living desk object.

Seven scenes: clock (day-sky background), fire, plasma, matrix rain,
game of life, starfield, dvd bounce. Press any pad to skip to the next
scene; scenes auto-rotate; everything dims at night.

Config in ambient.json (auto-created):
  rotate_minutes, brightness (0-100), clock_24h,
  night_dim: {start, end, brightness}, scene (persisted last scene)

  python ambient.py           # emulator
  python ambient_hw.py        # real board via the app bundle
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

CONFIG_PATH = Path(__file__).resolve().parent / "ambient.json"
W = H = 12

DEFAULT = {
    "rotate_minutes": 10,
    "brightness": 100,
    "clock_24h": True,
    "night_dim": {"start": 22, "end": 8, "brightness": 25},
    "scene": "clock",
}

FONT = {  # 3x5 digits
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


class Scene:
    name = "scene"

    def __init__(self) -> None: ...
    def draw(self, buf: list, now: float) -> None: ...


class Clock(Scene):
    name = "clock"

    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def draw(self, buf, now):
        t = time.localtime()
        # sky background: hue follows the day (deep blue night -> warm day)
        day = (t.tm_hour + t.tm_min / 60) / 24
        sun = max(0.0, math.sin((day - 0.25) * 2 * math.pi))  # 0 at 6am/6pm-ish
        sky = hsv(0.62 - 0.12 * sun, 0.9 - 0.35 * sun, 0.06 + 0.10 * sun)
        for i in range(144):
            buf[i] = sky
        hour = t.tm_hour if self.cfg["clock_24h"] else (t.tm_hour % 12 or 12)
        digits = f"{hour:02d}{t.tm_min:02d}"
        positions = [(2, 0), (7, 0), (2, 7), (7, 7)]  # HH top, MM bottom
        for ch, (ox, oy) in zip(digits, positions):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        buf[(oy + dy) * W + ox + dx] = (235, 235, 235)
        if t.tm_sec % 2 == 0:  # blinking second dots
            buf[6 * W + 5] = buf[6 * W + 6] = (240, 90, 0)


class Fire(Scene):
    name = "fire"

    def __init__(self, *_):
        self.heat = [[0.0] * W for _ in range(H + 2)]

    def draw(self, buf, now):
        h = self.heat
        for x in range(W):  # stoke the bottom
            h[H + 1][x] = random.uniform(0.55, 1.0)
        for y in range(H + 1):
            for x in range(W):
                below = h[y + 1]
                v = (below[x] * 2 + below[(x - 1) % W] + below[(x + 1) % W]) / 4
                h[y][x] = max(0.0, v - random.uniform(0.02, 0.11))
        for y in range(H):
            for x in range(W):
                v = h[y][x]
                buf[y * W + x] = (
                    int(255 * min(1, v * 1.6)),
                    int(255 * max(0, v * 1.4 - 0.45)),
                    int(255 * max(0, v * 2.2 - 1.6)),
                )


class Plasma(Scene):
    name = "plasma"

    def __init__(self, *_): ...

    def draw(self, buf, now):
        t = now * 0.35
        for y in range(H):
            for x in range(W):
                v = (math.sin(x * 0.55 + t) + math.sin(y * 0.48 - t * 1.2)
                     + math.sin((x + y) * 0.35 + t * 0.7)
                     + math.sin(math.hypot(x - 5.5, y - 5.5) * 0.9 - t)) / 4
                buf[y * W + x] = hsv(0.55 + v * 0.35, 0.85, 0.28 + 0.30 * abs(v))


class Rain(Scene):
    name = "rain"

    def __init__(self, *_):
        self.drops = [[random.uniform(0, W), random.uniform(-H, 0),
                       random.uniform(5, 11)] for _ in range(9)]
        self.fade = [[0.0] * W for _ in range(H)]
        self.last = time.monotonic()

    def draw(self, buf, now):
        dt = min(0.3, now - self.last)
        self.last = now
        for row in self.fade:
            for x in range(W):
                row[x] *= 0.88
        for d in self.drops:
            d[1] += d[2] * dt
            if d[1] > H + 3:
                d[0], d[1], d[2] = random.uniform(0, W), random.uniform(-6, -1), random.uniform(5, 11)
            yy = int(d[1])
            if 0 <= yy < H:
                self.fade[yy][int(d[0]) % W] = 1.0
        for y in range(H):
            for x in range(W):
                v = self.fade[y][x]
                buf[y * W + x] = (0, int(230 * v), int(60 * v * v))


class Life(Scene):
    name = "life"

    def __init__(self, *_):
        self.reseed()
        self.next_gen = 0.0
        self.history: list[int] = []

    def reseed(self):
        self.grid = [[random.random() < 0.32 for _ in range(W)] for _ in range(H)]
        self.hue = random.random()

    def draw(self, buf, now):
        if now >= self.next_gen:
            self.next_gen = now + 0.45
            g = self.grid
            nxt = [[False] * W for _ in range(H)]
            for y in range(H):
                for x in range(W):
                    n = sum(g[(y + dy) % H][(x + dx) % W]
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if (dx, dy) != (0, 0))
                    nxt[y][x] = n == 3 or (g[y][x] and n == 2)
            self.grid = nxt
            sig = hash(tuple(tuple(r) for r in nxt))
            self.history = (self.history + [sig])[-8:]
            if len(self.history) == 8 and len(set(self.history)) <= 2:
                self.reseed()
        col = hsv(self.hue, 0.8, 0.75)
        for y in range(H):
            for x in range(W):
                buf[y * W + x] = col if self.grid[y][x] else (2, 2, 6)


class Starfield(Scene):
    name = "stars"

    def __init__(self, *_):
        self.stars = [(random.randrange(W), random.randrange(H),
                       random.uniform(0, 6.3), random.uniform(0.5, 1.8))
                      for _ in range(16)]
        self.shoot = None      # (x, y, dx, dy, t0)
        self.next_shoot = time.monotonic() + random.uniform(4, 10)

    def draw(self, buf, now):
        for i in range(144):
            buf[i] = (1, 1, 4)
        for x, y, phase, speed in self.stars:
            v = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(now * speed + phase))
            c = int(210 * v)
            buf[y * W + x] = (c, c, int(c * 1.1) if c < 230 else 255)
        if self.shoot is None and now >= self.next_shoot:
            self.shoot = (random.uniform(0, 4), random.uniform(0, 3), 9.0, 5.0, now)
        if self.shoot:
            x0, y0, dx, dy, t0 = self.shoot
            age = now - t0
            for trail in range(4):
                px = x0 + dx * (age - trail * 0.05)
                py = y0 + dy * (age - trail * 0.05)
                if 0 <= px < W and 0 <= py < H:
                    v = 255 - trail * 60
                    buf[int(py) * W + int(px)] = (v, v, v)
            if x0 + dx * age > W + 2:
                self.shoot = None
                self.next_shoot = now + random.uniform(4, 12)


class Bounce(Scene):
    name = "bounce"

    def __init__(self, *_):
        self.x, self.y = 3.0, 4.0
        self.vx, self.vy = 3.1, 2.3
        self.hue = 0.0
        self.last = time.monotonic()

    def draw(self, buf, now):
        dt = min(0.3, now - self.last)
        self.last = now
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x <= 0 or self.x >= W - 2:
            self.vx *= -1; self.x = max(0, min(W - 2, self.x)); self.hue += 0.17
        if self.y <= 0 or self.y >= H - 2:
            self.vy *= -1; self.y = max(0, min(H - 2, self.y)); self.hue += 0.17
        for i in range(144):
            buf[i] = (0, 0, 0)
        col = hsv(self.hue, 0.9, 0.9)
        for dy in (0, 1):
            for dx in (0, 1):
                buf[(int(self.y) + dy) * W + int(self.x) + dx] = col


SCENES = [Clock, Fire, Plasma, Rain, Life, Starfield, Bounce]


class Ambient(Game):
    fps = 14

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        allowed = self.cfg.get("scenes")            # optional allow-list, e.g. ["clock"]
        self.scenes = ([s for s in SCENES if s.name in allowed] or SCENES) \
            if isinstance(allowed, list) and allowed else SCENES
        names = [s.name for s in self.scenes]
        self.idx = names.index(self.cfg["scene"]) if self.cfg["scene"] in names else 0
        self.scene = self.scenes[self.idx](self.cfg)
        self.next_rotate = time.monotonic() + self.cfg["rotate_minutes"] * 60
        locked = len(self.scenes) == 1
        log(f"ambient up — scene '{self.scene.name}'"
            + ("" if locked else ", press any pad for the next one"))

    def _switch(self, idx: int) -> None:
        self.idx = idx % len(self.scenes)
        self.scene = self.scenes[self.idx](self.cfg)
        self.cfg["scene"] = self.scene.name
        self.next_rotate = time.monotonic() + self.cfg["rotate_minutes"] * 60
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
        except Exception:
            pass
        log(f"scene -> {self.scene.name}")

    def on_press(self, x, y):
        if len(self.scenes) > 1:                    # locked to one scene -> no cycling
            self._switch(self.idx + 1)

    def update(self, dt):
        if len(self.scenes) > 1 and time.monotonic() >= self.next_rotate:
            self._switch(self.idx + 1)

    def _dim_factor(self) -> float:
        f = self.cfg["brightness"] / 100.0
        nd = self.cfg.get("night_dim") or {}
        start, end = nd.get("start", 22), nd.get("end", 8)
        hour = time.localtime().tm_hour
        night = start <= hour or hour < end if start > end else start <= hour < end
        if night:
            f *= nd.get("brightness", 25) / 100.0
        return f

    def draw(self, screen):
        buf = [(0, 0, 0)] * 144
        self.scene.draw(buf, time.monotonic())
        f = self._dim_factor()
        screen.px = [tuple(min(255, int(v * f)) for v in px) for px in buf]


if __name__ == "__main__":
    run(Ambient)
