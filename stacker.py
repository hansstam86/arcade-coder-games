#!/usr/bin/env python3
"""Stacker — the tower-builder arcade gem, translated to 144 buttons.

A white row of blocks slides back and forth over your tower. Press any
pad to drop it: only the part overlapping the row below survives — the
overhang flashes red as it is sawn off, and the tower narrows. Climb
all the way to the top row (11 clean drops) and the whole tower
cascades rainbow: you beat the stacker.

Perfect drops (exact alignment) build a streak — three in a row and
your tower blossoms one cell wider toward centre, a mushroom cap that
becomes the new legal landing zone. The tower renders as a rainbow
gradient climbing from blue at the base to red at the summit, so
progress is one rising colour.

Any pad drops the row. After a miss (or a win), any pad starts a new
game. Speed rises with height but is capped for fair BLE latency —
the difficulty is in the width.

stacker.json (auto-created, hot-reloads): start_width, base_speed,
speed_per_row, max_speed, flash_seconds, bonus_streak.

  python stacker.py            # emulator at http://127.0.0.1:7777
  python stacker.py --hw       # real board over BLE
"""

from __future__ import annotations

import colorsys
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "stacker.json"

DEFAULT = {
    "start_width": 6,
    "base_speed": 2.0,          # columns per second
    "speed_per_row": 0.3,
    "max_speed": 5.0,
    "flash_seconds": 0.6,        # the beat after a drop lands
    "bonus_streak": 3,           # consecutive perfects -> tower blossoms
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _row_color(y: int, val: float = 1.0):
    """Rainbow climbing the tower: blue base -> red summit."""
    hue = (y / 11.0) * 0.66
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, val)
    return (int(r * 255), int(g * 255), int(b * 255))


class Stacker(Game):
    fps = 20

    def start(self):
        self._load()
        self.next_check = 0.0
        self.new_game()
        log("stacker — press any pad to drop the row; climb to the top")

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

    # -- game -------------------------------------------------------------------
    def new_game(self) -> None:
        w = int(self.cfg.get("start_width", 6))
        self.tower = {H - 1: ((W - w) // 2, w)}     # base row, centred
        self.top_y = H - 1
        self.w = w
        self.streak = 0
        self.perfects = 0
        self.state = "slide"
        self.anim_t = 0.0
        self.lost_cells: list[tuple[int, int]] = []
        self._new_row()

    def _speed(self) -> float:
        rows = H - 1 - self.top_y
        return min(float(self.cfg.get("base_speed", 2.0)) + float(self.cfg.get("speed_per_row", 0.3)) * rows,
                   float(self.cfg.get("max_speed", 5.0)))

    def _new_row(self) -> None:
        w = min(W, self.w)
        rows = H - 1 - self.top_y
        self.side = 1 if rows % 2 == 0 else -1
        self.pos = 0.0 if self.side > 0 else float(W - w)
        self.dir = self.side

    def _sliding_cells(self) -> range:
        x = int(self.pos + 0.5)
        return range(x, x + min(W, self.w))

    def drop(self) -> None:
        if self.state != "slide":
            return
        x = int(self.pos + 0.5)
        y = self.top_y - 1
        tx, tw = self.tower[self.top_y]
        w = min(W, self.w)
        ox = max(x, tx)
        ow = min(x + w, tx + tw) - ox
        if ow <= 0:
            self.state = "over"
            self.miss_row = (y, x, w)
            self.anim_t = 0.0
            log(f"missed at row {H - 1 - y} — tower stands {H - 1 - self.top_y} high, "
                f"{self.perfects} perfects")
            return
        perfect = ow == w
        self.tower[y] = (ox, ow)
        self.lost_cells = [(cx, y) for cx in range(x, x + w)
                           if not (tx <= cx < tx + tw)]
        self.top_y = y
        self.w = ow
        self.anim_t = float(self.cfg.get("flash_seconds", 0.6))
        if perfect:
            self.streak += 1
            self.perfects += 1
            bonus = int(self.cfg.get("bonus_streak", 3))
            if self.streak >= bonus and ow < W:
                side = 0 if ox > 0 and (ox + ow >= W or ox <= (W - ox - ow)) else 1
                #   ^ grow toward whichever side has more room
                if side == 0:
                    self.tower[y] = (ox - 1, ow + 1)
                else:
                    self.tower[y] = (ox, ow + 1)
                self.w = ow + 1
                self.streak = 0
                log(f"PERFECT x{bonus} — the tower blossoms to {self.w} wide")
            else:
                log(f"perfect! streak {self.streak}")
        else:
            self.streak = 0
        if y == 0:
            self.state = "win"
            self.anim_t = 0.0
            log(f"TOPPED OUT — {H - 1} rows, {self.perfects} perfects. "
                f"you beat the stacker")
        else:
            self.state = "flash"

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if self.state == "slide":
            self.drop()
        elif self.state in ("over", "win"):
            self.new_game()

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        if self.state == "slide":
            w = min(W, self.w)
            self.pos += self.dir * self._speed() * dt
            hi = float(W - w)
            if self.pos > hi:
                self.pos = hi - (self.pos - hi)
                self.dir = -1
            if self.pos < 0.0:
                self.pos = -self.pos
                self.dir = 1
        elif self.state == "flash":
            self.anim_t -= dt
            if self.anim_t <= 0:
                self._new_row()
                self.state = "slide"
        else:
            self.anim_t += dt
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("stacker.json reloaded")
            except OSError:
                pass

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        dim = self.state in ("over",)
        # the tower
        for y, (x, w) in self.tower.items():
            col = _row_color(y, 0.35 if dim else 1.0)
            for cx in range(x, x + w):
                screen.set(cx, y, col)
        if self.state == "slide":
            pulse = 0.75 + 0.25 * math.sin(now * 10)
            col = (int(255 * pulse),) * 3
            for cx in self._sliding_cells():
                screen.set(cx, self.top_y - 1, col)
        elif self.state == "flash":
            bright = max(0.4, self.anim_t / max(0.01, float(self.cfg.get("flash_seconds", 0.6))))
            if self.streak > 0 or not self.lost_cells:     # perfect: gold pulse
                col = (255, int(200 * bright), int(40 * bright))
                x, w = self.tower[self.top_y]
                for cx in range(x, x + w):
                    screen.set(cx, self.top_y, col)
            blink = 0.5 + 0.5 * math.sin(self.anim_t * 25)  # lost overhang: red
            for cx, cy in self.lost_cells:
                screen.set(cx, cy, (int(220 * blink), 20, 20))
        elif self.state == "over":
            y, x, w = self.miss_row
            blink = 0.5 + 0.5 * math.sin(self.anim_t * 6)
            for cx in range(x, x + w):
                screen.set(cx, y, (int(230 * blink), 30, 30))
        elif self.state == "win":
            for y, (x, w) in self.tower.items():            # rainbow cascade
                hue = (y / 11.0 + self.anim_t * 0.25) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
                col = (int(r * 255), int(g * 255), int(b * 255))
                for cx in range(x, x + w):
                    screen.set(cx, y, col)


if __name__ == "__main__":
    run(Stacker)