#!/usr/bin/env python3
"""Ambilight — the board glows the colours of your Mac screen, live.

A tiny helper (bin/screencap, ScreenCaptureKit) streams a 24×24 average of the
display; this averages it down to 12×12, smooths it over time for a soft glow,
and shows it on the board. Whatever's on your screen — a film, your wallpaper,
a chart — bleeds onto the shelf behind you.

Needs Screen Recording granted to ArcadeMinesweeper (same as the equalizer).
Config in ambilight.json: brightness (0–100), saturation, smooth (0–1).

  python ambilight.py         # emulator (needs the helper + permission)
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

BASE = Path(__file__).resolve().parent
HELPER = BASE / "bin" / "screencap"
CONFIG_PATH = BASE / "ambilight.json"
SRC = 24                      # helper output size (SRC×SRC)
FRAME_BYTES = SRC * SRC * 3
W = H = 12

DEFAULT = {"brightness": 100, "saturation": 1.35, "smooth": 0.35}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Ambilight(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.target = [[0.0, 0.0, 0.0] for _ in range(144)]   # latest 12×12 (0..255)
        self.disp = [[0.0, 0.0, 0.0] for _ in range(144)]     # smoothed
        self.busy = True
        self.ok = False
        self.proc = None
        self._stop = False
        self._lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()
        log("ambilight — mirroring the screen")

    def stop(self):
        self._stop = True
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass

    # -- capture reader ------------------------------------------------------
    def _reader(self):
        if not HELPER.exists():
            log("ambilight: bin/screencap missing (run scripts/build_screencap.sh)")
            return
        try:
            self.proc = subprocess.Popen([str(HELPER)], stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"ambilight: helper failed: {e}")
            return
        buf = b""
        while not self._stop and self.proc.poll() is None:
            chunk = self.proc.stdout.read(FRAME_BYTES - len(buf))
            if not chunk:
                break
            buf += chunk
            if len(buf) >= FRAME_BYTES:
                self._ingest(buf[:FRAME_BYTES])
                buf = buf[FRAME_BYTES:]
        self.ok = False

    def _ingest(self, frame: bytes):
        # average each 2×2 block of the 24×24 source into one 12×12 pixel
        out = [[0.0, 0.0, 0.0] for _ in range(144)]
        for by in range(H):
            for bx in range(W):
                r = g = b = 0
                for dy in range(2):
                    for dx in range(2):
                        i = ((by * 2 + dy) * SRC + (bx * 2 + dx)) * 3
                        r += frame[i]; g += frame[i + 1]; b += frame[i + 2]
                out[by * W + bx] = [r / 4, g / 4, b / 4]
        with self._lock:
            self.target = out
            self.ok = True

    # -- render --------------------------------------------------------------
    def _punch(self, px):
        r, g, b = px
        m = (r + g + b) / 3
        s = self.cfg.get("saturation", 1.35)
        return (m + (r - m) * s, m + (g - m) * s, m + (b - m) * s)

    def draw(self, screen):
        now = time.monotonic()
        if not self.ok:
            v = int(30 + 20 * abs((now * 1.5) % 2 - 1))     # waiting shimmer
            for y in range(H):
                for x in range(W):
                    screen.set(x, y, (v // 3, v // 3, v))
            return
        with self._lock:
            target = self.target
        k = max(0.05, min(1.0, self.cfg.get("smooth", 0.35)))
        f = max(0.05, self.cfg.get("brightness", 100) / 100.0)
        for i in range(144):
            d, t = self.disp[i], target[i]
            d[0] += (t[0] - d[0]) * k
            d[1] += (t[1] - d[1]) * k
            d[2] += (t[2] - d[2]) * k
            r, g, b = self._punch(d)
            screen.set(i % W, i // W,
                       (max(0, min(255, int(r * f))),
                        max(0, min(255, int(g * f))),
                        max(0, min(255, int(b * f)))))


if __name__ == "__main__":
    run(Ambilight)
