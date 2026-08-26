#!/usr/bin/env python3
"""Studio Clock — a broadcast-style clock for the Arcade Coder.

Big HH:MM in the middle, with a seconds ring sweeping smoothly around the
border: it fills red over the minute behind a bright white "hand", with dim
hour ticks like a clock face, and resets each minute. Tap to scroll the date.
Meant to sit on a shelf behind you on camera — clean and professional.

Config in studioclock.json: clock_24h (bool), accent [r,g,b], brightness.

  python studioclock.py       # emulator
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "studioclock.json"
W = H = 12

DEFAULT = {"clock_24h": True, "accent": [255, 45, 45], "brightness": 90, "mirror": True}

FONT = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}
DIGIT_POS = [(2, 1), (7, 1), (2, 6), (7, 6)]      # HH top, MM bottom (inside the ring)


def _ring():
    loop = [(x, 0) for x in range(W)]
    loop += [(W - 1, y) for y in range(1, H)]
    loop += [(x, H - 1) for x in range(W - 2, -1, -1)]
    loop += [(0, y) for y in range(H - 2, 0, -1)]
    i = loop.index((6, 0))                        # start at 12 o'clock (top centre)
    return loop[i:] + loop[:i]


RING = _ring()
RN = len(RING)                                    # 44
TICKS = {round(k * RN / 12) % RN for k in range(12)}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class StudioClock(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.accent = tuple(self.cfg.get("accent", [255, 45, 45]))
        self.date_until = 0.0
        self.busy = True
        log("studio clock ready")

    def on_press(self, x, y):
        self.date_until = time.monotonic() + 2.6    # scroll the date

    def draw(self, screen):
        now = time.monotonic()
        t = datetime.now()
        secs = t.second + time.time() % 1            # smooth sub-second
        screen.clear((0, 0, 0))

        # seconds ring — dim track + hour ticks, red fill behind a white hand
        lit = secs / 60 * RN
        for k, (x, y) in enumerate(RING):
            if k < lit:
                g = 0.35 + 0.65 * (k / max(1.0, lit))
                screen.set(x, y, tuple(int(c * g) for c in self.accent))
            else:
                screen.set(x, y, (55, 55, 62) if k in TICKS else (16, 16, 20))
        hx, hy = RING[int(lit) % RN]
        screen.set(hx, hy, (255, 255, 255))

        # big HH:MM in the centre
        hour = t.hour if self.cfg.get("clock_24h", True) else (t.hour % 12 or 12)
        text = f"{hour:02d}{t.minute:02d}"
        col = (240, 240, 235)
        for ch, (ox, oy) in zip(text, DIGIT_POS):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, col)

        # date scroll (on tap), over the middle
        if now < self.date_until:
            ds = t.strftime("%a %d %b").upper()
            cols = render_columns(ds)
            off = (now - (self.date_until - 2.6)) * 16
            for r in range(2, 9):                    # dark band for legibility
                for x in range(2, 10):
                    screen.set(x, r, (0, 0, 0))
            for sx in range(1, 11):
                ci = int(off) - (10 - sx)
                if 0 <= ci < len(cols):
                    for r in range(5):
                        if cols[ci][r]:
                            screen.set(sx, 3 + r, self.accent)

        # global brightness
        f = max(0.1, self.cfg.get("brightness", 90) / 100.0)
        screen.px = [tuple(int(c * f) for c in px) for px in screen.px]
        if self.cfg.get("mirror", True):             # flip for a mirrored webcam
            p = screen.px
            screen.px = [p[y * W + (W - 1 - x)] for y in range(H) for x in range(W)]


if __name__ == "__main__":
    run(StudioClock)
