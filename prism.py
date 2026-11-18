#!/usr/bin/env python3
"""Prism — bend, split and mix light on 144 buttons.

Pure red, green and blue beams enter the dark board from the edges.
Mirrors reflect them at right angles — press any mirror to flip it
between '/' and '\' and watch the light reroute instantly. Targets glow
faintly in the colour they want; light them to solve the level.

The rulebook is additive colour mixing: red + green through one cell
makes yellow, green + blue makes cyan, all three make white. Target
colours have to be MADE, not matched.

Bright comet pulses stream along each beam so the light feels alive
and the direction is obvious. Turn-based: the hardware latency cannot
touch it.

Pads: press a mirror to flip it. Corners: top-left previous level,
bottom-left restart this level, bottom-right skip to the next. Level
pips on the right edge. Solving a level celebrates for a moment and
advances automatically.

prism.json (auto-created, hot-reloads): flow_speed, pulse_spacing.

  python prism.py              # emulator at http://127.0.0.1:7777
  python prism.py --hw         # real board over BLE
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, H, W, run

CONFIG_PATH = Path(__file__).resolve().parent / "prism.json"

DEFAULT = {
    "flow_speed": 5.0,          # comet pulses, cells per second
    "pulse_spacing": 6.0,       # cells between comet pulses
}

R, G, B = 1, 2, 4                 # colour masks — additive
MASK_COLORS = {
    R: (255, 45, 45),
    G: (40, 255, 60),
    B: (50, 80, 255),
    R | G: (255, 225, 50),       # yellow
    R | B: (255, 70, 255),       # magenta
    G | B: (60, 255, 255),       # cyan
    R | G | B: (255, 255, 255),  # white
}

MIRROR_SLASH = (170, 170, 190)    # '/' — dim
MIRROR_BACK = (255, 255, 255)    # '\' — bright

PREV_PAD = (0, 0)
RESET_PAD = (0, 11)
SKIP_PAD = (11, 11)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def reflect(dx: int, dy: int, mirror: str):
    """'/' and '\' reflect a direction at right angles."""
    return (-dy, -dx) if mirror == "/" else (dy, dx)


# sources: (x, y, dx, dy, mask) — the beam enters AT (x, y) moving (dx, dy)
# mirrors: (x, y, initial orientation) — the player flips these
# targets: (x, y, required mask) — satisfied when the cell CONTAINS the colour
LEVELS = (
    ("first light",
     [(0, 5, 1, 0, R)],
     [(8, 5, "\\")],
     [(8, 1, R)]),
    ("make yellow",
     [(0, 3, 1, 0, R), (3, 0, 0, 1, G)],
     [(7, 3, "\\"), (3, 7, "/")],
     [(7, 7, R | G)]),
    ("cyan crossing",
     [(0, 2, 1, 0, G), (0, 9, 1, 0, B)],
     [(5, 2, "/"), (5, 9, "\\")],
     [(5, 5, G | B)]),
    ("white out",
     [(0, 1, 1, 0, R), (0, 5, 1, 0, G), (0, 9, 1, 0, B)],
     [(4, 1, "/"), (4, 5, "/"), (4, 9, "\\")],
     [(4, 5, R | G | B)]),
    ("shared spine",
     [(0, 6, 1, 0, R), (11, 3, -1, 0, B)],
     [(4, 6, "\\"), (4, 3, "\\")],
     [(4, 4, R | B)]),
    ("double duty",
     [(0, 2, 1, 0, R), (6, 0, 0, 1, G), (0, 9, 1, 0, B)],
     [(9, 2, "/"), (6, 5, "/"), (3, 9, "/")],
     [(9, 5, R | G), (3, 11, B)]),
    ("full spectrum",
     [(0, 5, 1, 0, R), (0, 9, 1, 0, G), (0, 1, 1, 0, B)],
     [(9, 5, "/"), (5, 9, "\\"), (5, 1, "/")],
     [(5, 5, R | G | B)]),
)


class Prism(Game):
    fps = 20

    def start(self):
        self._load()
        self.t = 0.0
        self.next_check = 0.0
        self.level_i = 0
        self.load_level(0)
        log("prism — press mirrors to flip them; mix red, green and blue "
            "into the colours the targets want")

    # -- config --------------------------------------------------------------
    def _load(self):
        self.cfg = dict(DEFAULT)
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

    # -- level --------------------------------------------------------------------
    def load_level(self, i: int) -> None:
        self.level_i = i % len(LEVELS)
        name, sources, mirrors, targets = LEVELS[self.level_i]
        self.level_name = name
        self.sources = list(sources)
        self.mirrors = {(x, y): m for x, y, m in mirrors}
        self.targets = list(targets)
        self.state = "play"
        self.recompute()
        log(f"level {self.level_i + 1}/{len(LEVELS)} — {name} "
            f"({len(self.mirrors)} mirrors, {len(self.targets)} targets)")

    def recompute(self) -> None:
        """Trace every beam; accumulate additive colour masks per cell."""
        self.cells: dict[tuple[int, int], int] = {}
        self.paths: list[tuple[int, list]] = []
        for (x, y, dx, dy, mask) in self.sources:
            path = []
            cx, cy, cdx, cdy = x, y, dx, dy
            for _ in range(160):                        # loop guard
                if not (0 <= cx < W and 0 <= cy < H):
                    break
                self.cells[(cx, cy)] = self.cells.get((cx, cy), 0) | mask
                path.append((cx, cy))
                m = self.mirrors.get((cx, cy))
                if m:
                    cdx, cdy = reflect(cdx, cdy, m)
                cx, cy = cx + cdx, cy + cdy
            self.paths.append((mask, path))
        self.lit = all(
            (self.cells.get((tx, ty), 0) & req) == req
            for tx, ty, req in self.targets)

    def satisfied(self) -> bool:
        return self.lit

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == PREV_PAD:
            self.level_i = (self.level_i - 1) % len(LEVELS)
            self.load_level(self.level_i)
        elif (x, y) == RESET_PAD:
            self.load_level(self.level_i)
        elif (x, y) == SKIP_PAD:
            self.level_i = (self.level_i + 1) % len(LEVELS)
            self.load_level(self.level_i)
        elif (x, y) in self.mirrors:
            if self.state == "won":
                return
            self.mirrors[(x, y)] = "/" if self.mirrors[(x, y)] == "\\" else "\\"
            self.recompute()
            if self.lit:
                self.state = "won"
                self.won_at = time.monotonic()
                log(f"solved — {self.level_name}! advancing")
            else:
                log(f"mirror at ({x},{y}) flipped")

    # -- frame -----------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        if self.state == "won" and time.monotonic() - self.won_at > 2.2:
            last = self.level_i == len(LEVELS) - 1
            self.level_i = (self.level_i + 1) % len(LEVELS)
            self.load_level(self.level_i)
            if last:
                log("every level lit — looping back to first light")
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 1.0
            try:
                if CONFIG_PATH.stat().st_mtime != self.mtime:
                    self._load()
                    log("prism.json reloaded")
            except OSError:
                pass

    @staticmethod
    def _boost(rgb, f: float):
        return tuple(min(255, int(c + (255 - c) * f)) for c in rgb)

    def draw(self, screen):
        screen.clear((0, 0, 0))
        beam_pulse = 0.84 + 0.16 * math.sin(self.t * 6.0)
        won = self.state == "won"
        # beam cells
        for (x, y), mask in self.cells.items():
            col = MASK_COLORS[mask]
            col = tuple(int(c * beam_pulse) for c in col)
            if won:
                col = self._boost(col, 0.4 + 0.4 * abs(((self.t * 8) % 2) - 1))
            screen.set(x, y, col)
        # comet pulses streaming along each beam
        speed = float(self.cfg.get("flow_speed", 5.0))
        spacing = max(2.0, float(self.cfg.get("pulse_spacing", 6.0)))
        for si, (mask, path) in enumerate(self.paths):
            n = len(path)
            if n < 2:
                continue
            k = int(1 + n // spacing)
            for p in range(int(k)):
                pos = (self.t * speed + p * spacing + si * 1.7) % n
                px_, py_ = path[int(pos)]
                base = MASK_COLORS[self.cells[(px_, py_)]]
                screen.set(px_, py_, self._boost(base, 0.75))
        # targets: dim ask, bright thanks
        for (tx, ty, req) in self.targets:
            base = MASK_COLORS[req]
            if (self.cells.get((tx, ty), 0) & req) == req:
                col = self._boost(base, 0.6 if won else 0.35)
            else:
                col = tuple(int(c * 0.28) for c in base)
            screen.set(tx, ty, col)
        # mirrors: '/' dim, '\' bright — the orientation is readable
        for (x, y), m in self.mirrors.items():
            screen.set(x, y, MIRROR_SLASH if m == "/" else MIRROR_BACK)
        # sources: their colour pushed toward white — clearly emitters
        for (x, y, _dx, _dy, mask) in self.sources:
            screen.set(x, y, self._boost(MASK_COLORS[mask], 0.45))
        # level pips on the right edge
        for i in range(len(LEVELS)):
            screen.set(11, i, (255, 255, 255) if i == self.level_i else (30, 30, 40))
        # HUD pads
        screen.set(*PREV_PAD, (30, 90, 230))
        screen.set(*RESET_PAD, (60, 60, 60))
        screen.set(*SKIP_PAD, (170, 60, 230))


if __name__ == "__main__":
    run(Prism)