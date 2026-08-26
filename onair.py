#!/usr/bin/env python3
"""On-Air / Focus light — a room-visible "busy" sign for the Arcade Coder.

Detects whether your microphone is in use (i.e. you're on a call) via a tiny
CoreAudio helper (bin/micstate) and turns the whole board into a pulsing red
ON AIR sign. When the mic is idle it shows a calm green "available" glow.

Three modes, cycled by pressing the board:
  AUTO  — follow the mic (red when in use, green when free)   [blue marker]
  ON    — force ON AIR regardless of the mic                  [red marker]
  OFF   — force available                                     [green marker]

Config in onair.json (auto-created): poll_seconds, mic_helper (path).

  python onair.py             # emulator
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "onair.json"
W = H = 12

DEFAULT = {
    "poll_seconds": 2.0,
    "mic_helper": str(BASE / "bin" / "micstate"),
    "mirror": True,     # flip horizontally so text reads right through a mirrored webcam
}

MODES = ["auto", "on", "off"]
MODE_MARK = {"auto": (0, 120, 255), "on": (255, 40, 40), "off": (0, 200, 90)}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class OnAir(Game):
    fps = 12

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.helper = self.cfg.get("mic_helper")
        self.mode = "auto"
        self.mic_on = False
        self.busy = True                 # keep the sign up; never auto-ambient
        self.cols = render_columns("ON AIR")   # scrolling banner columns
        self.scroll = 0.0
        self.last_poll = 0.0
        self._poll()
        log("on-air ready — AUTO (follows the mic); press to change mode")

    # -- mic polling ---------------------------------------------------------
    def _poll(self) -> None:
        self.last_poll = time.monotonic()
        if not self.helper or not Path(self.helper).exists():
            self.mic_on = False
            return
        try:
            out = subprocess.run([self.helper], capture_output=True, text=True,
                                 timeout=2)
            self.mic_on = out.stdout.strip() == "1"
        except Exception:
            self.mic_on = False

    def _on_air(self) -> bool:
        if self.mode == "on":
            return True
        if self.mode == "off":
            return False
        return self.mic_on

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        log(f"on-air mode -> {self.mode}")
        if self.mode == "auto":
            self._poll()

    def update(self, dt):
        now = time.monotonic()
        if self.mode == "auto" and now - self.last_poll >= self.cfg["poll_seconds"]:
            self._poll()
        self.scroll += dt * 7.0

    # -- render --------------------------------------------------------------
    def _banner(self, screen, color) -> None:
        n = len(self.cols)
        off = int(self.scroll) % (n + W)
        for sx in range(W):
            ci = sx - (W - off)          # scroll right-to-left
            col = self.cols[ci % n] if 0 <= ci < n else None
            if col is None:
                continue
            for r in range(5):
                if col[r]:
                    screen.set(sx, 3 + r, color)

    def draw(self, screen):
        now = time.monotonic()
        if self._on_air():
            p = 0.55 + 0.45 * abs((now * 1.6) % 2 - 1)      # strong pulse
            screen.clear((int(150 * p) + 40, 0, 0))
            self._banner(screen, (255, 255, 255))
            # REC dot, top-centre
            screen.set(5, 1, (255, 255, 255)); screen.set(6, 1, (255, 255, 255))
        else:
            b = 0.5 + 0.5 * abs((now * 0.7) % 2 - 1)        # slow breathing
            screen.clear((0, int(40 * b) + 6, int(12 * b)))
            # soft green orb in the middle
            for y in range(H):
                for x in range(W):
                    d = ((x - 5.5) ** 2 + (y - 5.5) ** 2) ** 0.5
                    if d < 3:
                        v = (1 - d / 3) * b
                        screen.set(x, y, (0, int(180 * v), int(70 * v)))
        screen.set(0, 6, MODE_MARK[self.mode])              # mode marker (left edge)
        if self.cfg.get("mirror", True):                    # flip for a mirrored webcam
            px = screen.px
            screen.px = [px[y * W + (W - 1 - x)] for y in range(H) for x in range(W)]


if __name__ == "__main__":
    run(OnAir)
