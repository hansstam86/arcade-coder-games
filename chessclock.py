#!/usr/bin/env python3
"""Chess clock — a two-player game timer for the Arcade Coder.

Two clocks: Player 1 (orange, top half) and Player 2 (blue, bottom half),
each showing MMSS. The active player's clock counts down; tap your own half
to end your move and start the opponent's clock. If your time hits zero your
flag falls and you lose.

Middle band controls:
  left pad  ... cycle time preset (1 / 3 / 5 / 10 min) and reset
  right pad ... pause / resume
  centre    ... arrow pointing at whose clock is running

Optional Fischer increment via chessclock.json (increment seconds, presets).

  python chessclock.py        # emulator
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "chessclock.json"
P1_COL = (255, 120, 40)
P2_COL = (60, 150, 255)

FONT = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class ChessClock(Game):
    fps = 10

    def start(self):
        self.cfg = {"presets": [60, 180, 300, 600], "increment": 0}
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.presets = self.cfg.get("presets") or [60, 180, 300, 600]
        self.increment = int(self.cfg.get("increment", 0))
        self.preset_idx = 2 if len(self.presets) > 2 else 0     # default 5 min
        self.busy = True
        self._reset()
        log("chess clock ready — tap your half to pass the turn")

    def _reset(self):
        t = float(self.presets[self.preset_idx])
        self.times = {1: t, 2: t}
        self.active = 1
        self.running = False
        self.winner = None
        self.last = time.monotonic()

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if y in (5, 6):                              # middle band controls
            if x <= 2:                               # cycle preset + reset
                self.preset_idx = (self.preset_idx + 1) % len(self.presets)
                self._reset()
                log(f"preset {self.presets[self.preset_idx] // 60} min")
            elif x >= 9:                             # pause / resume
                if self.winner is None:
                    self.running = not self.running
                    self.last = time.monotonic()
            return
        if self.winner is not None:                  # game over -> any half taps reset
            self._reset()
            return
        player = 1 if y <= 4 else 2
        if player != self.active:                    # only the active player's button counts
            return
        if not self.running:                         # first press / resume: start ticking
            self.running = True
        else:                                        # end turn -> opponent's clock
            self.times[player] += self.increment
            self.active = 2 if player == 1 else 1
        self.last = time.monotonic()

    def update(self, dt):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        if self.running and self.winner is None:
            self.times[self.active] -= elapsed
            if self.times[self.active] <= 0:
                self.times[self.active] = 0
                self.winner = 2 if self.active == 1 else 1
                self.running = False
                log(f"flag fall — Player {self.active} lost on time")

    # -- render --------------------------------------------------------------
    def _digits(self, screen, secs, oy, color):
        s = int(secs + 0.999)
        text = f"{min(99, s // 60):02d}{s % 60:02d}"
        for k, ch in enumerate(text):
            ox = k * 3
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, color)

    def _half_color(self, player, base, now):
        if self.winner == player:                    # winner glows
            p = 0.5 + 0.5 * abs((now * 2) % 2 - 1)
            return tuple(min(255, int(c * (0.5 + p))) for c in (0, 220, 90))
        loser = self.winner is not None and self.winner != player
        low = self.active == player and self.running and self.times[player] <= 10
        if loser or (low and int(now * 4) % 2):      # flash red when low / lost
            return (255, 40, 40)
        active = self.active == player and self.winner is None
        f = 1.0 if active else 0.28
        return tuple(int(c * f) for c in base)

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        self._digits(screen, self.times[1], 0, self._half_color(1, P1_COL, now))
        self._digits(screen, self.times[2], 7, self._half_color(2, P2_COL, now))

        # middle band: reset (left), turn arrow (centre), pause (right)
        for yy in (5, 6):
            for xx in range(0, 3):
                screen.set(xx, yy, (90, 90, 90))     # reset / preset
            pc = (0, 190, 70) if self.running else (220, 140, 0)
            for xx in range(9, 12):
                screen.set(xx, yy, pc if self.winner is None else (60, 60, 60))
        # arrow toward the active player's half
        ac = P1_COL if self.active == 1 else P2_COL
        arow = 5 if self.active == 1 else 6
        if self.winner is None:
            for xx in range(4, 8):
                screen.set(xx, arow, ac)
            screen.set(5, arow, (255, 255, 255)); screen.set(6, arow, (255, 255, 255))


if __name__ == "__main__":
    run(ChessClock)
