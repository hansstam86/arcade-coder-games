#!/usr/bin/env python3
"""GIF player — play animated GIFs on the Arcade Coder.

Drop any `.gif` into the `gifs/` folder and it shows up here, downsampled to
12x12 and looped at its own frame timing. Pixel-art GIFs look crisp; busy ones
become a lovely abstract colour dance. Tap anywhere to skip to the next GIF.
Comes with a few demo loops (run scripts/make_gifs.py to regenerate them).

Config in gifplayer.json: brightness (0–100), smooth (blend photographic GIFs).

  python gifplayer.py         # emulator
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

BASE = Path(__file__).resolve().parent
GIF_DIR = BASE / "gifs"
CONFIG_PATH = BASE / "gifplayer.json"
W = H = 12


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _load_gif(path):
    """Return (frames, durations) — frames are 144-long lists of (r,g,b)."""
    from PIL import Image
    im = Image.open(path)
    frames, durs = [], []
    try:
        while True:
            fr = im.convert("RGB").resize((W, H), Image.LANCZOS)
            frames.append(list(fr.getdata()))
            durs.append(max(0.03, im.info.get("duration", 90) / 1000.0))
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    return frames, durs


class GifPlayer(Game):
    fps = 20

    def start(self):
        self.cfg = {"brightness": 90}
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.paths = sorted(GIF_DIR.glob("*.gif")) if GIF_DIR.exists() else []
        self.idx = 0
        self.frames, self.durs = [], []
        self.fi = 0
        self.frame_until = 0.0
        self.scroll = 0.0
        if self.paths:
            self._select(0)
        log(f"gif player — {len(self.paths)} gif(s)")

    def _select(self, i):
        self.idx = i % len(self.paths)
        try:
            self.frames, self.durs = _load_gif(self.paths[self.idx])
        except Exception as e:
            self.frames, self.durs = [], []
            log(f"gif load failed: {e}")
        self.fi = 0
        self.frame_until = time.monotonic() + (self.durs[0] if self.durs else 0.1)
        log(f"gif -> {self.paths[self.idx].name}")

    def on_press(self, x, y):
        if len(self.paths) > 1:
            self._select(self.idx + 1)

    def update(self, dt):
        now = time.monotonic()
        self.scroll += dt * 8
        if self.frames and now >= self.frame_until:
            self.fi = (self.fi + 1) % len(self.frames)
            self.frame_until = now + self.durs[self.fi]

    def draw(self, screen):
        if not self.frames:                       # no gifs -> hint
            screen.clear((4, 4, 12))
            cols = render_columns("  ADD GIFS TO gifs/  ")
            base = int(self.scroll) % max(1, len(cols))
            for sx in range(W):
                ci = base + sx
                if 0 <= ci < len(cols):
                    for r in range(5):
                        if cols[ci][r]:
                            screen.set(sx, 3 + r, (0, 200, 255))
            return
        f = max(0.1, self.cfg.get("brightness", 90) / 100.0)
        frame = self.frames[self.fi]
        for i, px in enumerate(frame):
            screen.set(i % W, i // W,
                       (int(px[0] * f), int(px[1] * f), int(px[2] * f)))


if __name__ == "__main__":
    run(GifPlayer)
