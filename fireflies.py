#!/usr/bin/env python3
"""Fireflies — 144 Kuramoto oscillators synchronizing on your desk.

Every pixel is a phase oscillator with its own drifting natural
frequency (like real fireflies). Each one tugs only on its eight
torus neighbours: d(theta) = omega + K * mean(sin(theta_j - theta_i)).
Out of disorder the coupling spins up traveling waves and spirals of
agreeing flashes, and then — consensus: all 144 fireflies blink in
unison, the whole board strobing through the rainbow as one organism.

Rendering maps phase to hue and the flash pulse (cos^3) to
brightness, so a synchronized board sweeps its colour in lockstep
while a chaotic one twinkles like static.

Pads (same five-corner layout):
  top-left     play/pause (green running, red paused)
  top-right    cycle coupling strength K: weak / medium / strong
  top-centre   chaos — scramble every phase, restart the march
  bottom-left  metronome — snap every firefly to phase 0
  bottom-right uniform frequencies — remove the natural drift
Any other pad pokes that firefly: its phase scrambles and the sync
wound heals before your eyes.

The order parameter r = |mean(e^i theta)| is logged live:
chaos -> waves -> nearly synced -> SYNCHRONIZED.

fireflies.json (auto-created, hot-reloads): coupling, omega, spread,
wrap.

  python fireflies.py           # emulator at http://127.0.0.1:7777
  python fireflies.py --hw      # real board over BLE
"""

from __future__ import annotations

import colorsys
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "fireflies.json"

DEFAULT = {
    "coupling": [0.8, 2.0, 4.0],   # K presets, cycled by pad
    "K_index": 2,
    "omega": 2.094,                 # base frequency (~3s flash cycle)
    "spread": 0.35,                 # +/- natural drift per firefly
    "wrap": True,                   # torus neighbours
    "saturation": 0.90,
}

N = W * H
TWO_PI = 2.0 * math.pi
MAX_STEP = 0.05                     # integration substeps


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _r(phases) -> float:
    """Kuramoto order parameter: 0 chaos, 1 consensus."""
    c = sum(math.cos(p) for p in phases)
    s = sum(math.sin(p) for p in phases)
    return math.hypot(c / len(phases), s / len(phases))


def _status(r: float) -> str:
    if r < 0.3:
        return "chaos"
    if r < 0.7:
        return "waves forming"
    if r < 0.95:
        return "nearly synced"
    return "SYNCHRONIZED"


class Fireflies(Game):
    fps = 20

    PAUSE_PAD = (0, 0)
    K_PAD = (11, 0)
    CHAOS_PAD = (6, 0)
    METRO_PAD = (0, 11)
    UNIFORM_PAD = (11, 11)

    def start(self):
        self._load()
        self.rnd = random.Random()
        self.phases = [0.0] * N
        self.omegas = [0.0] * N
        self.running = True
        self.next_check = 0.0
        self.next_rlog = 0.0
        self._roll_frequencies()
        self._chaos()
        log("fireflies — poke pads to scramble phases; chaos / metronome / "
            "coupling on the corner pads. watch for r")

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
    def K(self) -> float:
        ks = self.cfg.get("coupling") or DEFAULT["coupling"]
        i = min(int(self.cfg.get("K_index", 2)), len(ks) - 1)
        return float(ks[i])

    # -- the swarm --------------------------------------------------------------
    def _roll_frequencies(self) -> None:
        base = float(self.cfg.get("omega", 2.094))
        spread = float(self.cfg.get("spread", 0.35))
        uniform = getattr(self, "uniform_omegas", False)
        for i in range(N):
            self.omegas[i] = base if uniform else base + self.rnd.uniform(-spread, spread)

    def _chaos(self) -> None:
        for i in range(N):
            self.phases[i] = self.rnd.random() * TWO_PI
        log("chaos — every firefly scrambled")

    def _integrate(self, h: float) -> None:
        """One Euler substep of the Kuramoto flow with local coupling."""
        K = self.K
        wrap = bool(self.cfg.get("wrap", True))
        new = [0.0] * N
        for i in range(N):
            x, y = i % W, i // W
            acc = 0.0
            cnt = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if wrap:
                        nx, ny = nx % W, ny % H
                    elif not (0 <= nx < W and 0 <= ny < H):
                        continue
                    acc += math.sin(self.phases[ny * W + nx] - self.phases[i])
                    cnt += 1
            new[i] = self.phases[i] + h * (self.omegas[i] + K * acc / max(1, cnt))
        self.phases = [p % TWO_PI for p in new]

    def order(self) -> float:
        return _r(self.phases)

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == self.PAUSE_PAD:
            self.running = not self.running
            log("paused" if not self.running else "running")
        elif (x, y) == self.K_PAD:
            ks = self.cfg.get("coupling") or DEFAULT["coupling"]
            self.cfg["K_index"] = (int(self.cfg.get("K_index", 2)) + 1) % len(ks)
            log(f"coupling -> {self.K:g}")
        elif (x, y) == self.CHAOS_PAD:
            self._chaos()
        elif (x, y) == self.METRO_PAD:
            self.phases = [0.0] * N
            log("metronome — every firefly snapped to phase 0")
        elif (x, y) == self.UNIFORM_PAD:
            self.uniform_omegas = not getattr(self, "uniform_omegas", False)
            self._roll_frequencies()
            log("uniform frequencies" if self.uniform_omegas
                else "natural drift restored")
        else:
            i = y * W + x
            self.phases[i] = self.rnd.random() * TWO_PI
            log(f"poke at ({x},{y}) — phase scrambled, watching the wound heal")

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.running:
            while dt > 0:
                h = min(MAX_STEP, dt)
                self._integrate(h)
                dt -= h
        now = time.monotonic()
        if now >= self.next_rlog:
            self.next_rlog = now + 2.0
            r = self.order()
            log(f"r = {r:.3f} — {_status(r)}")
        if now >= self.next_check:
            self.next_check = now + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("fireflies.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        sat = float(self.cfg.get("saturation", 0.9))
        for i in range(N):
            theta = self.phases[i]
            flash = max(0.0, math.cos(theta)) ** 3      # the blink
            val = 0.05 + 0.95 * flash
            hue = theta / TWO_PI
            r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
            screen.set(i % W, i // W, (int(r * 255), int(g * 255), int(b * 255)))
        # HUD pads
        screen.set(*self.PAUSE_PAD, (0, 220, 60) if self.running else (230, 40, 40))
        screen.set(*self.K_PAD, (30, 90, 230))
        screen.set(*self.CHAOS_PAD, (240, 140, 20))
        screen.set(*self.METRO_PAD, (60, 60, 60))
        screen.set(*self.UNIFORM_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(Fireflies)