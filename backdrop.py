#!/usr/bin/env python3
"""Backdrop — slow, elegant ambient scenes to sit on a shelf behind you.

Five living visuals meant as a calm camera background: aurora, a lo-fi rainy
window, drifting jellyfish, a flowing particle field, and a lava lamp. Tap
anywhere to cycle scenes (the name flashes); the choice is remembered. It
stays on (won't idle back to the clock) so it holds through a meeting.

Config in backdrop.json (auto-created): scene, brightness (0–100).

  python backdrop.py          # emulator
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
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "backdrop.json"
W = H = 12

DEFAULT = {"scene": "aurora", "brightness": 85, "mirror": True}


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, max(0.0, min(1.0, v)))
    return int(r * 255), int(g * 255), int(b * 255)


def blend(a, b, t):
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


# ---- scenes ---------------------------------------------------------------
class Aurora:
    name = "AURORA"

    def draw(self, buf, now, dt):
        t = now * 0.22
        for x in range(W):
            b1 = 6 + 3.0 * math.sin(x * 0.55 + t * 1.2) + 1.5 * math.sin(x * 1.1 - t * 0.7)
            b2 = 4.5 + 2.2 * math.sin(x * 0.4 - t * 0.9 + 2.0)
            hue = 0.40 + 0.16 * math.sin(x * 0.33 + t * 0.6)
            for y in range(H):
                v = max(0.0, 1 - abs(y - b1) / 3.0) ** 1.7
                v += 0.5 * max(0.0, 1 - abs(y - b2) / 2.6) ** 1.7
                v *= 0.72 + 0.28 * math.sin(now * 3 + x * 1.3 + y * 0.7)
                v = max(0.0, min(1.0, v))
                buf[y * W + x] = blend((2, 3, 12), hsv(hue, 0.85, 1.0), v)


class RainyWindow:
    name = "LOFI"

    def __init__(self):
        random.seed(7)
        self.sky = [(h, random.randint(3, 7)) for h in range(W)]     # building heights
        self.win = {(x, H - 1 - k): random.random() < 0.5
                    for x in range(W) for k in range(7)}
        self.twinkle = [random.uniform(0, 6.3) for _ in range(W)]
        self.drops = [[random.uniform(0, W), random.uniform(0, H), random.uniform(9, 15)]
                      for _ in range(9)]
        self.lightning = 0.0

    def draw(self, buf, now, dt):
        flash = now < self.lightning
        for y in range(H):
            base = (8, 10, 26) if not flash else (120, 130, 170)
            top = blend(base, (2, 3, 12), y / H if not flash else 0)
            for x in range(W):
                buf[y * W + x] = top
        for x, hgt in self.sky:                       # buildings + windows
            for k in range(hgt):
                y = H - 1 - k
                lit = self.win.get((x, y), False)
                if lit:
                    tw = 0.6 + 0.4 * math.sin(now * 1.5 + self.twinkle[x])
                    buf[y * W + x] = (int(230 * tw), int(180 * tw), int(60 * tw))
                else:
                    buf[y * W + x] = (10, 10, 16)
        for d in self.drops:                          # rain
            d[0] += 2.2 * dt
            d[1] += d[2] * dt
            if d[1] >= H:
                d[0], d[1] = random.uniform(0, W), random.uniform(-2, 0)
            x, y = int(d[0]) % W, int(d[1])
            if 0 <= y < H:
                buf[y * W + x] = blend(buf[y * W + x], (150, 190, 255), 0.7)
        if not flash and random.random() < 0.006:
            self.lightning = now + 0.16


class Jellyfish:
    name = "JELLY"

    def __init__(self):
        self.js = [self._new(random.uniform(0, H)) for _ in range(3)]

    def _new(self, y):
        return {"x": random.uniform(2, W - 2), "y": y,
                "hue": random.choice([0.5, 0.75, 0.85]),
                "spd": random.uniform(0.7, 1.3), "ph": random.uniform(0, 6.3)}

    def draw(self, buf, now, dt):
        for i in range(144):
            buf[i] = (1, 3, 16)
        for j in self.js:
            j["y"] -= j["spd"] * dt
            if j["y"] < -3:
                j.update(self._new(H + 2))
            cx, cy = j["x"], j["y"]
            fade = max(0.0, min(1.0, (j["y"]) / (H - 2)))        # dim near the top
            bell = 1.6 + 0.5 * math.sin(now * 2.2 + j["ph"])     # pulsing bell
            col = hsv(j["hue"], 0.7, 1.0)
            for yy in range(H):
                for xx in range(W):
                    d = math.hypot(xx - cx, (yy - cy) * 1.3)
                    if d <= bell and yy <= cy + 0.5:             # dome
                        v = (1 - d / bell) * fade
                        buf[yy * W + xx] = blend(buf[yy * W + xx], col, min(1, v * 1.2))
            for k in range(1, 5):                                # tentacles
                ty = int(cy + k)
                if 0 <= ty < H:
                    off = math.sin(now * 3 + k + j["ph"]) * 0.8
                    tx = int(cx + off)
                    if 0 <= tx < W:
                        v = fade * (1 - k / 5) * 0.7
                        buf[ty * W + tx] = blend(buf[ty * W + tx], col, v)


class FlowField:
    name = "FLOW"

    def __init__(self):
        self.p = [[random.uniform(0, W), random.uniform(0, H), random.random()]
                  for _ in range(46)]
        self.fade = [(0, 0, 0)] * 144

    def draw(self, buf, now, dt):
        self.fade = [tuple(int(c * 0.82) for c in px) for px in self.fade]
        t = now * 0.25
        for pt in self.p:
            x, y, hue = pt
            a = (math.sin(x * 0.6 + t) + math.cos(y * 0.6 - t * 1.1)
                 + math.sin((x + y) * 0.35 + t * 0.7)) * 1.3
            x += math.cos(a) * 3.2 * dt * 3
            y += math.sin(a) * 3.2 * dt * 3
            if not (0 <= x < W): x %= W
            if not (0 <= y < H): y %= H
            pt[0], pt[1] = x, y
            col = hsv(0.55 + hue * 0.35 + now * 0.02, 0.85, 1.0)
            self.fade[int(y) * W + int(x)] = col
        for i in range(144):
            buf[i] = blend((2, 2, 8), self.fade[i], 1.0) if self.fade[i] != (0, 0, 0) \
                else (2, 2, 8)


class LavaLamp:
    name = "LAVA"

    def __init__(self):
        self.blobs = [[random.uniform(2, W - 2), random.uniform(2, H - 2),
                       random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2),
                       random.uniform(2.2, 3.2)] for _ in range(4)]

    def draw(self, buf, now, dt):
        for b in self.blobs:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            if b[0] < 1 or b[0] > W - 1:
                b[2] *= -1; b[0] = max(1, min(W - 1, b[0]))
            if b[1] < 1 or b[1] > H - 1:
                b[3] *= -1; b[1] = max(1, min(H - 1, b[1]))
        for y in range(H):
            for x in range(W):
                f = 0.0
                for b in self.blobs:
                    f += b[4] * b[4] / ((x - b[0]) ** 2 + (y - b[1]) ** 2 + 0.6)
                if f > 1.0:
                    hue = (0.02 + 0.12 * math.sin(now * 0.3) + f * 0.05) % 1.0
                    buf[y * W + x] = hsv(hue, 0.9, min(1.0, 0.35 + f * 0.25))
                else:
                    buf[y * W + x] = blend((14, 2, 8), (40, 6, 20), min(1.0, f))


SCENES = [Aurora, RainyWindow, Jellyfish, FlowField, LavaLamp]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Backdrop(Game):
    fps = 14

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        names = [s.name.lower() for s in SCENES]
        want = str(self.cfg.get("scene", "aurora")).lower()
        self.idx = names.index(want) if want in names else 0
        self.scene = SCENES[self.idx]()
        self.name_until = time.monotonic() + 2.0
        self.busy = True                 # hold through a meeting
        self.last = time.monotonic()
        log(f"backdrop — {self.scene.name}")

    def on_press(self, x, y):
        self.idx = (self.idx + 1) % len(SCENES)
        self.scene = SCENES[self.idx]()
        self.name_until = time.monotonic() + 2.0
        self.cfg["scene"] = self.scene.name.lower()
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
        except Exception:
            pass
        log(f"backdrop -> {self.scene.name}")

    def draw(self, screen):
        now = time.monotonic()
        dt = min(0.2, now - self.last)
        self.last = now
        buf = [(0, 0, 0)] * 144
        self.scene.draw(buf, now, dt)
        f = max(0.05, self.cfg.get("brightness", 85) / 100.0)
        screen.px = [tuple(min(255, int(v * f)) for v in px) for px in buf]

        if now < self.name_until:                    # scroll the scene name past
            cols = render_columns(self.scene.name)
            off = (now - (self.name_until - 2.0)) * 15   # cols/sec, right-to-left
            for sx in range(W):
                ci = int(off) - (W - 1 - sx)
                if 0 <= ci < len(cols):
                    for r in range(5):
                        if cols[ci][r]:
                            screen.set(sx, 3 + r, (255, 255, 255))

        if self.cfg.get("mirror", True):             # flip for a mirrored webcam
            p = screen.px
            screen.px = [p[y * W + (W - 1 - x)] for y in range(H) for x in range(W)]


if __name__ == "__main__":
    run(Backdrop)
