#!/usr/bin/env python3
"""YouTube Music control — a media remote for the Arcade Coder.

Top: an audio-reactive bar visual driven by the shared system-audio capture.
Middle: a transport bar — [⏮ prev][▶/⏸ play·pause][⏭ next] — sent as macOS
media keys, so YouTube Music (in any browser, even backgrounded) responds.
Bottom: a track progress bar, from the now-playing helper (bin/nowplaying,
private MediaRemote). Play/pause state follows the real playback rate when
that info is available, else falls back to whether audio is coming out. The
bottom-corner volume pads work here too.

  python ytmusic.py           # emulator (no live audio/keys/metadata)
"""

from __future__ import annotations

import math
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
import media

BASE = Path(__file__).resolve().parent
NP_HELPER = BASE / "bin" / "nowplaying"
W = H = 12
VIS_BOTTOM = 4          # bars grow up from row 4
SEP_ROW = 5
TRANSPORT_ROWS = (6, 7, 8)
PROGRESS_ROW = 10
PLAY_THRESHOLD = 0.004  # bus.level above this => "playing" (fallback)


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
        # now-playing (from the helper)
        self.np = None                  # (elapsed, duration, rate, title, artist)
        self.np_at = 0.0
        self._np_stop = False
        self._poll_np()
        threading.Thread(target=self._np_loop, daemon=True).start()
        log("ytmusic ready — ⏮ ⏯ ⏭ (media keys)")

    def stop(self):
        self._np_stop = True

    def _bus(self):
        return getattr(self, "audio_bus", None)

    # -- now-playing polling -------------------------------------------------
    def _poll_np(self) -> None:
        if not NP_HELPER.exists():
            return
        try:
            out = subprocess.run([str(NP_HELPER)], capture_output=True, text=True,
                                 timeout=3)
            line = out.stdout.strip()
            if line.startswith("OK|"):
                _, el, dur, rate, title, artist = (line.split("|", 5) + [""] * 6)[:6]
                self.np = (float(el), float(dur), float(rate), title, artist)
                self.np_at = time.monotonic()
            else:
                self.np = None
        except Exception:
            self.np = None

    def _np_loop(self) -> None:
        while not self._np_stop:
            self._poll_np()
            time.sleep(1.0)

    def _elapsed_now(self):
        """Interpolated (elapsed, duration) or None."""
        if not self.np:
            return None
        el, dur, rate, _t, _a = self.np
        if dur <= 0:
            return None
        if rate > 0:
            el = el + (time.monotonic() - self.np_at) * rate
        return max(0.0, min(dur, el)), dur

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
        if self.np:                     # trust real playback rate if we have it
            self.playing = self.np[2] > 0
        else:
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
        if self.playing:                # pause bars
            self._glyph(screen, [(5, r0), (5, r0 + 1), (5, r0 + 2),
                                 (7, r0), (7, r0 + 1), (7, r0 + 2)],
                        col("play", (0, 230, 90)))
        else:                           # play triangle
            self._glyph(screen, [(5, r0), (5, r0 + 1), (5, r0 + 2), (6, r0 + 1)],
                        col("play", white))
        # progress bar (row PROGRESS_ROW)
        prog = self._elapsed_now()
        if prog:
            elapsed, dur = prog
            filled = int(round(elapsed / dur * W))
            head = min(W - 1, filled)
            for x in range(W):
                if x < filled:
                    screen.set(x, PROGRESS_ROW, (255, 40, 40))
                else:
                    screen.set(x, PROGRESS_ROW, (50, 12, 12))
            screen.set(head, PROGRESS_ROW, (255, 255, 255))   # playhead
        else:
            for x in range(W):          # no metadata -> dim baseline
                screen.set(x, PROGRESS_ROW, (30, 8, 8))


if __name__ == "__main__":
    run(YTMusic)
