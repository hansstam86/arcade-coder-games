#!/usr/bin/env python3
"""Spaces — a physical AeroSpace workspace switcher for the Arcade Coder.

For the Omachy / AeroSpace tiling setup. Shows workspaces 1–9 as a 3×3 grid
(numpad layout: top-left = 1, bottom-right = 9). Each tile has its own hue;
brightness shows state — dim = empty, solid = has windows, bright pulse =
the focused workspace. Tap a tile to jump to that workspace.

  python spaces.py            # emulator (needs AeroSpace installed)
"""

from __future__ import annotations

import colorsys
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12
AERO = shutil.which("aerospace") or "/opt/homebrew/bin/aerospace"
HUES = [0.0, 0.08, 0.14, 0.30, 0.45, 0.52, 0.62, 0.78, 0.90]   # per-workspace colour


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _aero(*args):
    try:
        out = subprocess.run([AERO, *args], capture_output=True, text=True, timeout=3)
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


class Spaces(Game):
    fps = 12

    def start(self):
        self.focused = "1"
        self.nonempty = {"1"}
        self.ok = Path(AERO).exists()
        self.shift = False                           # SHIFT armed = next tap MOVES the window
        self.flash = None                            # move-confirmation flash (tile origin)
        self.flash_until = 0.0
        self.busy = False
        self._stop = False
        if self.ok:
            self._poll()
            threading.Thread(target=self._loop, daemon=True).start()
        log(f"spaces — AeroSpace switcher ({'ready' if self.ok else 'aerospace not found'})")

    def stop(self):
        self._stop = True

    def _poll(self):
        f = _aero("list-workspaces", "--focused")
        if f:
            self.focused = f[0]
        self.nonempty = set(_aero("list-workspaces", "--monitor", "all", "--empty", "no"))

    def _loop(self):
        while not self._stop:
            self._poll()
            time.sleep(0.7)

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if not self.ok:
            return
        if y == 11:                                  # bottom gap row = SHIFT (move-window) toggle
            self.shift = not self.shift
            log(f"spaces shift -> {self.shift}")
            return
        col, row = x // 4, y // 4                    # 3x3 tiles -> workspace 1..9
        if col > 2 or row > 2:
            return
        n = str(row * 3 + col + 1)
        if self.shift:                               # send the focused window to workspace n
            threading.Thread(target=lambda: _aero("move-node-to-workspace", n),
                             daemon=True).start()
            self.shift = False                       # shift is one-shot, like tapping the key
            self.flash = (col * 4, row * 4)
            self.flash_until = time.monotonic() + 0.45
            log(f"spaces move-window -> workspace {n}")
            return
        self.focused = n                             # optimistic switch
        threading.Thread(target=lambda: _aero("workspace", n), daemon=True).start()
        log(f"spaces -> workspace {n}")

    def update(self, dt):
        pass

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        if not self.ok:
            for x in range(W):                       # dim red bar = no aerospace
                screen.set(x, 5, (40, 0, 0)); screen.set(x, 6, (40, 0, 0))
            return
        pulse = 0.55 + 0.45 * abs((now * 1.6) % 2 - 1)
        for row in range(3):
            for col in range(3):
                n = str(row * 3 + col + 1)
                hue = HUES[row * 3 + col]
                if n == self.focused:
                    v = 0.55 + 0.45 * pulse
                elif n in self.nonempty:
                    v = 0.5
                else:
                    v = 0.12
                r, g, b = colorsys.hsv_to_rgb(hue, 0.85, v)
                col0, row0 = col * 4, row * 4
                for dy in range(3):                  # 3x3 tile + 1px gap
                    for dx in range(3):
                        screen.set(col0 + dx, row0 + dy,
                                   (int(r * 255), int(g * 255), int(b * 255)))
                if n == self.focused:                # white corner ticks on the focused one
                    screen.set(col0, row0, (255, 255, 255))
                    screen.set(col0 + 2, row0 + 2, (255, 255, 255))
                if self.shift:                       # armed: orange pip = "tap to send window here"
                    screen.set(col0 + 1, row0 + 1, (255, 140, 0))

        if self.flash and now < self.flash_until:    # move confirmation
            ox, oy = self.flash
            for dy in range(3):
                for dx in range(3):
                    screen.set(ox + dx, oy + dy, (255, 255, 255))

        sp = 0.45 + 0.55 * abs((now * 2.4) % 2 - 1)  # SHIFT strip along the bottom gap row
        for x in range(W):
            if x in (0, 6, 11):                      # leave the volume −/mute/+ pads alone
                continue
            screen.set(x, 11, (int(255 * sp), int(120 * sp), 0) if self.shift else (35, 35, 40))


if __name__ == "__main__":
    run(Spaces)
