#!/usr/bin/env python3
"""YouTube Music control — a media remote for the Arcade Coder.

The top of the board is an audio-reactive bar visual driven by the shared
system-audio capture, so it dances while music plays and settles when it's
paused. The bottom third is a transport bar:

    [  ⏮ prev  ][  ▶/⏸ play·pause  ][  ⏭ next  ]

Play/next/previous are sent as macOS media keys, so YouTube Music (in any
browser, even in the background) responds — as does Music/Spotify if that's
what owns "now playing". The play/pause glyph reflects whether audio is
actually coming out. The bottom-corner volume pads work here too.

  python ytmusic.py           # emulator (no live audio/keys)
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
import media

W = H = 12
RED = (230, 0, 0)
VIS_BOTTOM = 6          # bars grow up from row 6
PLAY_THRESHOLD = 0.004  # bus.level above this => treat as "playing"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class YTMusic(Game):
    fps = 14

    def start(self):
        self.levels = [0.0] * W
        self.gain = 1e-4
        self.playing = False
        self.flash = {}                 # button -> expiry (tap feedback)
        self.last = time.monotonic()
        self.busy = False               # a remote; let it idle out normally
        log("ytmusic ready — ⏮ ⏯ ⏭ (media keys)")

    def _bus(self):
        return getattr(self, "audio_bus", None)

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if y < 8:                       # top = visual, ignore taps there
            return
        now = time.monotonic()
        if x <= 3:
            self.flash["prev"] = now + 0.2
            media.prev_track(); log("ytmusic: prev")
        elif x >= 8:
            self.flash["next"] = now + 0.2
            media.next_track(); log("ytmusic: next")
        else:
            self.flash["play"] = now + 0.2
            media.play_pause(); log("ytmusic: play/pause")

    def update(self, dt):
        now = time.monotonic()
        bus = self._bus()
        lvl = bus.level if bus is not None else 0.0
        self.playing = lvl > PLAY_THRESHOLD
        self.gain = max(lvl, self.gain * 0.99, 1e-4)
        norm = min(1.0, lvl / self.gain) if self.gain else 0.0
        for i in range(W):
            wob = 0.55 + 0.45 * math.sin(now * 4.0 + i * 0.9)
            target = norm * wob * VIS_BOTTOM if self.playing else 0.0
            if target >= self.levels[i]:
                self.levels[i] = target
            else:
                self.levels[i] = max(target, self.levels[i] - 0.6)

    # -- render --------------------------------------------------------------
    def _bar_color(self, frac):
        # bottom red -> mid orange -> top near-white
        if frac < 0.5:
            return (230, int(120 * (frac / 0.5)), 0)
        f = (frac - 0.5) / 0.5
        return (230 + int(25 * f), 120 + int(135 * f), int(200 * f))

    def _glyph(self, screen, cells, color):
        for x, y in cells:
            if 0 <= x < W and 0 <= y < H:
                screen.set(x, y, color)

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        # audio-reactive bars (rows 0..6)
        for i in range(W):
            h = int(round(self.levels[i]))
            for r in range(h):
                y = VIS_BOTTOM - r
                if 0 <= y <= VIS_BOTTOM:
                    screen.set(i, y, self._bar_color(r / max(1, VIS_BOTTOM)))
        # separator + transport plate
        for x in range(W):
            screen.set(x, 7, (40, 0, 0))
        for y in range(8, 11):
            for x in range(W):
                screen.set(x, y, (26, 0, 0))
        # tap flashes
        def col(key, base):
            return (255, 255, 255) if now < self.flash.get(key, 0) else base
        white = (245, 245, 245)
        # prev  ⏮  (cols 1-3)
        self._glyph(screen, [(1, 8), (1, 9), (1, 10), (3, 8), (2, 9), (3, 10)],
                    col("prev", white))
        # next  ⏭  (cols 8-10)
        self._glyph(screen, [(8, 8), (9, 9), (8, 10), (10, 8), (10, 9), (10, 10)],
                    col("next", white))
        # play / pause  (cols 5-6)
        if self.playing:                       # show pause bars
            self._glyph(screen, [(5, 8), (5, 9), (5, 10), (7, 8), (7, 9), (7, 10)],
                        col("play", (0, 230, 90)))
        else:                                  # show play triangle
            self._glyph(screen, [(5, 8), (5, 9), (5, 10), (6, 9)],
                        col("play", white))
        # a small "now playing" dot pulses red when audio is present
        if self.playing:
            p = int(120 + 120 * (0.5 + 0.5 * math.sin(now * 5)))
            screen.set(6, 11, (p, 0, 0))


if __name__ == "__main__":
    run(YTMusic)
