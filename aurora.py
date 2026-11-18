#!/usr/bin/env python3
"""Aurora — the plasma, done properly. The ambient mode to end all ambient modes.

Four layered sine fields with incommensurate frequencies, a slowly
wandering virtual centre and a gentle global breath produce a flowing
colour field that never repeats itself. Palettes are curated, not raw
rainbow: aurora borealis, sunset, euromaxxing gold-on-reflex-blue and
classic rainbow.

Pads (same five-corner layout):
  top-left     freeze / resume the flow
  top-right    cycle speed: stately / flowing / brisk
  top-centre   cycle palette: aurora -> sunset -> euromaxxing -> rainbow
  bottom-left  still the water (clear all ripples)
  bottom-right a big central pulse
Any other pad drops a ripple into the field at that point — touch the
aurora and watch it shiver outward and settle.

aurora.json (auto-created, hot-reloads): speeds, breathing.

  python aurora.py             # emulator at http://127.0.0.1:7777
  python aurora.py --hw        # real board over BLE
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "aurora.json"

DEFAULT = {
    "speeds": [0.4, 0.8, 1.6],   # flow speed multipliers
    "speed_index": 1,
    "breathing": True,            # slow global brightness breath
}

PALETTES = (
    ("aurora", ((10, 12, 45), (0, 90, 130), (0, 210, 170),
                (70, 240, 120), (40, 120, 220), (130, 40, 200))),
    ("sunset", ((25, 5, 30), (140, 20, 60), (255, 90, 40),
                (255, 200, 80), (200, 60, 110), (60, 15, 60))),
    ("euromaxxing", ((4, 20, 90), (0, 105, 255), (120, 180, 255),
                     (255, 204, 0), (180, 120, 0), (30, 40, 130))),
    ("rainbow", ((255, 0, 0), (255, 200, 0), (0, 230, 0),
                 (0, 220, 220), (40, 60, 255), (220, 40, 200))),
)

FREEZE_PAD = (0, 0)
SPEED_PAD = (11, 0)
PALETTE_PAD = (6, 0)
STILL_PAD = (0, 11)
PULSE_PAD = (11, 11)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _palette_color(stops, t: float):
    """Cyclic smooth interpolation through the palette stops."""
    t %= 1.0
    pos = t * len(stops)
    i = int(pos)
    f = pos - i
    a, b = stops[i % len(stops)], stops[(i + 1) % len(stops)]
    return tuple(int(a[c] + (b[c] - a[c]) * f) for c in range(3))


def _torus_dist(x: float, y: float, rx: float, ry: float) -> float:
    dx = abs(x - rx)
    dy = abs(y - ry)
    dx = min(dx, W - dx)
    dy = min(dy, H - dy)
    return math.sqrt(dx * dx + dy * dy)


class Aurora(Game):
    fps = 20

    def start(self):
        self._load()
        self.t = 0.0
        self.ripples: list[tuple[float, float, float, float]] = []   # x, y, t0, amp
        self.palette_i = 0
        self.running = True
        self.next_check = 0.0
        log("aurora — touch pads ripple the field; palette / speed / freeze "
            "on the corners")

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
    def speed(self) -> float:
        speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
        i = min(int(self.cfg.get("speed_index", 1)), len(speeds) - 1)
        return float(speeds[i])

    # -- the field ----------------------------------------------------------------
    def field(self, x: float, y: float) -> float:
        t = self.t
        cx = 5.5 + 3.5 * math.sin(t * 0.13)
        cy = 5.5 + 3.5 * math.sin(t * 0.17 + 1.7)
        v = (math.sin(x * 0.42 + t * 0.9)
             + math.sin(y * 0.47 - t * 0.7)
             + math.sin((x + y) * 0.30 + t * 0.5)
             + math.sin(math.sqrt((x - cx) ** 2 + (y - cy) ** 2) * 0.85 - t * 1.3))
        for rx, ry, rt, amp in self.ripples:
            s = t - rt
            if s < 0:
                continue
            d = _torus_dist(x, y, rx, ry)
            v += amp * math.exp(-s * 0.7) * math.sin(d * 2.0 - s * 7.0) * max(0.0, 1.0 - d * 0.08)
        return v

    def add_ripple(self, x: float, y: float, amp: float = 1.2) -> None:
        self.ripples.append((x, y, self.t, amp))
        self.ripples = self.ripples[-8:]          # keep only the young ones
        log(f"ripple at ({x:g},{y:g})")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == FREEZE_PAD:
            self.running = not self.running
            log("frozen" if not self.running else "flowing")
        elif (x, y) == SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 1)) + 1) % len(speeds)
            log(f"speed -> {self.speed:g}")
        elif (x, y) == PALETTE_PAD:
            self.palette_i = (self.palette_i + 1) % len(PALETTES)
            log(f"palette -> {PALETTES[self.palette_i][0]}")
        elif (x, y) == STILL_PAD:
            self.ripples = []
            log("still — ripples cleared")
        elif (x, y) == PULSE_PAD:
            self.add_ripple(5.5, 5.5, amp=2.5)
        else:
            self.add_ripple(x, y)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            self.t += dt * self.speed
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("aurora.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        stops = PALETTES[self.palette_i][1]
        breathe = (0.92 + 0.08 * math.sin(self.t * 0.4)) if self.cfg.get("breathing", True) else 1.0
        for y in range(H):
            for x in range(W):
                # the field spans a little over half a palette cycle, drifting
                # slowly through the hues so even a frozen field breathes
                p = (self.field(x, y) * 0.09 + self.t * 0.015) % 1.0
                r, g, b = _palette_color(stops, p)
                screen.set(x, y, (int(r * breathe), int(g * breathe), int(b * breathe)))
        # HUD pads
        screen.set(*FREEZE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*SPEED_PAD, (30, 90, 230))
        screen.set(*PALETTE_PAD, (240, 140, 20))
        screen.set(*STILL_PAD, (60, 60, 60))
        screen.set(*PULSE_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(Aurora)