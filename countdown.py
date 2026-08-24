#!/usr/bin/env python3
"""Countdown timer — set the time on the board, then let it run down.

SET mode shows a big MM:SS (minutes on top, seconds below) with a control bar
across the middle:

    [-min][-sec][ START ][+sec][+min]

Green means add, red means subtract; the outer buttons step minutes, the inner
ones step seconds (5 s). The number updates as you press, so what you see is
what will run.

RUN mode ticks the time down, with controls in the corners:
    centre 2x2 ... pause / resume
    top-left ..... stop (back to SET)
    top-right .... +1 min (extend)
    bottom-left .. restart from the top

At zero the board flashes red and an alarm sound repeats until you press to
acknowledge.

Config in countdown.json (auto-created): target (last time in seconds),
  sec_step (seconds button step), alarm_sound (aiff path or "").

  python countdown.py         # emulator
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "countdown.json"
MAX_SECONDS = 99 * 60 + 59

DEFAULT = {
    "target": 5 * 60,
    "sec_step": 5,
    "alarm_sound": "/System/Library/Sounds/Glass.aiff",
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

MINUTE_POS = [(2, 0), (7, 0)]   # two digit blocks, top rows 0-4
SECOND_POS = [(2, 7), (7, 7)]   # two digit blocks, bottom rows 7-11
BAND = (5, 6)                   # control-bar rows

# SET control bar: (x-range, key) across the middle band
SET_BAR = [
    (range(0, 2),  "min-"),
    (range(2, 4),  "sec-"),
    (range(4, 8),  "start"),
    (range(8, 10), "sec+"),
    (range(10, 12), "min+"),
]

# RUN mode corner buttons
RUN_STOP = (1, 1)       # back to SET
RUN_EXTEND = (10, 1)    # +1 min
RUN_RESTART = (1, 10)   # restart from target
RUN_CENTER = {(5, 5), (6, 5), (5, 6), (6, 6)}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Countdown(Game):
    fps = 10

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.target = max(0, min(MAX_SECONDS, int(self.cfg.get("target", 300))))
        self.step = max(1, int(self.cfg.get("sec_step", 5)))
        self.mode = "set"           # set | run | alarm
        self.running = False
        self.remaining = float(self.target)
        self.busy = False
        self.alarm_on = False
        self.press_flash = {}       # button key -> monotonic expiry (tap feedback)
        self.last = time.monotonic()
        log(f"countdown ready — {self.target // 60:02d}:{self.target % 60:02d}")

    # -- setting -------------------------------------------------------------
    def _adjust(self, delta: int) -> None:
        self.target = max(0, min(MAX_SECONDS, self.target + delta))
        self.remaining = float(self.target)
        self._save()

    def _save(self) -> None:
        self.cfg["target"] = self.target
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
        except Exception:
            pass

    # -- alarm ---------------------------------------------------------------
    def _alarm_loop(self) -> None:
        snd = self.cfg.get("alarm_sound") or ""
        while self.alarm_on:
            if snd and Path(snd).exists():
                try:
                    subprocess.run(["afplay", snd], timeout=4)
                except Exception:
                    time.sleep(1.0)
            else:
                time.sleep(1.0)

    def _start_alarm(self) -> None:
        self.mode = "alarm"
        self.running = False
        if not self.alarm_on:
            self.alarm_on = True
            threading.Thread(target=self._alarm_loop, daemon=True).start()
        log("countdown finished — alarm (press to stop)")

    def _stop_alarm(self) -> None:
        self.alarm_on = False

    def _to_set(self) -> None:
        self._stop_alarm()
        self.mode = "set"
        self.running = False
        self.remaining = float(self.target)

    def _begin_run(self) -> None:
        self.mode = "run"
        self.running = True
        self.remaining = float(self.target)
        self.last = time.monotonic()
        log(f"countdown start — {self.target // 60:02d}:{self.target % 60:02d}")

    def stop(self) -> None:
        """Called by ArcadeOS when leaving the app — silence any alarm."""
        self._stop_alarm()

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if self.mode == "alarm":
            self._to_set()
            return
        if self.mode == "run":
            if (x, y) == RUN_STOP:
                self._to_set()
            elif (x, y) == RUN_EXTEND:
                self.remaining = min(MAX_SECONDS, self.remaining + 60)
            elif (x, y) == RUN_RESTART:
                self.remaining = float(self.target)
                self.running = True
                self.last = time.monotonic()
            elif (x, y) in RUN_CENTER:
                self.running = not self.running
            return
        # set mode: which bar button?
        if y in BAND:
            for xs, key in SET_BAR:
                if x in xs:
                    self.press_flash[key] = time.monotonic() + 0.15
                    if key == "min+":
                        self._adjust(60)
                    elif key == "min-":
                        self._adjust(-60)
                    elif key == "sec+":
                        self._adjust(self.step)
                    elif key == "sec-":
                        self._adjust(-self.step)
                    elif key == "start" and self.target > 0:
                        self._begin_run()
                    return

    def update(self, dt):
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.busy = self.mode in ("run", "alarm")
        if self.mode == "run" and self.running:
            self.remaining -= elapsed
            if self.remaining <= 0:
                self.remaining = 0.0
                self._start_alarm()

    # -- render --------------------------------------------------------------
    def _digits(self, screen, col, secs=None) -> None:
        s = self.remaining if secs is None else secs
        s = max(0, int(s + 0.99))
        text = f"{min(99, s // 60):02d}{s % 60:02d}"
        for ch, (ox, oy) in zip(text, MINUTE_POS + SECOND_POS):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, col)

    def _fill(self, screen, xs, rows, color) -> None:
        for yy in rows:
            for xx in xs:
                screen.set(xx, yy, color)

    def draw(self, screen):
        now = time.monotonic()
        if self.mode == "alarm":
            on = int(now * 5) % 2 == 0
            screen.clear((130, 0, 0) if on else (12, 0, 0))
            if on:
                self._digits(screen, (255, 255, 255))
            return

        screen.clear((0, 0, 0))
        if self.mode == "set":
            self._digits(screen, (0, 200, 255))
            # control bar
            def lit(key, base):
                if now < self.press_flash.get(key, 0):
                    return (255, 255, 255)
                return base
            self._fill(screen, range(0, 2), BAND, lit("min-", (210, 30, 30)))
            self._fill(screen, range(2, 4), BAND, lit("sec-", (150, 55, 20)))
            self._fill(screen, range(8, 10), BAND, lit("sec+", (30, 140, 60)))
            self._fill(screen, range(10, 12), BAND, lit("min+", (30, 210, 60)))
            if self.target > 0:                       # pulsing START
                p = int(120 + 100 * (0.5 + 0.5 * math.sin(now * 3)))
                self._fill(screen, range(4, 8), BAND,
                           (255, 255, 255) if now < self.press_flash.get("start", 0)
                           else (0, p, 0))
            else:
                self._fill(screen, range(4, 8), BAND, (40, 40, 40))
        else:  # run
            base = (255, 60, 40) if self.remaining <= 10 else (235, 235, 235)
            col = base
            if not self.running and int(now * 2) % 2 == 0:      # blink when paused
                col = tuple(c // 4 for c in base)
            self._digits(screen, col)
            for cx, cy in RUN_CENTER:                            # pause / resume
                screen.set(cx, cy, (255, 170, 0) if not self.running else (0, 120, 0))
            screen.set(*RUN_STOP, (200, 40, 40))                 # stop
            screen.set(*RUN_EXTEND, (0, 190, 90))                # +1 min
            screen.set(*RUN_RESTART, (0, 120, 220))              # restart


if __name__ == "__main__":
    run(Countdown)
