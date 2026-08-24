#!/usr/bin/env python3
"""YouTube Music control — a media remote for the Arcade Coder.

Top: an audio-reactive bar visual driven by the shared system-audio capture.
Middle: a transport bar — [⏮ prev][▶/⏸ play·pause][⏭ next] — sent as macOS
media keys, so YouTube Music (in any browser, even backgrounded) responds.
Play/pause state follows whether audio is coming out. The global bottom-row
pads (volume −, mute, volume +) work here too.

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
VIS_BOTTOM = 4          # bars grow up from row 4
SEP_ROW = 5
TRANSPORT_ROWS = (6, 7, 8)
PLAY_THRESHOLD = 0.004  # bus.level above this => "playing"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class YTMusic(Game):
    fps = 14

    def start(self):
        self.levels = [0.0] * W
        self.gain = 1e-4
        self.playing = False
        self.flash = {}                 # button -> expiry (tap feedback)
        self.busy = False
        log("ytmusic ready — ⏮ ⏯ ⏭")

    def _bus(self):
        return getattr(self, "audio_bus", None)

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if not (TRANSPORT_ROWS[0] <= y <= TRANSPORT_ROWS[-1] + 1):
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
            self.levels[i] = target if target >= self.levels[i] \
                else max(target, self.levels[i] - 0.5)

    # -- render --------------------------------------------------------------
    def _bar_color(self, frac):
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
        # audio-reactive bars (rows 0..VIS_BOTTOM)
        for i in range(W):
            h = int(round(self.levels[i]))
            for r in range(h):
                y = VIS_BOTTOM - r
                if 0 <= y <= VIS_BOTTOM:
                    screen.set(i, y, self._bar_color(r / max(1, VIS_BOTTOM)))
        # separator + transport plate
        for x in range(W):
            screen.set(x, SEP_ROW, (40, 0, 0))
        for y in TRANSPORT_ROWS:
            for x in range(W):
                screen.set(x, y, (26, 0, 0))
        r0 = TRANSPORT_ROWS[0]

        def col(key, base):
            return (255, 255, 255) if now < self.flash.get(key, 0) else base
        white = (245, 245, 245)
        # prev ⏮ (cols 1-3)
        self._glyph(screen, [(1, r0), (1, r0 + 1), (1, r0 + 2),
                             (3, r0), (2, r0 + 1), (3, r0 + 2)], col("prev", white))
        # next ⏭ (cols 8-10)
        self._glyph(screen, [(8, r0), (9, r0 + 1), (8, r0 + 2),
                             (10, r0), (10, r0 + 1), (10, r0 + 2)], col("next", white))
        # play/pause (cols 5-7)
        if self.playing:
            self._glyph(screen, [(5, r0), (5, r0 + 1), (5, r0 + 2),
                                 (7, r0), (7, r0 + 1), (7, r0 + 2)],
                        col("play", (0, 230, 90)))
        else:
            self._glyph(screen, [(5, r0), (5, r0 + 1), (5, r0 + 2), (6, r0 + 1)],
                        col("play", white))


if __name__ == "__main__":
    run(YTMusic)
