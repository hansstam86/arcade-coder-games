#!/usr/bin/env python3
"""Stopwatch — count-up timer with laps for the Arcade Coder.

Big MM:SS (minutes over seconds). Middle control bar:

    [ LAP ][ START / PAUSE ][ RESET ]

Tapping LAP records a split and flashes the time in yellow for a moment;
lap count shows as dots on the top row. START/PAUSE toggles; RESET zeroes it.

  python stopwatch.py         # emulator
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12
BAND = (5, 6)
MINUTE_POS = [(2, 0), (7, 0)]
SECOND_POS = [(2, 7), (7, 7)]

FONT = {
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


class Stopwatch(Game):
    fps = 12

    def start(self):
        self.elapsed = 0.0
        self.running = False
        self.laps = []
        self.lap_show_until = 0.0
        self.lap_value = 0.0
        self.flash_until = 0.0
        self.busy = False
        self.last = time.monotonic()
        log("stopwatch ready — centre = start/pause, left = lap, right = reset")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if y not in BAND:
            return
        now = time.monotonic()
        if x <= 3:                              # LAP
            if self.elapsed > 0:
                self.laps.append(self.elapsed)
                self.lap_value = self.elapsed
                self.lap_show_until = now + 1.6
                self.flash_until = now + 0.12
                log(f"lap {len(self.laps)}: {self._fmt(self.elapsed)}")
        elif x >= 8:                            # RESET
            self.elapsed = 0.0
            self.running = False
            self.laps = []
            self.lap_show_until = 0.0
        else:                                   # START / PAUSE
            self.running = not self.running
            self.last = now

    def update(self, dt):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.busy = self.running
        if self.running:
            self.elapsed += elapsed

    # -- render --------------------------------------------------------------
    def _fmt(self, secs):
        s = int(secs)
        return f"{min(99, s // 60):02d}{s % 60:02d}"

    def _digits(self, screen, value, col):
        text = self._fmt(value)
        for ch, (ox, oy) in zip(text, MINUTE_POS + SECOND_POS):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, col)

    def _fill(self, screen, xs, color):
        for yy in BAND:
            for xx in xs:
                screen.set(xx, yy, color)

    def draw(self, screen):
        now = time.monotonic()
        if now < self.flash_until:
            screen.clear((60, 60, 20))
        else:
            screen.clear((0, 0, 0))
        showing_lap = now < self.lap_show_until
        value = self.lap_value if showing_lap else self.elapsed
        col = (255, 230, 60) if showing_lap else \
            ((235, 235, 235) if self.running else (120, 120, 120))
        self._digits(screen, value, col)
        # control bar
        self._fill(screen, range(0, 4), (30, 90, 200))       # LAP (blue)
        self._fill(screen, range(4, 8),                      # START / PAUSE
                   (255, 170, 0) if self.running else (0, 200, 80))
        self._fill(screen, range(8, 12), (170, 30, 30))      # RESET (red)


if __name__ == "__main__":
    run(Stopwatch)
