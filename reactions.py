#!/usr/bin/env python3
"""Reactions — a live engagement meter for the Arcade Coder.

Shows a count that climbs and bursts confetti every time it goes up — point it
at your LinkedIn post's reaction count and it becomes a physical "watch my
desk light up" meter behind you. Fed by the dashboard `POST /meter {count}`
(absolute total; the app celebrates each increase). Milestones flash the board.

  python reactions.py         # emulator (drive it with POST /meter)
"""

from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12

FONT = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}
CONFETTI = [(255, 210, 60), (0, 130, 255), (255, 60, 110), (0, 220, 90), (255, 255, 255)]
HEART = [(1, 1), (2, 0), (3, 1), (3, 2), (2, 3), (1, 2), (0, 1)]   # tiny 4x4 heart

# state pushed by the /meter API (module-level so the web thread can set it)
STATE = {"count": 0, "goal": 50}


def set_count(count, goal=None):
    STATE["count"] = max(0, int(count))
    if goal:
        STATE["goal"] = max(1, int(goal))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Reactions(Game):
    fps = 20

    def start(self):
        self.shown = STATE["count"]
        self.confetti = []
        self.flash_until = 0.0
        self.pop = 0.0
        self.busy = True
        self.last = time.monotonic()
        log(f"reactions meter — {self.shown}")

    def _burst(self, n, milestone=False):
        for _ in range(n):
            a = random.uniform(0, 6.28)
            sp = random.uniform(2, 7)
            self.confetti.append([5.5, 5.5, math.cos(a) * sp, math.sin(a) * sp - 2,
                                  random.choice(CONFETTI), 1.0])
        self.pop = time.monotonic() + 0.4
        if milestone:
            self.flash_until = time.monotonic() + 0.8

    def update(self, dt):
        now = time.monotonic()
        dt = min(0.1, now - self.last)
        self.last = now
        c = STATE["count"]
        if c > self.shown:
            delta = c - self.shown
            crossed = (c // 10) > (self.shown // 10)
            self.shown = c
            self._burst(min(30, 5 + delta * 5), milestone=crossed)
            log(f"reactions -> {c}")
        elif c < self.shown:
            self.shown = c                     # reset support
        for p in self.confetti:                # physics
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 9 * dt                      # gravity
            p[5] -= dt * 0.7
        self.confetti = [p for p in self.confetti if p[5] > 0 and p[1] < H + 1]

    # -- render --------------------------------------------------------------
    def _number(self, screen, n, color):
        text = str(min(999, n))
        width = len(text) * 3 + (len(text) - 1)
        x0 = (W - width) // 2
        pop = 1 if time.monotonic() < self.pop else 0
        oy = 3 - pop
        cx = x0
        for ch in text:
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(cx + dx, oy + dy, color)
            cx += 4

    def draw(self, screen):
        now = time.monotonic()
        if now < self.flash_until:                       # milestone flash
            on = int(now * 8) % 2
            screen.clear((60, 25, 0) if on else (0, 0, 0))
        else:
            screen.clear((0, 0, 0))
        # heart in the top-left corner
        beat = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(now * 3))
        for hx, hy in HEART:
            screen.set(hx, hy, (int(255 * beat), int(40 * beat), int(70 * beat)))
        # the count
        self._number(screen, self.shown, (255, 220, 80))
        # progress bar toward the goal (bottom row)
        goal = max(1, STATE.get("goal", 50))
        lit = min(W, round(self.shown / goal * W))
        for x in range(W):
            screen.set(x, 11, (0, 130, 255) if x < lit else (18, 22, 34))
        # confetti on top
        for p in self.confetti:
            x, y = int(p[0]), int(p[1])
            if 0 <= x < W and 0 <= y < H:
                f = max(0.0, min(1.0, p[5]))
                screen.set(x, y, tuple(int(c * f) for c in p[4]))


if __name__ == "__main__":
    run(Reactions)
