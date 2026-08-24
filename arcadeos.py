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
           "sound_activated": False, "sound_threshold": 0.006, "silence_seconds": 6.0,
           # mirror the board onto a Divoom Pixoo (must be in app mode)
           "pixoo_mirror": False,
           # dedicated Mac-volume pads: bottom-left = down, bottom-right = up.
           # Active in idle/ambient, equalizer, home, and the notification
           # center (set "everywhere" to also override games/deck/etc.).
           "volume_pads": True, "volume_step": 6, "volume_everywhere": False}

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
        self.pending_marquee: str | None = None
        self.marquee_return_to: str | None = None
        self.marquee_return_at = 0.0
        from notifcenter import NotifCenter

        self.center = NotifCenter()       # on-board notification center (modal)
        self.in_center = False
        self.center_return_to: str | None = None
        self.volume = None                # dedicated Mac-volume pads
        self.vol_shown_until = 0.0
        self.vol_level = 0
        if self.cfg.get("volume_pads"):
            try:
                from volume import Volume

                self.volume = Volume()
                self.vol_level = self.volume.level
            except Exception as exc:  # noqa: BLE001
                log(f"volume pads unavailable: {exc!r}")
        try:
            from notifd import ensure_server as notify_server

            self.notify = notify_server()
            self.notify.on_notification = self.center.add
        except Exception as exc:  # noqa: BLE001
            log(f"notification service not started: {exc!r}")
        self.pixoo = None
        if self.cfg.get("pixoo_mirror"):
            try:
                from pixoo_mirror import PixooMirror

                self.pixoo = PixooMirror()
                log("pixoo mirror started (mirroring board -> /dev/cu.Pixoo)")
            except Exception as exc:  # noqa: BLE001
                log(f"pixoo mirror failed: {exc!r}")
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

    VOL_DOWN = (0, 11)
    VOL_UP = (11, 11)

    def _volume_active(self) -> bool:
        if self.volume is None:
            return False
        if self.cfg.get("volume_everywhere"):
            return True
        # active where a press isn't otherwise doing interactive work
        return self.in_center or self.app_name in ("home", "ambient", "party")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        now = time.monotonic()
        self.last_press = now
        # dedicated volume pads (checked first so they always win where active)
        if self._volume_active() and (x, y) in (self.VOL_DOWN, self.VOL_UP):
            step = self.cfg.get("volume_step", 6)
            self.vol_level = self.volume.change(step if (x, y) == self.VOL_UP else -step)
            self.vol_shown_until = now + 1.2
            return
        if self.in_center:                          # a press marks the alert read
            self.center.press(x, y)
            return
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
        if self.pending_marquee is not None:           # a notification wants to scroll
            text, self.pending_marquee = self.pending_marquee, None
            if self.app_name != "marquee":
                self.marquee_return_to = self.app_name
            self.enter("marquee")
            self.app.set_text(text)
            # one full scroll pass, then return to where we were
            dur = (self.app.total + 24) / max(1.0, self.app.cfg["speed"]) + 0.5
            self.marquee_return_at = now + dur
            log(f"notification marquee: {text!r} ({dur:.0f}s)")
        if self.marquee_return_at and now >= self.marquee_return_at:
            self.marquee_return_at = 0.0
            back = self.marquee_return_to or "ambient"
            self.marquee_return_to = None
            self.enter(back)
        if self.pending_switch:                        # from the web dashboard
            name, self.pending_switch = self.pending_switch, None
            self.auto_ambient_from = None
            self.marquee_return_at = 0.0               # a manual switch cancels the return
            self.enter(name)
        if self.app is not None:
            self.app.update(dt)                     # underlying app keeps running
        # notification center: modal, overrides everything until all are read
        if self.center.has_unread() and not self.in_center:
            self.in_center = True
            log(f"notification center: {self.center.unread()} unread (press to dismiss)")
        elif self.in_center and not self.center.has_unread():
            self.in_center = False
            log("notifications cleared")
        if self.in_center:                          # nothing else runs while modal
            return
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
        now = time.monotonic()
        if self.in_center:                          # modal: the alert owns the screen
            self.center.draw(screen, now)
        elif self.app is not None:
            self.app.draw(screen)
            if self.notify:
                self.notify.draw_overlay(screen, now)
        else:
            screen.clear((0, 0, 0))
            for _name, _cls, icon, (x, y) in APPS:
                screen.set(x, y, icon[0]); screen.set(x + 1, y, icon[1])
                screen.set(x, y + 1, icon[2]); screen.set(x + 1, y + 1, icon[3])
            pulse = int(40 + 30 * (0.5 + 0.5 * __import__("math").sin(now * 2)))
            screen.set(6, 11, (0, pulse, pulse // 2))   # heartbeat (not on a vol pad)
            if self.notify:
                self.notify.draw_overlay(screen, now)
        self._draw_volume(screen, now)              # dedicated volume pads on top
        if self.pixoo:
            self.pixoo.set_board_frame(screen.px)

    def _draw_volume(self, screen, now: float) -> None:
        if not self._volume_active():
            return
        dx, dy = self.VOL_DOWN
        ux, uy = self.VOL_UP
        screen.set(dx, dy, (0, 120, 255))           # always lit − (blue)
        screen.set(ux, uy, (0, 230, 80))            # always lit + (green)
        if now < self.vol_shown_until:              # feedback bar after a press
            lit = round(self.vol_level / 100 * 12)
            for x in range(12):
                if x < lit:
                    g = 140 + int(x / 11 * 115)
                    screen.set(x, 10, (0, g, 40))
                else:
                    screen.set(x, 10, (10, 10, 14))
            screen.set(dx, dy, (120, 200, 255))     # flash brighter on press
            screen.set(ux, uy, (150, 255, 150))


if __name__ == "__main__":
    run(ArcadeOS)
