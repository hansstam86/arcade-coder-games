#!/usr/bin/env python3
"""Studio Sign — a TV broadcast cue sign for the Arcade Coder.

The board becomes the gallery sign: ON AIR in pulsing red, APPLAUSE in
flashing gold (auto-returns to the previous cue), COMMERCIAL BREAK,
BACK TO THE STUDIO, STAND BY, QUIET PLEASE, REHEARSAL, REPLAY and
BREAKING NEWS.

Press the right half of the board to advance to the next cue, the left
half to go back. The left column shows your position in the cue deck.

The cue deck lives in studio.json (auto-created) and hot-reloads while
it runs — re-word cues, recolour them, reorder the deck, add your own.

  python studio.py             # emulator at http://127.0.0.1:7777
  python studio.py --hw        # real board over BLE (start from a freshly
                                # booted, idle board — see repo README)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "studio.json"

DEFAULT = {
    "start_index": 0,
    "mirror": False,   # flip horizontally so text reads right in a mirrored webcam
    "cues": [
        {"text": "ON AIR", "style": "tally", "color": [255, 255, 255], "bg": [200, 8, 8]},
        {"text": "STAND BY", "style": "scroll", "color": [255, 170, 40], "bg": [30, 12, 0], "speed": 6.0},
        {"text": "APPLAUSE", "style": "flash", "color": [255, 210, 40], "bg": [60, 40, 0], "speed": 6.0, "auto_return": 12.0},
        {"text": "COMMERCIAL BREAK", "style": "scroll", "color": [255, 255, 255], "bg": [0, 30, 110], "speed": 7.0},
        {"text": "BACK TO THE STUDIO", "style": "scroll", "color": [40, 255, 220], "bg": [0, 22, 22], "speed": 7.0},
        {"text": "QUIET PLEASE", "style": "pulse", "color": [130, 160, 255], "bg": [3, 5, 12], "speed": 3.5},
        {"text": "REHEARSAL", "style": "scroll", "color": [255, 90, 255], "bg": [24, 0, 26], "speed": 6.0},
        {"text": "REPLAY", "style": "scroll", "color": [70, 255, 110], "bg": [0, 26, 10], "speed": 8.0},
        {"text": "BREAKING NEWS", "style": "flash", "color": [255, 255, 255], "bg": [150, 0, 0], "speed": 7.0},
    ],
}

GAP = 4      # blank columns between scroll passes
TEXT_Y = 3   # top row of the 5-tall text band


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _stack_lines(text: str) -> list[str] | None:
    """Split text into words that fit 12px-wide lines of 3x5 font (max 2)."""
    words = text.upper().split()
    if not words or len(words) > 2:
        return None
    for w in words:
        if len(render_columns(w)) - 1 > W:
            return None
    return words


class Studio(Game):
    fps = 20

    def start(self):
        self.return_to: int | None = None
        self.return_at = 0.0
        self.next_check = 0.0
        self._load()
        self.i = max(0, min(int(self.cfg.get("start_index", 0)), len(self.cfg["cues"]) - 1))
        self._enter()
        self.busy = True                 # a studio sign must stay up; never auto-ambient
        cue = self.cue()["text"]
        log(f"studio sign ready — cue {self.i}: {cue!r} (right half = next, left half = back)")

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
        self.cfg["cues"] = [c for c in self.cfg["cues"] if str(c.get("text", "")).strip()]
        if not self.cfg["cues"]:
            self.cfg["cues"] = json.loads(json.dumps(DEFAULT["cues"]))
        try:
            self.mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            self.mtime = 0.0

    def cue(self) -> dict:
        return self.cfg["cues"][self.i]

    def _enter(self):
        """Set up state for the current cue (call after self.i changes)."""
        cue = self.cue()
        self._cols = render_columns(str(cue["text"]).upper())
        self._total = len(self._cols) - 1
        self.offset = -float(W)      # scroll slides in from the right
        ar = float(cue.get("auto_return", 0) or 0)
        self.return_at = time.monotonic() + ar if ar > 0 else 0.0

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        self.goto(self.i + 1 if x >= W // 2 else self.i - 1)

    def goto(self, index: int):
        n = len(self.cfg["cues"])
        new = index % n
        if new == self.i:
            return
        if self.cfg["cues"][new].get("auto_return") and not self.cue().get("auto_return"):
            self.return_to = self.i          # remember where to come back to
        elif not self.cfg["cues"][new].get("auto_return"):
            self.return_to = None            # a manual change cancels pending returns
        self.i = new
        self._enter()
        log(f"cue -> {self.cue()['text']!r}")

    # -- frame ---------------------------------------------------------------
    def update(self, dt):
        now = time.monotonic()
        if self.cue()["style"] != "tally":
            self.offset += float(self.cue().get("speed", 7.0)) * dt
            if self.offset >= self._total + W + GAP:
                self.offset = -float(W)
        if self.return_at and now >= self.return_at and self.return_to is not None:
            self.i = self.return_to
            self.return_to = None
            self._enter()
            log(f"cue -> {self.cue()['text']!r} (auto-return)")
        if now >= self.next_check:
            self.next_check = now + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    self.i = min(self.i, len(self.cfg["cues"]) - 1)
                    self._enter()
                    log(f"studio.json reloaded — cue {self.i}: {self.cue()['text']!r}")
            except OSError:
                pass

    def _marker(self, screen) -> None:
        """Left column: dim tick per cue, bright at the current position."""
        n = len(self.cfg["cues"])
        for k in range(n):
            y = round(k * (H - 1) / max(1, n - 1))
            screen.set(0, y, (190, 190, 190) if k == self.i else (28, 28, 28))

    def _scroll_text(self, screen, color) -> None:
        base = int(self.offset)
        for sx in range(W):
            ci = base + sx
            if 0 <= ci <= self._total:
                col = self._cols[ci]
                for r in range(5):
                    if col[r]:
                        screen.set(sx, TEXT_Y + r, color)

    def draw(self, screen):
        now = time.monotonic()
        cue = self.cue()
        bg = tuple(int(c) for c in cue.get("bg", [0, 0, 0]))
        color = tuple(int(c) for c in cue.get("color", [255, 255, 255]))
        style = cue.get("style", "scroll")
        scale = 1.0

        self._marker(screen)

        if style == "tally":
            b = 0.82 + 0.18 * abs((now * 1.2) % 2 - 1)     # slow, strong pulse
            screen.clear(tuple(int(c * b) for c in bg))
            lines = _stack_lines(str(cue["text"]))
            if lines:
                ys = (1, 7) if len(lines) == 2 else (3,)
                for line, y in zip(lines, ys):
                    cols = render_columns(line)
                    x0 = (W - (len(cols) - 1)) // 2
                    for sx, col in enumerate(cols):
                        for r in range(5):
                            if col[r]:
                                screen.set(x0 + sx, y + r, color)
            else:
                self._scroll_text(screen, color)
        elif style == "pulse":
            b = 0.55 + 0.45 * abs((now * 0.7) % 2 - 1)     # quiet breathing
            screen.clear(tuple(int(c * b) for c in bg))
            self._scroll_text(screen, color)
        else:  # scroll, flash
            screen.clear(bg)
            self._scroll_text(screen, color)
            if style == "flash" and int(now * 3) % 2:
                scale = 0.12                              # hard studio strobe

        if scale != 1.0:
            screen.px = [tuple(int(c * scale) for c in p) for p in screen.px]
        if self.cfg.get("mirror", False):                 # flip for a mirrored webcam
            p = screen.px
            screen.px = [p[y * W + (W - 1 - x)] for y in range(H) for x in range(W)]


if __name__ == "__main__":
    run(Studio)
