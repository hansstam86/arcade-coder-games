#!/usr/bin/env python3
"""Pomodoro timer — a focus/break timer for the Arcade Coder.

A depleting ring around the board counts down the current interval; the
minutes remaining show in the middle. Work sessions are tomato-red, short
breaks green, the long break (after N rounds) blue. When an interval ends the
board flashes and the next one begins automatically.

Controls (press):
  centre / most of the board .... start / pause
  top-right button (amber) ...... cycle the interval preset (25/5, 50/10, ...)
  bottom-left button (blue) ..... reset the current interval
  bottom-right button (white) ... skip to the next interval

Config in pomodoro.json (auto-created):
  presets (list of {name, work, short, long, rounds}), preset (chosen index),
  auto_start (roll straight into the next interval when one ends)

  python pomodoro.py          # emulator
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "pomodoro.json"

PRESETS = [
    {"name": "classic",   "work": 25, "short": 5,  "long": 15, "rounds": 4},
    {"name": "deep",      "work": 50, "short": 10, "long": 30, "rounds": 4},
    {"name": "short",     "work": 15, "short": 3,  "long": 15, "rounds": 4},
    {"name": "ultradian", "work": 90, "short": 20, "long": 30, "rounds": 2},
]

DEFAULT = {
    "presets": PRESETS,
    "preset": 0,          # index of the active preset (cycled on-device)
    "auto_start": True,   # begin the next interval automatically
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

# phase -> (label, full colour, dim background colour)
PHASES = {
    "work":  ((255, 70, 40),  (40, 8, 4)),
    "short": ((0, 200, 90),   (2, 30, 12)),
    "long":  ((0, 130, 255),  (2, 14, 40)),
}

PRESET_BTN = (10, 1)
RESET_BTN = (1, 10)
SKIP_BTN = (10, 10)


def _ring_cells() -> list[tuple[int, int]]:
    """Interior perimeter (cols 1..10, rows 1..10), clockwise from top-left."""
    cells = [(x, 1) for x in range(1, 11)]          # top, left->right
    cells += [(10, y) for y in range(2, 11)]        # right, top->bottom
    cells += [(x, 10) for x in range(9, 0, -1)]     # bottom, right->left
    cells += [(1, y) for y in range(9, 1, -1)]      # left, bottom->top
    return cells


RING = _ring_cells()  # 36 cells


class Pomodoro(Game):
    fps = 8

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.presets = self.cfg.get("presets") or PRESETS
        self.preset_idx = max(0, min(len(self.presets) - 1,
                                     int(self.cfg.get("preset", 0))))
        self.completed = 0            # finished work sessions
        self.phase = "work"
        self.total = self._duration("work")
        self.remaining = float(self.total)
        self.running = False
        self.busy = False             # true while counting -> block auto-ambient
        self.flash_until = 0.0        # phase-change celebration
        self.last = time.monotonic()
        log(f"pomodoro ready — preset '{self._preset()['name']}' "
            f"({self._preset()['work']} min work), press to start")

    # -- timer model ---------------------------------------------------------
    def _preset(self) -> dict:
        return self.presets[self.preset_idx]

    def _duration(self, phase: str) -> int:
        key = {"work": "work", "short": "short", "long": "long"}[phase]
        return max(1, int(self._preset()[key])) * 60

    def _rounds(self) -> int:
        return max(1, int(self._preset().get("rounds", 4)))

    def _cycle_preset(self) -> None:
        self.preset_idx = (self.preset_idx + 1) % len(self.presets)
        self.cfg["preset"] = self.preset_idx
        self._load_phase("work", False)     # restart at the new work length
        self.completed = 0
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
        except Exception:
            pass
        log(f"pomodoro preset -> {self._preset()['name']} "
            f"({self._preset()['work']}/{self._preset()['short']})")

    def _load_phase(self, phase: str, run_it: bool) -> None:
        self.phase = phase
        self.total = self._duration(phase)
        self.remaining = float(self.total)
        self.running = run_it

    def _advance(self) -> None:
        """Move to the next interval when the current one hits zero."""
        if self.phase == "work":
            self.completed += 1
            nxt = "long" if self.completed % self._rounds() == 0 else "short"
        else:
            nxt = "work"
        self.flash_until = time.monotonic() + 2.5
        self._load_phase(nxt, self.cfg.get("auto_start", True))
        log(f"pomodoro -> {self.phase} ({self.total // 60} min), "
            f"{self.completed} done")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == PRESET_BTN:
            self._cycle_preset()
            return
        if (x, y) == RESET_BTN:
            self._load_phase(self.phase, False)
            log("pomodoro reset")
            return
        if (x, y) == SKIP_BTN:
            # skip counts a work session as done, like finishing it
            if self.phase == "work":
                self.completed += 1
            nxt = ("long" if self.phase == "work"
                   and self.completed % self._rounds() == 0
                   else "short" if self.phase == "work" else "work")
            self._load_phase(nxt, False)
            log(f"pomodoro skip -> {self.phase}")
            return
        self.running = not self.running     # anywhere else = start/pause

    def update(self, dt):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.busy = self.running
        if self.running:
            self.remaining -= elapsed
            if self.remaining <= 0:
                self._advance()

    # -- render --------------------------------------------------------------
    def _digits(self, screen, now: float) -> None:
        secs = max(0, int(self.remaining + 0.99))
        final_min = secs < 60
        value = secs if final_min else (secs + 59) // 60   # ceil to minutes
        text = f"{min(99, value):02d}"
        col = (255, 235, 120) if final_min else (235, 235, 235)
        if not self.running and int(now * 2) % 2 == 0:     # blink while paused
            col = tuple(c // 4 for c in col)
        positions = [(2, 4), (6, 4)]                       # two 3x5 digits
        for ch, (ox, oy) in zip(text, positions):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, col)

    def draw(self, screen):
        now = time.monotonic()
        full, dim = PHASES[self.phase]
        screen.clear((0, 0, 0))
        # phase-change flash: whole interior pulses
        if now < self.flash_until:
            on = int(now * 6) % 2 == 0
            c = full if on else dim
            for y in range(1, 11):
                for x in range(1, 11):
                    screen.set(x, y, c)
            self._digits(screen, now)
            self._buttons(screen)
            return
        # dim interior background
        for y in range(1, 11):
            for x in range(1, 11):
                screen.set(x, y, dim)
        # depleting ring
        frac = self.remaining / self.total if self.total else 0
        lit = int(round(frac * len(RING)))
        for i, (x, y) in enumerate(RING):
            screen.set(x, y, full if i < lit else tuple(c // 3 for c in full))
        self._digits(screen, now)
        self._buttons(screen)

    def _buttons(self, screen) -> None:
        screen.set(*PRESET_BTN, (255, 180, 0))   # cycle preset (amber)
        screen.set(*RESET_BTN, (40, 90, 200))    # reset (blue)
        screen.set(*SKIP_BTN, (200, 200, 200))   # skip (white)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


if __name__ == "__main__":
    run(Pomodoro)
