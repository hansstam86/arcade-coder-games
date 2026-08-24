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
from party import Party
from marquee import Marquee

CONFIG_PATH = Path(__file__).resolve().parent / "arcadeos.json"

DEFAULT = {"idle_minutes": 10, "corner_taps": 3, "corner_window": 1.5,
           # sound-activated equalizer: play audio -> party; quiet -> ambient
           "sound_activated": False, "sound_threshold": 0.006, "silence_seconds": 6.0}

APPS = [
    # (name, class, icon quad colours [tl, tr, bl, br], position) — 3x3 grid
    ("games", Arcade, [(0, 180, 0), (200, 0, 0), (200, 180, 0), (0, 60, 220)], (1, 1)),
    ("deck", Deck, [(230, 230, 230)] * 4, (5, 1)),
    ("kopads", KOPads, [(240, 90, 0), (220, 200, 0), (230, 230, 230), (200, 0, 60)], (9, 1)),
    ("seq", Sequencer, [(0, 200, 0), (0, 200, 0), (2, 2, 10), (0, 200, 0)], (1, 5)),
    ("midiviz", MidiViz, [(200, 0, 180), (0, 190, 190), (0, 190, 190), (200, 0, 180)], (5, 5)),
    ("rhythm", Rhythm, [(200, 0, 60), (220, 200, 0), (220, 200, 0), (200, 0, 60)], (9, 5)),
    ("ambient", Ambient, [(0, 40, 120), (0, 60, 160), (0, 60, 160), (0, 40, 120)], (1, 9)),
    ("party", Party, [(0, 220, 0), (255, 220, 0), (255, 60, 0), (180, 0, 255)], (5, 9)),
    ("marquee", Marquee, [(0, 200, 255), (0, 120, 255), (0, 120, 255), (0, 200, 255)], (9, 9)),
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
        self.sound_auto = False           # True while party was auto-opened by sound
        self.last_sound = 0.0
        self.bus = None
        if self.cfg.get("sound_activated"):
            try:
                from audiobus import AudioBus

                self.bus = AudioBus()
                log("sound-activated: shared audio bus started")
            except Exception as exc:  # noqa: BLE001
                log(f"audio bus failed: {exc!r}")
        try:
            from arcadeos_web import ensure_server, set_os

            set_os(self)
            ensure_server()
        except Exception as exc:  # noqa: BLE001
            log(f"dashboard not started: {exc!r}")
        self.notify = None
        try:
            from notifd import ensure_server as notify_server

            self.notify = notify_server()
        except Exception as exc:  # noqa: BLE001
            log(f"notification service not started: {exc!r}")
        log("ArcadeOS home — press an icon: " + " ".join(n for n, *_ in APPS))
        if self.bus is not None:            # sound-activated: rest in ambient
            self.enter("ambient")

    # -- app switching -------------------------------------------------------
    def enter(self, name: str) -> None:
        self.last_press = time.monotonic()   # any entry counts as activity
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
        if name == "party" and self.bus is not None:
            self.app.audio_bus = self.bus     # share the one capture
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
        if (self.cfg["idle_minutes"] > 0            # 0 = auto-ambient disabled
                and self.app_name not in ("home", "ambient")
                and not self.auto_ambient_from
                and not getattr(self.app, "busy", False)
                and now - self.last_press > self.cfg["idle_minutes"] * 60):
            self.auto_ambient_from = self.app_name
            self.enter("ambient")
            log(f"idle — ambient (press to return to {self.auto_ambient_from})")
        self._sound_supervise(now)

    def _sound_supervise(self, now: float) -> None:
        """Sound-activated equalizer: audio playing -> party, quiet -> ambient.
        Only toggles between ambient and an auto-opened party; leaves the user
        alone in any other app or a manually-opened party."""
        if self.bus is None or not self.cfg.get("sound_activated"):
            return
        loud = self.bus.level > self.cfg["sound_threshold"]
        if loud:
            self.last_sound = now
        if self.app_name in ("ambient", "home") and loud:
            self.enter("party")
            self.sound_auto = True
            log(f"sound detected (level {self.bus.level:.3f}) — equalizer")
        elif (self.app_name == "party" and self.sound_auto
              and now - self.last_sound > self.cfg["silence_seconds"]):
            self.enter("ambient")
            self.sound_auto = False
            log("quiet — back to ambient")

    def draw(self, screen):
        if self.app is not None:
            self.app.draw(screen)
            if self.notify:
                self.notify.draw_overlay(screen, time.monotonic())
            return
        now = time.monotonic()
        screen.clear((0, 0, 0))
        for _name, _cls, icon, (x, y) in APPS:
            screen.set(x, y, icon[0]); screen.set(x + 1, y, icon[1])
            screen.set(x, y + 1, icon[2]); screen.set(x + 1, y + 1, icon[3])
        # heartbeat pixel so home doesn't look frozen
        pulse = int(40 + 30 * (0.5 + 0.5 * __import__("math").sin(now * 2)))
        screen.set(0, 11, (0, pulse, pulse // 2))
        if self.notify:
            self.notify.draw_overlay(screen, now)


if __name__ == "__main__":
    run(ArcadeOS)
