#!/usr/bin/env python3
"""ArcadeOS — one process hosting everything the Arcade Coder can be.

Home screen with seven app icons: games (the 10-game arcade), deck, ko-pads,
sequencer, visualizer, rhythm, ambient. Press an icon to enter an app.

- Hot corner: triple-tap the top-left pad within 1.5s from anywhere -> home.
- Auto-ambient: no presses for `idle_minutes` -> ambient; one press returns
  you to the app you were in. Apps that report `busy` (sequencer playing,
  visualizer mid-jam, rhythm mid-run) are never interrupted.
- Web dashboard at http://127.0.0.1:7770 shows the running app and switches
  apps remotely.

  python arcadeos.py            # emulator
  python arcadeos_hw.py         # real board via the app bundle
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "examples"))

from arcadecoder import Game, run
from full_arcade import Arcade
from deck import Deck
from kopads import KOPads
from seq import Sequencer
from midiviz import MidiViz
from rhythm import Rhythm
from ambient import Ambient

CONFIG_PATH = Path(__file__).resolve().parent / "arcadeos.json"

DEFAULT = {"idle_minutes": 10, "corner_taps": 3, "corner_window": 1.5}

APPS = [
    # (name, class, icon quad colours [tl, tr, bl, br], position)
    ("games", Arcade, [(0, 180, 0), (200, 0, 0), (200, 180, 0), (0, 60, 220)], (1, 2)),
    ("deck", Deck, [(230, 230, 230)] * 4, (4, 2)),
    ("kopads", KOPads, [(240, 90, 0), (220, 200, 0), (230, 230, 230), (200, 0, 60)], (7, 2)),
    ("seq", Sequencer, [(0, 200, 0), (0, 200, 0), (2, 2, 10), (0, 200, 0)], (10, 2)),
    ("midiviz", MidiViz, [(200, 0, 180), (0, 190, 190), (0, 190, 190), (200, 0, 180)], (1, 7)),
    ("rhythm", Rhythm, [(200, 0, 60), (220, 200, 0), (220, 200, 0), (200, 0, 60)], (4, 7)),
    ("ambient", Ambient, [(0, 40, 120), (0, 60, 160), (0, 60, 160), (0, 40, 120)], (7, 7)),
]
APP_BY_NAME = {name: cls for name, cls, _i, _p in APPS}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class ArcadeOS(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.app = None
        self.app_name = "home"
        self.auto_ambient_from: str | None = None
        self.last_press = time.monotonic()
        self.corner_taps: list[float] = []
        self.pending_switch: str | None = None
        try:
            from arcadeos_web import ensure_server, set_os

            set_os(self)
            ensure_server()
        except Exception as exc:  # noqa: BLE001
            log(f"dashboard not started: {exc!r}")
        log("ArcadeOS home — press an icon: " + " ".join(n for n, *_ in APPS))

    # -- app switching -------------------------------------------------------
    def enter(self, name: str) -> None:
        if name == "home":
            self._cleanup()
            self.app, self.app_name = None, "home"
            log("home")
            return
        cls = APP_BY_NAME.get(name)
        if cls is None:
            return
        self._cleanup()
        self.app = cls()
        self.app.start()
        self.app_name = name
        log(f"entered {name}")

    def _cleanup(self) -> None:
        app = self.app
        if app is None:
            return
        for attr in ("port",):          # close MIDI handles apps hold
            port = getattr(app, attr, None)
            if port is not None and hasattr(port, "close"):
                try:
                    port.close()
                except Exception:
                    pass
        stop = getattr(app, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        now = time.monotonic()
        self.last_press = now
        # hot corner: N taps on (0,0) within the window -> home
        if (x, y) == (0, 0) and self.app_name != "home":
            self.corner_taps = [t for t in self.corner_taps if now - t < self.cfg["corner_window"]]
            self.corner_taps.append(now)
            if len(self.corner_taps) >= self.cfg["corner_taps"]:
                self.corner_taps = []
                self.enter("home")
                return
        else:
            self.corner_taps = []
        if self.auto_ambient_from:                     # wake from auto-ambient
            back = self.auto_ambient_from
            self.auto_ambient_from = None
            self.enter(back)
            return
        if self.app_name == "home":
            for name, _cls, _icon, (bx, by) in APPS:
                if bx - 1 <= x <= bx + 2 and by - 1 <= y <= by + 2:
                    self.enter(name)
                    return
            return
        self.app.on_press(x, y)

    # -- loop ----------------------------------------------------------------
    def update(self, dt):
        now = time.monotonic()
        if self.pending_switch:                        # from the web dashboard
            name, self.pending_switch = self.pending_switch, None
            self.auto_ambient_from = None
            self.enter(name)
        if self.app is not None:
            self.app.update(dt)
        if (self.app_name not in ("home", "ambient")
                and not self.auto_ambient_from
                and not getattr(self.app, "busy", False)
                and now - self.last_press > self.cfg["idle_minutes"] * 60):
            self.auto_ambient_from = self.app_name
            self.enter("ambient")
            log(f"idle — ambient (press to return to {self.auto_ambient_from})")

    def draw(self, screen):
        if self.app is not None:
            self.app.draw(screen)
            return
        now = time.monotonic()
        screen.clear((0, 0, 0))
        for _name, _cls, icon, (x, y) in APPS:
            screen.set(x, y, icon[0]); screen.set(x + 1, y, icon[1])
            screen.set(x, y + 1, icon[2]); screen.set(x + 1, y + 1, icon[3])
        # heartbeat pixel so home doesn't look frozen
        pulse = int(40 + 30 * (0.5 + 0.5 * __import__("math").sin(now * 2)))
        screen.set(0, 11, (0, pulse, pulse // 2))


if __name__ == "__main__":
    run(ArcadeOS)
