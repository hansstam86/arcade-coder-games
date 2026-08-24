#!/usr/bin/env python3
"""Countdown timer — set the time on the board, then let it run down.

Two modes. In SET mode four corner buttons adjust the target time and a green
button in the middle starts it; in RUN mode the time ticks down and the middle
button pauses/resumes. At zero the board flashes red and an alarm sound repeats
until you press to acknowledge.

Layout (interior corners, clear of the global edge pads):
  SET:  top-left (-1 min)   top-right (+1 min)
        bottom-left (-15 s) bottom-right (+15 s)
        centre green 2x2 = START
  RUN:  centre 2x2 = pause / resume,  top-left = stop (back to SET)
  ALARM: press anywhere = acknowledge

Config in countdown.json (auto-created): target (last time in seconds),
  step_sec (seconds button step), alarm_sound (aiff path or "").

  python countdown.py         # emulator
"""

from __future__ import annotations

import json
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
    "step_sec": 15,
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

# buttons (interior corners) and the centre pad
MIN_DOWN = (1, 1)
MIN_UP = (10, 1)
SEC_DOWN = (1, 10)
SEC_UP = (10, 10)
CENTER = {(5, 5), (6, 5), (5, 6), (6, 6)}
STOP_BTN = (1, 1)   # in RUN mode, top-left stops back to SET

MINUTE_POS = [(2, 0), (7, 0)]   # two digit blocks, top
SECOND_POS = [(2, 7), (7, 7)]   # two digit blocks, bottom


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
        self.step = max(1, int(self.cfg.get("step_sec", 15)))
        self.mode = "set"           # set | run | alarm
        self.running = False
        self.remaining = float(self.target)
        self.busy = False           # true while running/alarming
        self.alarm_on = False
        self.last = time.monotonic()
        log(f"countdown ready — {self.target // 60:02d}:{self.target % 60:02d}, "
            "set the time and press the centre to start")

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

    def stop(self) -> None:
        """Called by ArcadeOS when leaving the app — silence any alarm."""
        self._stop_alarm()

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if self.mode == "alarm":
            self._to_set()
            return
        if self.mode == "run":
            if (x, y) == STOP_BTN:
                self._to_set()
                return
            if (x, y) in CENTER:
                self.running = not self.running
            return
        # set mode
        if (x, y) == MIN_UP:
            self._adjust(60)
        elif (x, y) == MIN_DOWN:
            self._adjust(-60)
        elif (x, y) == SEC_UP:
            self._adjust(self.step)
        elif (x, y) == SEC_DOWN:
            self._adjust(-self.step)
        elif (x, y) in CENTER and self.target > 0:
            self.mode = "run"
            self.running = True
            self.remaining = float(self.target)
            self.last = time.monotonic()
            log(f"countdown start — {self.target // 60:02d}:{self.target % 60:02d}")

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
    def _time_digits(self, screen, col) -> None:
        secs = max(0, int(self.remaining + 0.99))
        mm, ss = min(99, secs // 60), secs % 60
        text = f"{mm:02d}{ss:02d}"
        for ch, (ox, oy) in zip(text, MINUTE_POS + SECOND_POS):
            for dy, row in enumerate(FONT[ch]):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        screen.set(ox + dx, oy + dy, col)

    def draw(self, screen):
        now = time.monotonic()
        if self.mode == "alarm":
            on = int(now * 5) % 2 == 0
            screen.clear((120, 0, 0) if on else (10, 0, 0))
            if on:
                self._time_digits(screen, (255, 255, 255))
            return

        screen.clear((0, 0, 0))
        if self.mode == "set":
            col = (0, 200, 255)
            self._time_digits(screen, col)
            # adjust buttons
            screen.set(*MIN_UP, (0, 200, 90))
            screen.set(*MIN_DOWN, (200, 40, 40))
            screen.set(*SEC_UP, (0, 140, 70))
            screen.set(*SEC_DOWN, (150, 30, 30))
            # start (green 2x2), pulsing, only when time > 0
            if self.target > 0:
                p = int(120 + 100 * (0.5 + 0.5 * __import__("math").sin(now * 3)))
                for cx, cy in CENTER:
                    screen.set(cx, cy, (0, p, 0))
        else:  # run
            secs = self.remaining
            base = (255, 60, 40) if secs <= 10 else (235, 235, 235)
            col = base
            if not self.running and int(now * 2) % 2 == 0:      # blink when paused
                col = tuple(c // 4 for c in base)
            self._time_digits(screen, col)
            # centre = pause/resume
            cc = (255, 170, 0) if not self.running else (0, 120, 0)
            for cx, cy in CENTER:
                screen.set(cx, cy, cc)
            screen.set(*STOP_BTN, (120, 20, 20))                # stop back to set


if __name__ == "__main__":
    run(Countdown)
