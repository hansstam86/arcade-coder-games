#!/usr/bin/env python3
"""World Clocks — glance at several time zones on the Arcade Coder.

Shows a big HH:MM clock for one city, with a day-sky tint that follows that
city's local hour (deep blue at night, warm by day). A row of coloured dots
marks which city you're on. Tap anywhere to cycle cities — the name scrolls
past, then its clock.

Config in worldclock.json (auto-created): clock_24h, and a list of cities
  {name, tz (IANA, e.g. "Asia/Shanghai"), color [r,g,b]}.

  python worldclock.py        # emulator
"""

from __future__ import annotations

import colorsys
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:                       # pragma: no cover
    ZoneInfo = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "worldclock.json"
W = H = 12

DEFAULT = {
    "clock_24h": True,
    "cities": [
        {"name": "STOCKHOLM", "tz": "Europe/Stockholm", "color": [0, 120, 255]},
        {"name": "SHANGHAI", "tz": "Asia/Shanghai", "color": [255, 60, 0]},
        {"name": "NEW YORK", "tz": "America/New_York", "color": [0, 220, 80]},
        {"name": "SAN FRANCISCO", "tz": "America/Los_Angeles", "color": [255, 200, 0]},
    ],
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
DIGIT_POS = [(2, 0), (7, 0), (2, 7), (7, 7)]   # HH top, MM bottom


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


class WorldClock(Game):
    fps = 8

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.cities = self.cfg.get("cities") or DEFAULT["cities"]
        self.idx = 0
        self.name_scroll = None          # (start_time) while the name is scrolling
        self.busy = False
        log(f"world clock — {len(self.cities)} cities, tap to cycle")

    def _local(self, city):
        tz = city.get("tz")
        if ZoneInfo is not None and tz:
            try:
                return datetime.now(ZoneInfo(tz))
            except Exception:
                pass
        return datetime.now()            # fallback: Mac local time

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        self.idx = (self.idx + 1) % len(self.cities)
        self.name_scroll = time.monotonic()
        log(f"world clock -> {self.cities[self.idx]['name']}")

    def update(self, dt):
        if self.name_scroll is not None and time.monotonic() - self.name_scroll > 2.2:
            self.name_scroll = None

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        city = self.cities[self.idx]
        color = tuple(city.get("color", [200, 200, 200]))
        t = self._local(city)

        if self.name_scroll is not None:           # scroll the city name
            screen.clear((6, 6, 14))
            cols = render_columns(city["name"])
            speed = 9.0
            off = (time.monotonic() - self.name_scroll) * speed
            for sx in range(W):
                ci = int(off) - (W - 1 - sx)
                if 0 <= ci < len(cols):
                    colbits = cols[ci]
                    for r in range(5):
                        if colbits[r]:
                            screen.set(sx, 3 + r, color)
            return

        # day-sky background from this city's local hour
        day = (t.hour + t.minute / 60) / 24
        sun = max(0.0, math.sin((day - 0.25) * 2 * math.pi))
        sky = hsv(0.62 - 0.12 * sun, 0.9 - 0.35 * sun, 0.05 + 0.10 * sun)
        screen.clear(sky)

        hour = t.hour if self.cfg.get("clock_24h", True) else (t.hour % 12 or 12)
        text = f"{hour:02d}{t.minute:02d}"
        for ch, (ox, oy) in zip(text, DIGIT_POS):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, (235, 235, 235))
        if t.second % 2 == 0:                       # blinking separator
            screen.set(5, 6, color); screen.set(6, 6, color)

        # city selector dots (row 5), current one bright/pulsing
        n = len(self.cities)
        x0 = (W - (2 * n - 1)) // 2
        pulse = 0.5 + 0.5 * abs((time.monotonic() * 1.5) % 2 - 1)
        for i, c in enumerate(self.cities):
            col = tuple(c.get("color", [180, 180, 180]))
            if i == self.idx:
                col = tuple(min(255, int(v * (0.6 + 0.6 * pulse)) + 40) for v in col)
            else:
                col = tuple(v // 4 for v in col)
            screen.set(x0 + i * 2, 5, col)


if __name__ == "__main__":
    run(WorldClock)
