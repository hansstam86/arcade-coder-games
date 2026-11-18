#!/usr/bin/env python3
"""Grover Search — the quantum algorithm you play against the clock.

The board hides a target among its 144 pixels. Your state is the
honest uniform superposition (amplitude 1/12 everywhere), and each
iteration applies the real Grover operator: oracle phase-flip on the
target, then diffusion (reflect about the mean). Success probability at
the target follows sin^2((2k+1)*asin(1/12)) — it peaks near certainty
at k = 9 iterations (the theoretical pi/4 * sqrt(N)), collapses back
to almost zero around k = 18, and breathes forever after.

Rendering maps probability to brightness and the SIGN of the
amplitude to hue: gold where amplitudes are positive, blue where the
over-rotation has driven them negative. You literally watch the wave
invert.

Pads:
  top-left     auto-run on/off (iterate at the current speed)
  top-right    cycle speed: 1 / 2 / 5 iterations per second
  top-centre   +1 iteration, the manual crank (works while paused)
  bottom-left  restart the round: fresh superposition, same target
  bottom-right new round: a new secret target
  left column  progress tick for the iteration count; the green marker
               at y=10 is the theoretical optimum (9 iterations)
Any other pad is a projective MEASUREMENT at that pixel: it wins if
and only if that pixel is the target AND the sample succeeds with
probability |amplitude|^2 — measure too early and even the right
pixel can fail you. Miss, and the target reveals itself briefly.

grover.json (auto-created, hot-reloads): speeds, reveal_seconds.

  python grover.py           # emulator at http://127.0.0.1:7777
  python grover.py --hw      # real board over BLE
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "grover.json"

DEFAULT = {
    "speeds": [1, 2, 5],      # auto-run iterations per second
    "speed_index": 1,
    "reveal_seconds": 2.2,     # win/miss reveal before the next round
}

N = W * H
A0 = 1.0 / math.sqrt(N)       # the uniform superposition
OPTIMUM_K = 9                 # round(pi/4 * sqrt(144)) — near-certain here

GOLD = (255, 200, 60)         # positive amplitudes
BLUE = (70, 130, 255)         # negative amplitudes (over-rotation)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Grover(Game):
    fps = 20

    PAUSE_PAD = (0, 0)
    SPEED_PAD = (11, 0)
    STEP_PAD = (6, 0)
    RESTART_PAD = (0, 11)
    NEW_PAD = (11, 11)
    OPT_TICK_Y = 1 + OPTIMUM_K          # left-column y for the optimum marker

    def start(self):
        self._load()
        self.acc = 0.0
        self.running = False
        self.next_check = 0.0
        self.wins = 0
        self.misses = 0
        self.new_round()
        log("grover search — iterate (top-centre), auto-run (top-left), "
            "speed (top-right); press a pixel to measure. optimum ~9")

    # -- config --------------------------------------------------------------
    def _load(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        else:
            CONFIG_PATH.write_text(json.dumps(DEFAULT, indent=2) + "\n")
        try:
            self.mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            self.mtime = 0.0

    @property
    def gps(self) -> float:
        speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
        i = min(int(self.cfg.get("speed_index", 1)), len(speeds) - 1)
        return float(speeds[i])

    # -- round / algorithm ------------------------------------------------------
    def new_round(self) -> None:
        self.target = random.randrange(N)
        self.amps = [A0] * N
        self.iters = 0
        self.state = "search"
        log("new round — target hidden among 144")

    def restart_round(self) -> None:
        self.amps = [A0] * N
        self.iters = 0
        self.state = "search"
        log("round restarted — fresh superposition, same target")

    def iterate(self) -> None:
        if self.state != "search":
            return
        a = self.amps
        t = self.target
        a[t] = -a[t]                                   # oracle reflection
        m = 2.0 * sum(a) / N                           # diffusion: reflect
        for i in range(N):                              # about the mean
            a[i] = m - a[i]
        self.iters += 1
        p = a[t] * a[t]
        log(f"iteration {self.iters} — p(target) {p:.4f}")

    def measure(self, x: int, y: int) -> None:
        if self.state != "search":
            return
        i = y * W + x
        self.last_measured = i
        p = self.amps[i] * self.amps[i]
        if i == self.target and random.random() < p:
            self.state = "win"
            self.reveal_at = time.monotonic()
            self.wins += 1
            log(f"FOUND at ({x},{y}) in {self.iters} iterations "
                f"(optimum ~{OPTIMUM_K}) — wins {self.wins}")
        else:
            self.state = "miss"
            self.reveal_at = time.monotonic()
            self.misses += 1
            tx, ty = self.target % W, self.target // W
            log(f"miss — measured ({x},{y}), the target was at ({tx},{ty}) "
                f"at {self.iters} iterations")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == self.PAUSE_PAD:
            self.running = not self.running
            log("auto-run" if self.running else "paused")
        elif (x, y) == self.SPEED_PAD:
            speeds = self.cfg.get("speeds") or DEFAULT["speeds"]
            self.cfg["speed_index"] = (int(self.cfg.get("speed_index", 1)) + 1) % len(speeds)
            log(f"speed -> {self.gps:g} iterations/s")
        elif (x, y) == self.STEP_PAD:
            self.iterate()
        elif (x, y) == self.RESTART_PAD:
            self.restart_round()
        elif (x, y) == self.NEW_PAD:
            self.new_round()
        else:
            self.measure(x, y)

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.state == "search" and self.running:
            self.acc += dt
            interval = 1.0 / max(0.1, self.gps)
            while self.acc >= interval:
                self.acc -= interval
                self.iterate()
        elif self.state in ("win", "miss"):
            if time.monotonic() - self.reveal_at >= float(self.cfg.get("reveal_seconds", 2.2)):
                self.new_round()
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("grover.json reloaded")
            except OSError:
                pass

    def _draw_field(self, screen, now: float) -> None:
        for i in range(N):
            a = self.amps[i]
            p = a * a
            if p < 1e-6:
                continue
            val = min(1.0, math.sqrt(p) * 1.1)
            base = GOLD if a >= 0 else BLUE
            screen.set(i % W, i // W, tuple(int(c * val) for c in base))

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        if self.state == "search":
            self._draw_field(screen, now)
            # progress tick + optimum marker on the left column
            screen.set(0, self.OPT_TICK_Y, (0, 140, 60))
            if self.iters:
                tick_y = 1 + (self.iters - 1) % 11
                hot = tick_y == self.OPT_TICK_Y
                screen.set(0, tick_y, (0, 255, 120) if hot else (170, 170, 170))
        elif self.state == "win":
            tx, ty = self.target % W, self.target // W
            pulse = 0.7 + 0.3 * math.sin(now * 8)
            screen.set(tx, ty, (0, int(255 * pulse), int(120 * pulse)))
        else:  # miss: show what you measured and where the target was
            mx, my = self.last_measured % W, self.last_measured // W
            blink = 0.5 + 0.5 * math.sin(now * 10)
            screen.set(mx, my, (int(200 * blink), 20, 20))
            tx, ty = self.target % W, self.target // W
            screen.set(tx, ty, (255, 200, 60))
        # HUD pads
        screen.set(*self.PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*self.SPEED_PAD, (30, 90, 230))
        screen.set(*self.STEP_PAD, (240, 140, 20))
        screen.set(*self.RESTART_PAD, (60, 60, 60))
        screen.set(*self.NEW_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(Grover)