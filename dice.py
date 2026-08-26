#!/usr/bin/env python3
"""Dice — a fair dice roller for board games on the Arcade Coder.

Tap anywhere to roll. The dice tumble briefly, then settle. Fairness: the
committed result comes from Python's `secrets` module — a cryptographically
secure RNG seeded from OS entropy — via `secrets.randbelow(6)`, which is
UNBIASED (no modulo bias; each face is exactly 1/6). The fast face changes
during the tumble are just animation and never decide the outcome.

The right-edge pad toggles between one and two dice.

  python dice.py              # emulator
"""

from __future__ import annotations

import random          # animation only (never decides a result)
import secrets         # the real, fair source of the roll
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

# pip layout: a 3x3 grid of slots (col, row) per face value
FACES = {
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
    4: [(0, 0), (2, 0), (0, 2), (2, 2)],
    5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)],
    6: [(0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)],
}
SLOTS = {5: [1, 2, 3], 7: [1, 3, 5]}       # slot centres for a die of each size
BODY_A = (150, 25, 25)
BODY_B = (25, 45, 150)
BODY_1 = (150, 95, 0)
PIP = (255, 255, 255)
MODE_PAD = (11, 6)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fair_die() -> int:
    """A fair 1–6 from the OS CSPRNG (secrets), unbiased."""
    return secrets.randbelow(6) + 1


def draw_die(screen, ox, oy, size, value, body, bright=1.0):
    sl = SLOTS[size]
    b = tuple(min(255, int(c * bright)) for c in body)
    for i in range(size):
        for j in range(size):
            edge = i in (0, size - 1) or j in (0, size - 1)
            screen.set(ox + i, oy + j, b if edge else (8, 8, 12))
    pip = tuple(min(255, int(c * bright)) for c in PIP)
    for sc, sr in FACES[value]:
        screen.set(ox + sl[sc], oy + sl[sr], pip)


class Dice(Game):
    fps = 15

    def start(self):
        self.count = 2
        self.dice = [fair_die() for _ in range(self.count)]
        self.rolling_until = 0.0
        self.next_change = 0.0
        self.flash_until = 0.0
        self.busy = False
        log(f"dice ready — tap to roll (fair, via secrets). {self.dice}")

    def _roll(self):
        self.rolling_until = time.monotonic() + 0.7
        self.next_change = 0.0

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == MODE_PAD or (x == 11 and y in (5, 6)):
            self.count = 1 if self.count == 2 else 2
            self.dice = [fair_die() for _ in range(self.count)]
            log(f"dice: {self.count}")
            return
        self._roll()

    def update(self, dt):
        now = time.monotonic()
        if not self.rolling_until:
            return
        if now < self.rolling_until:
            if now >= self.next_change:            # tumble (display only)
                self.next_change = now + 0.05
                self.dice = [random.randint(1, 6) for _ in range(self.count)]
        else:                                      # settle on the FAIR result
            self.dice = [fair_die() for _ in range(self.count)]
            self.rolling_until = 0.0
            self.flash_until = now + 0.3
            log(f"rolled {self.dice} (sum {sum(self.dice)})")

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        rolling = bool(self.rolling_until)
        bright = 1.6 if now < self.flash_until else (0.7 if rolling else 1.0)
        shake = 1 if rolling and int(now * 20) % 2 else 0

        if self.count == 1:
            draw_die(screen, 2, 2 - shake, 7, self.dice[0], BODY_1, bright)
        else:
            draw_die(screen, 1, 3 - shake, 5, self.dice[0], BODY_A, bright)
            draw_die(screen, 6, 3 + shake, 5, self.dice[1], BODY_B, bright)

        # mode pad (right edge): 2 dots for two dice, 1 for one
        screen.set(11, 5, (0, 200, 120) if self.count == 2 else (30, 30, 30))
        screen.set(11, 6, (0, 200, 120))


if __name__ == "__main__":
    run(Dice)
