#!/usr/bin/env python3
"""Desk Tamagotchi — a little creature that lives on your habits.

A pixel pet that bobs, blinks and changes mood based on how you treat it and
what your Mac is doing:

  * tap the pet   -> play with it (happiness up, shows hearts)
  * tap the food  -> feed it (fullness up, bottom-left apple)
  * on a call     -> it naps while your mic is live
  * night         -> it sleeps
  * neglect       -> happiness / fullness decay in real time, even while the
                     app is closed, so it's hungrier when you come back

Three gauges on the bottom row show happiness, energy and fullness. State
persists to tamagotchi.json.

  python tamagotchi.py        # emulator (no mic sensing)
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "tamagotchi.json"
MIC_HELPER = BASE / "bin" / "micstate"
W = H = 12

MOOD_COLOR = {
    "happy": (0, 220, 90), "content": (0, 200, 200), "sad": (70, 100, 220),
    "hungry": (255, 150, 0), "sleep": (150, 90, 210),
}
# body blob (6 wide x 7 tall, rounded corners), relative to a top-left of (3,3)
_BODY = [(x, y) for y in range(0, 7) for x in range(0, 6)
         if (x, y) not in ((0, 0), (5, 0), (0, 6), (5, 6))]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Tamagotchi(Game):
    fps = 12

    def start(self):
        now = time.time()
        self.happiness = 80.0
        self.energy = 80.0
        self.fullness = 80.0
        self.born = now
        if CONFIG_PATH.exists():
            try:
                d = json.loads(CONFIG_PATH.read_text())
                self.happiness = float(d.get("happiness", 80))
                self.energy = float(d.get("energy", 80))
                self.fullness = float(d.get("fullness", 80))
                self.born = float(d.get("born", now))
                self._decay(min(3 * 86400, now - float(d.get("last", now))))  # offline
            except Exception:
                pass
        self.mic_on = False
        self.heart_until = 0.0
        self.eat_until = 0.0
        self.blink_until = 0.0
        self.next_blink = time.monotonic() + random.uniform(2, 5)
        self.busy = False
        self.last = time.monotonic()
        self.last_save = 0.0
        self._stop = False
        self._poll_mic()
        threading.Thread(target=self._mic_loop, daemon=True).start()
        log(f"tamagotchi awake — happiness {self.happiness:.0f}, "
            f"fullness {self.fullness:.0f}")

    def stop(self):
        self._stop = True
        self._save()

    # -- signals -------------------------------------------------------------
    def _poll_mic(self):
        try:
            if MIC_HELPER.exists():
                out = subprocess.run([str(MIC_HELPER)], capture_output=True,
                                     text=True, timeout=2)
                self.mic_on = out.stdout.strip() == "1"
        except Exception:
            self.mic_on = False

    def _mic_loop(self):
        while not self._stop:
            self._poll_mic()
            time.sleep(3.0)

    def _sleeping(self) -> bool:
        hour = time.localtime().tm_hour
        night = hour >= 22 or hour < 7
        return self.mic_on or night or self.energy < 8

    # -- model ---------------------------------------------------------------
    def _decay(self, secs: float):
        secs = max(0.0, secs)
        sleeping = self._sleeping()
        self.fullness = max(0.0, self.fullness - secs * (100 / (5 * 3600)))
        hp = 100 / (10 * 3600) * (2.0 if self.fullness < 20 else 1.0)
        self.happiness = max(0.0, self.happiness - secs * hp)
        if sleeping:
            self.energy = min(100.0, self.energy + secs * (100 / (2.5 * 3600)))
            self.happiness = min(100.0, self.happiness + secs * (100 / (24 * 3600)))
        else:
            self.energy = max(0.0, self.energy - secs * (100 / (8 * 3600)))

    def _save(self):
        try:
            CONFIG_PATH.write_text(json.dumps({
                "happiness": round(self.happiness, 1), "energy": round(self.energy, 1),
                "fullness": round(self.fullness, 1), "born": self.born,
                "last": time.time()}) + "\n")
        except Exception:
            pass

    def _mood(self) -> str:
        if self._sleeping():
            return "sleep"
        if self.fullness < 25:
            return "hungry"
        if self.happiness < 30:
            return "sad"
        if self.happiness >= 70 and self.fullness >= 50:
            return "happy"
        return "content"

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        now = time.monotonic()
        if x <= 2 and y >= 9:                        # feed (bottom-left apple)
            self.fullness = min(100.0, self.fullness + 45)
            self.happiness = min(100.0, self.happiness + 6)
            self.eat_until = now + 1.4
            log(f"fed — fullness {self.fullness:.0f}")
            return
        self.happiness = min(100.0, self.happiness + 22)   # play / pet
        self.energy = max(0.0, self.energy - 4)
        self.heart_until = now + 1.4

    def update(self, dt):
        now = time.monotonic()
        self._decay(now - self.last)
        self.last = now
        if time.time() - self.last_save > 5:
            self.last_save = time.time()
            self._save()

    # -- render --------------------------------------------------------------
    def _set(self, screen, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            screen.set(x, y, c)

    def draw(self, screen):
        now = time.monotonic()
        mood = self._mood()
        screen.clear((6, 6, 12))
        base = MOOD_COLOR[mood]
        bright = 0.5 + 0.5 * self.happiness / 100
        body = tuple(int(v * bright) for v in base)
        bob = 0 if mood in ("sleep", "sad") else (1 if int(now * 2) % 2 else 0)
        ox, oy = 3, 3 - bob

        for bx, by in _BODY:                         # body blob
            self._set(screen, ox + bx, oy + by, body)

        # eyes
        if now >= self.next_blink:
            self.blink_until = now + 0.13
            self.next_blink = now + random.uniform(2, 5)
        blinking = now < self.blink_until
        ex1, ex2, ey = ox + 1, ox + 4, oy + 2
        if mood == "sleep" or blinking:              # closed eyes (dashes)
            self._set(screen, ex1, ey, (10, 10, 20)); self._set(screen, ex2, ey, (10, 10, 20))
        else:
            self._set(screen, ex1, ey, (15, 15, 25)); self._set(screen, ex2, ey, (15, 15, 25))
            if mood in ("happy", "content"):         # a little sparkle
                self._set(screen, ex1, ey, (240, 240, 255)); self._set(screen, ex2, ey, (240, 240, 255))

        # mouth
        my = oy + 4
        if self.eat_until > now:                     # chewing (open mouth)
            self._set(screen, ox + 2, my, (60, 20, 20)); self._set(screen, ox + 3, my, (60, 20, 20))
        elif mood in ("happy",):                     # smile
            self._set(screen, ox + 1, my, (20, 10, 10)); self._set(screen, ox + 2, my + 1, (20, 10, 10))
            self._set(screen, ox + 3, my + 1, (20, 10, 10)); self._set(screen, ox + 4, my, (20, 10, 10))
        elif mood in ("sad", "hungry"):              # frown
            self._set(screen, ox + 1, my + 1, (20, 10, 10)); self._set(screen, ox + 2, my, (20, 10, 10))
            self._set(screen, ox + 3, my, (20, 10, 10)); self._set(screen, ox + 4, my + 1, (20, 10, 10))
        elif mood != "sleep":                        # neutral line
            for dx in range(1, 5):
                self._set(screen, ox + dx, my, (20, 10, 10))

        # effects
        if mood == "sleep":                          # rising Z's
            zt = (now * 1.5) % 3
            self._set(screen, ox + 6, oy - int(zt), (200, 200, 255))
        if self.heart_until > now:                   # hearts when played with
            for i in range(2):
                hy = oy - 1 - int(((now * 3) + i) % 3)
                self._set(screen, ox + 1 + i * 3, hy, (255, 60, 150))
        if mood == "hungry" and self.eat_until <= now:   # hunger sweat drop
            self._set(screen, ox + 6, oy + 1, (80, 160, 255))

        # food button (bottom-left apple)
        self._set(screen, 0, 11, (0, 180, 0)); self._set(screen, 1, 11, (220, 30, 30))
        self._set(screen, 1, 10, (0, 180, 0))

        # gauges on the bottom row: happiness | energy | fullness
        for i, (val, col) in enumerate((
                (self.happiness, (0, 220, 90)), (self.energy, (240, 220, 0)),
                (self.fullness, (255, 150, 0)))):
            x0 = 3 + i * 3
            lit = int(round(val / 100 * 2))
            for k in range(2):
                self._set(screen, x0 + k, 11,
                          col if k < lit else tuple(c // 6 for c in col))


if __name__ == "__main__":
    run(Tamagotchi)
