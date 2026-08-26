#!/usr/bin/env python3
"""Scrolling text marquee for the Arcade Coder.

Renders a message in a 3x5 pixel font and scrolls it across the 12x12 board.
Message, colour (solid or rainbow), speed, and background live in marquee.json
and hot-reload while it runs.

  python marquee.py           # emulator
  (on the board: it's an ArcadeOS app; also usable standalone)
"""

from __future__ import annotations

import colorsys
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "marquee.json"

DEFAULT = {
    "text": "HELLO ARCADE CODER  ",
    "color": [0, 200, 255],
    "rainbow": True,
    "speed": 7.0,          # pixels per second
    "background": [0, 0, 6],
    "y": 3,                # top row of the 5-tall text (centred-ish)
    "mirror": False,       # set true if using it as a camera background (mirrored webcam)
}

# 3x5 proportional-ish font; each glyph is 5 rows of a fixed-width bit string.
FONT = {
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["011", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"],
    "F": ["111", "100", "110", "100", "100"],
    "G": ["011", "100", "101", "101", "011"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "010"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["010", "101", "101", "101", "010"],
    "P": ["110", "101", "110", "100", "100"],
    "Q": ["010", "101", "101", "110", "011"],
    "R": ["110", "101", "110", "101", "101"],
    "S": ["011", "100", "010", "001", "110"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "100", "100"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    " ": ["00", "00", "00", "00", "00"],
    ".": ["000", "000", "000", "000", "010"],
    ",": ["000", "000", "000", "010", "100"],
    "!": ["010", "010", "010", "000", "010"],
    "?": ["111", "001", "011", "000", "010"],
    ":": ["000", "010", "000", "010", "000"],
    "-": ["000", "000", "111", "000", "000"],
    "+": ["000", "010", "111", "010", "000"],
    "'": ["010", "010", "000", "000", "000"],
    "/": ["001", "001", "010", "100", "100"],
    "<": ["001", "010", "100", "010", "001"],
    ">": ["100", "010", "001", "010", "100"],
    "*": ["000", "101", "010", "101", "000"],
    "=": ["000", "111", "000", "111", "000"],
    "(": ["010", "100", "100", "100", "010"],
    ")": ["010", "001", "001", "001", "010"],
    "#": ["101", "111", "101", "111", "101"],
    "%": ["101", "001", "010", "100", "101"],
    "@": ["111", "101", "101", "100", "111"],
    "$": ["011", "110", "011", "110", "010"],
    "&": ["110", "110", "111", "101", "011"],
    '"': ["101", "101", "000", "000", "000"],
    ";": ["000", "010", "000", "010", "100"],
}
UNKNOWN = ["111", "101", "101", "101", "111"]  # box for missing glyphs


def render_columns(text: str) -> list[list[int]]:
    """Return the message as a list of columns; each column is 5 bits (top..bottom)."""
    cols: list[list[int]] = []
    for ch in text.upper():
        glyph = FONT.get(ch, UNKNOWN)
        width = len(glyph[0])
        for c in range(width):
            cols.append([1 if glyph[r][c] == "1" else 0 for r in range(5)])
        cols.append([0, 0, 0, 0, 0])  # 1px spacing between glyphs
    return cols


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Marquee(Game):
    fps = 20

    def start(self):
        self._load()
        self.offset = -12.0            # start off the right edge
        self.last = time.monotonic()
        self.next_check = 0.0
        log(f"marquee: {self.cfg['text']!r}")

    def _load(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
            self.mtime = CONFIG_PATH.stat().st_mtime
        else:
            CONFIG_PATH.write_text(json.dumps(DEFAULT, indent=2) + "\n")
            self.mtime = CONFIG_PATH.stat().st_mtime
        self.columns = render_columns(self.cfg["text"])
        self.total = max(1, len(self.columns))

    def set_text(self, text: str):
        self.cfg["text"] = text
        self.columns = render_columns(text)
        self.total = max(1, len(self.columns))
        self.offset = -12.0

    def update(self, dt):
        now = time.monotonic()
        real_dt = now - self.last
        self.last = now
        self.offset += self.cfg["speed"] * real_dt
        # loop with a gap of 12 (one board width) after the message
        if self.offset >= self.total + 12:
            self.offset = -12.0
        if now >= self.next_check:
            self.next_check = now + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log(f"marquee reloaded: {self.cfg['text']!r}")
            except OSError:
                pass

    def draw(self, screen):
        screen.clear(tuple(self.cfg["background"]))
        y0 = int(self.cfg.get("y", 3))
        base = int(self.offset)
        for sx in range(12):
            ci = base + sx
            if 0 <= ci < self.total:
                col = self.columns[ci]
                for r in range(5):
                    if col[r]:
                        if self.cfg.get("rainbow"):
                            hue = ((ci) / 18.0 + time.monotonic() * 0.1) % 1.0
                            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                            color = (int(rr * 255), int(gg * 255), int(bb * 255))
                        else:
                            color = tuple(self.cfg["color"])
                        screen.set(sx, y0 + r, color)
        if self.cfg.get("mirror", False):            # flip for a mirrored webcam
            p = screen.px
            screen.px = [p[y * 12 + (11 - x)] for y in range(12) for x in range(12)]


if __name__ == "__main__":
    run(Marquee)
