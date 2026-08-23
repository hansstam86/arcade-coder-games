#!/usr/bin/env python3
"""Chase — the smallest possible arcadecoder game.

A green target sits somewhere; press it to score and it jumps elsewhere.
You have 15 seconds. Run with `python examples/chase.py` (emulator) or
`python examples/chase.py --hw` (real board).
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arcadecoder import Game, run


class Chase(Game):
    fps = 10

    def start(self):
        self.target = (5, 5)
        self.score = 0
        self.time_left = 15.0

    def on_press(self, x, y):
        if (x, y) == self.target:
            self.score += 1
            self.target = (random.randrange(12), random.randrange(12))

    def update(self, dt):
        self.time_left -= dt
        if self.time_left <= 0:
            self.end()

    def draw(self, screen):
        screen.clear()
        if self.time_left > 0:
            screen.set(*self.target, (0, 220, 0))
            bar = round(12 * self.time_left / 15)
            for x in range(bar):
                screen.set(x, 11, (0, 40, 120))
        else:  # score screen
            for i in range(min(self.score, 144)):
                screen.set(i % 12, i // 12, (0, 200, 0))


if __name__ == "__main__":
    run(Chase)
