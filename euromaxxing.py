#!/usr/bin/env python3
"""Euromaxxing — the Arcade Coder carries the mark.

Three modes, following the euromaxxing design system (deep flag-blue
ground, flag-gold as the one loud colour, gold spent carefully):

  mark   giant gold glyphs on reflex blue cranked for LEDs: a chunky
         hand-drawn "EU" alternating with a pixel "€", big enough to
         read across the room, breathing gently with a short blue
         blink between glyphs
  facts  the euro-facts ticker (the same euro-facts.json the desktop
         Touch Bar ticker reads), scrolling in gold on the lifted
         system ground
  spin   12 stars orbit as a comet: bright gold leader, fading trail —
         the euromaxxing loading spinner

Press any pad to cycle modes. euromaxxing.json (auto-created,
hot-reloads) carries the palette, speeds and facts path.

  python euromaxxing.py            # emulator at http://127.0.0.1:7777
  python euromaxxing.py --hw       # real board over BLE
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "euromaxxing.json"

DEFAULT_FACTS_PATH = "/home/hans/.config/omarchy/themes/euromaxxing/data/euro-facts.json"

DEFAULT = {
    "modes": ["mark", "facts", "spin"],
    "flag_blue": (0, 105, 255),       # flag reflex blue, cranked to 11 for LEDs
    "ground_blue": (18, 70, 160),      # system ground, lifted so the LEDs actually glow
    "gold": (255, 204, 0),            # flag gold, #ffcc00
    "facts_path": DEFAULT_FACTS_PATH,
    "scroll_speed": 7.0,              # px/s for the facts ticker
    "glyph_seconds": 6.0,             # EU <-> EUR alternation in mark mode
    "spin_speed": 1.2,                # rad/s for the orbiting comet
}

# hand-drawn 12x12 glyphs for mark mode — designed for the grid, not scaled
GLYPHS = (
    ("EU", (
        "............",
        "............",
        ".#####.##.##",
        ".#####.##.##",
        ".##....##.##",
        ".####..##.##",
        ".####..##.##",
        ".##....##.##",
        ".#####.#####",
        ".#####.#####",
        "............",
        "............",
    )),
    ("EUR", (
        "............",
        "....#####...",
        "..##.....##.",
        ".##.......##",
        ".###########",
        ".###########",
        ".##.......##",
        ".###########",
        ".###########",
        ".##.......##",
        "..##.....##.",
        "....#####...",
    )),
)

FALLBACK_FACTS = (
    "12 STARS 12 COLUMNS",
    "THE GOOD LIFE OPTIMIZED",
    "REFLEX BLUE AND FLAG GOLD",
)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _scale(rgb, f: float) -> tuple[int, int, int]:
    return (int(rgb[0] * f), int(rgb[1] * f), int(rgb[2] * f))


class Euromaxxing(Game):
    fps = 20

    def start(self):
        self._load()
        self.mode_i = 0
        self.offset = -12.0
        self.next_check = 0.0
        self.glyph_i = 0
        self.glyph_t = 0.0
        self.flash_until = 0.0
        self._load_facts()
        self._build_columns()
        log("euromaxxing — mark (big EU / EUR glyphs), facts (the euro "
            "ticker), spin (orbiting comet); press any pad to change mode")

    # -- config --------------------------------------------------------------
    def _load(self):
        self.cfg = json.loads(json.dumps(DEFAULT))     # deep copy
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

    def _load_facts(self):
        headlines = FALLBACK_FACTS
        try:
            facts = json.loads(Path(self.cfg["facts_path"]).read_text())
            heads = [str(f.get("headline", "")).strip() for f in facts]
            heads = [h for h in heads if h]
            if heads:
                headlines = heads
        except Exception:
            pass
        self.facts_text = " * ".join(headlines) + " * "
        try:
            self.facts_mtime = Path(self.cfg["facts_path"]).stat().st_mtime
        except OSError:
            self.facts_mtime = 0.0

    def _build_columns(self):
        self.columns = render_columns(self.facts_text)
        self.total = len(self.columns) - 1

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        modes = self.cfg.get("modes") or DEFAULT["modes"]
        self.mode_i = (self.mode_i + 1) % len(modes)
        log(f"mode -> {modes[self.mode_i]}")

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        mode = (self.cfg.get("modes") or DEFAULT["modes"])[self.mode_i]
        if mode == "mark":
            self.glyph_t += dt
            if self.glyph_t >= float(self.cfg.get("glyph_seconds", 6.0)):
                self.glyph_t = 0.0
                self.glyph_i = (self.glyph_i + 1) % len(GLYPHS)
                self.flash_until = time.monotonic() + 0.15   # blue-only blink
        if mode == "facts":
            self.offset += float(self.cfg.get("scroll_speed", 7.0)) * dt
            if self.offset >= self.total + 12 + 4:
                self.offset = -12.0
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("euromaxxing.json reloaded")
            except OSError:
                pass
            try:
                p = Path(self.cfg["facts_path"])
                if p.stat().st_mtime != self.facts_mtime:
                    self._load_facts()
                    self._build_columns()
                    self.offset = -12.0
                    log("euro-facts reloaded")
            except OSError:
                pass

    def draw_mark(self, screen, now: float) -> None:
        screen.clear(tuple(self.cfg["flag_blue"]))
        if now < self.flash_until:              # short blue blink between glyphs
            return
        b = 0.9 + 0.1 * math.sin(now * 1.4)     # gentle breathing on the gold
        gold = _scale(tuple(self.cfg["gold"]), b)
        _name, rows = GLYPHS[self.glyph_i]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    screen.set(x, y, gold)

    def draw_facts(self, screen, now: float) -> None:
        screen.clear(tuple(self.cfg["ground_blue"]))
        gold = tuple(self.cfg["gold"])
        base = int(self.offset)
        for sx in range(12):
            ci = base + sx
            if 0 <= ci <= self.total:
                col = self.columns[ci]
                for r in range(5):
                    if col[r]:
                        screen.set(sx, 3 + r, gold)

    def draw_spin(self, screen, now: float) -> None:
        screen.clear(tuple(self.cfg["ground_blue"]))
        gold = tuple(self.cfg["gold"])
        a0 = now * float(self.cfg.get("spin_speed", 1.2))
        for k in range(12):                       # leader + fading trail
            a = a0 + k * math.pi / 6
            x = int(5.5 + 4.5 * math.cos(a) + 0.5)
            y = int(5.5 + 4.5 * math.sin(a) + 0.5)
            screen.set(x, y, _scale(gold, 1.0 if k == 0 else max(0.15, 0.8 - k * 0.07)))
        screen.set(5, 5, _scale(gold, 0.25 + 0.2 * math.sin(now * 3)))
        screen.set(6, 6, _scale(gold, 0.25 + 0.2 * math.sin(now * 3)))

    def draw(self, screen):
        mode = (self.cfg.get("modes") or DEFAULT["modes"])[self.mode_i]
        now = time.monotonic()
        if mode == "mark":
            self.draw_mark(screen, now)
        elif mode == "spin":
            self.draw_spin(screen, now)
        else:
            self.draw_facts(screen, now)


if __name__ == "__main__":
    run(Euromaxxing)