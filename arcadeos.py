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
import threading
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
from pomodoro import Pomodoro
from countdown import Countdown
from weather import Weather
from onair import OnAir
from ytmusic import YTMusic
from doodle import Doodle
from stopwatch import Stopwatch
from worldclock import WorldClock
from tamagotchi import Tamagotchi
from tictactoe import TicTacToe
from othello import Othello
from dice import Dice
from chessclock import ChessClock
from sand import Sand
from backdrop import Backdrop
from studioclock import StudioClock
import macapps
import firefox

CONFIG_PATH = Path(__file__).resolve().parent / "arcadeos.json"

DEFAULT = {"idle_minutes": 10, "corner_taps": 3, "corner_window": 1.5,
           # sound-activated equalizer: play audio -> party; quiet -> ambient
           "sound_activated": False, "sound_threshold": 0.006, "silence_seconds": 6.0,
           # mirror the board onto a Divoom Pixoo (must be in app mode)
           "pixoo_mirror": False,
           # dedicated Mac-volume pads: bottom-left = down, bottom-right = up.
           # Active in idle/ambient, equalizer, home, and the notification
           # center (set "everywhere" to also override games/deck/etc.).
           "volume_pads": True, "volume_step": 6, "volume_everywhere": False,
           # app-cycle pads: top-left = previous app, top-right = next app,
           # cycling through home + every app. Always on.
           "nav_pads": True,
           # mac-app switch pads (like Cmd-Tab): top edge inside the nav pads.
           # Needs Accessibility permission (macOS prompts on first use).
           "mac_nav_pads": True,
           # firefox tab-switch pads (side edges, below the mac pads).
           "firefox_tab_pads": True}

APPS = [
    # (name, class, icon quad colours [tl, tr, bl, br], position) — 3 cols x 4 rows
    ("games", Arcade, [(0, 180, 0), (200, 0, 0), (200, 180, 0), (0, 60, 220)], (1, 1)),
    ("deck", Deck, [(230, 230, 230)] * 4, (5, 1)),
    ("kopads", KOPads, [(240, 90, 0), (220, 200, 0), (230, 230, 230), (200, 0, 60)], (9, 1)),
    ("seq", Sequencer, [(0, 200, 0), (0, 200, 0), (2, 2, 10), (0, 200, 0)], (1, 4)),
    ("midiviz", MidiViz, [(200, 0, 180), (0, 190, 190), (0, 190, 190), (200, 0, 180)], (5, 4)),
    ("rhythm", Rhythm, [(200, 0, 60), (220, 200, 0), (220, 200, 0), (200, 0, 60)], (9, 4)),
    ("ambient", Ambient, [(0, 40, 120), (0, 60, 160), (0, 60, 160), (0, 40, 120)], (1, 7)),
    ("party", Party, [(0, 220, 0), (255, 220, 0), (255, 60, 0), (180, 0, 255)], (5, 7)),
    ("marquee", Marquee, [(0, 200, 255), (0, 120, 255), (0, 120, 255), (0, 200, 255)], (9, 7)),
    ("pomodoro", Pomodoro, [(255, 70, 40), (255, 70, 40), (0, 200, 90), (0, 200, 90)], (1, 10)),
    ("countdown", Countdown, [(235, 235, 235), (235, 235, 235), (0, 180, 220), (0, 180, 220)], (9, 10)),
    ("weather", Weather, [(120, 200, 255), (255, 210, 0), (120, 200, 255), (180, 220, 255)], (5, 10)),
    ("onair", OnAir, [(220, 0, 0), (220, 0, 0), (0, 180, 60), (0, 180, 60)], (5, 10)),
    ("ytmusic", YTMusic, [(230, 0, 0), (255, 255, 255), (230, 0, 0), (230, 0, 0)], (9, 10)),
    ("doodle", Doodle, [(255, 40, 40), (0, 220, 60), (0, 120, 255), (255, 230, 0)], (5, 10)),
    ("stopwatch", Stopwatch, [(235, 235, 235), (0, 200, 80), (30, 90, 200), (170, 30, 30)], (5, 10)),
    ("worldclock", WorldClock, [(0, 120, 255), (255, 60, 0), (0, 220, 80), (255, 200, 0)], (5, 10)),
    ("pet", Tamagotchi, [(0, 220, 90), (0, 220, 90), (255, 60, 150), (0, 220, 90)], (5, 10)),
    ("ttt", TicTacToe, [(255, 40, 40), (0, 210, 220), (0, 210, 220), (255, 40, 40)], (5, 10)),
    ("othello", Othello, [(240, 240, 240), (40, 100, 255), (40, 100, 255), (240, 240, 240)], (5, 10)),
    ("dice", Dice, [(150, 25, 25), (255, 255, 255), (255, 255, 255), (25, 45, 150)], (5, 10)),
    ("chessclock", ChessClock, [(255, 120, 40), (255, 120, 40), (60, 150, 255), (60, 150, 255)], (5, 10)),
    ("sand", Sand, [(230, 200, 110), (30, 110, 255), (140, 90, 40), (255, 120, 0)], (5, 10)),
    ("backdrop", Backdrop, [(0, 200, 130), (120, 0, 220), (0, 120, 255), (255, 90, 0)], (5, 10)),
    ("studioclock", StudioClock, [(255, 45, 45), (240, 240, 235), (240, 240, 235), (255, 45, 45)], (5, 10)),
]
APP_BY_NAME = {name: cls for name, cls, _i, _p in APPS}
REGISTRY = {name: (name, cls, icon) for name, cls, icon, _p in APPS}   # all buildable apps

# home launcher: a single 3 cols x 5 rows grid of 2x2 icons, laid out from
# these slots (the stored icon positions in the APPS tuples are vestigial).
HOME_SLOTS = [(c, r) for r in (1, 3, 5, 7, 9) for c in (1, 5, 9)]

# apps.json chooses which apps appear on the home grid and in what slot order;
# edited live by the web organizer (http://127.0.0.1:7770/apps.html).
LAYOUT_PATH = Path(__file__).resolve().parent / "apps.json"


def load_layout_names() -> list:
    """Return the ordered list of enabled app names shown on the home grid.

    apps.json (when present) is the source of truth: its "slots" list names the
    enabled apps in order; apps not listed are hidden. With no apps.json every
    registered app is shown, in registry order. The list can be any length —
    the launcher pages it.
    """
    names = None
    if LAYOUT_PATH.exists():
        try:
            names = json.loads(LAYOUT_PATH.read_text()).get("slots")
        except Exception:
            names = None
    if not isinstance(names, list):
        names = [n for n, *_ in APPS]                 # default: all apps
    out, seen = [], set()
    for nm in names:
        if nm in REGISTRY and nm not in seen:
            out.append(nm); seen.add(nm)
    return out


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
        self.home_page = 0
        self.layout_names = load_layout_names()      # slot -> app name (from apps.json)
        self.layout_mtime = LAYOUT_PATH.stat().st_mtime if LAYOUT_PATH.exists() else 0.0
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
        self.muted = False                # dedicated mute pad (middle of bottom row)
        if self.cfg.get("volume_pads"):
            try:
                from volume import Volume, read_muted

                self.volume = Volume()
                self.vol_level = self.volume.level
                self.muted = read_muted()
                threading.Thread(target=self._mute_poll_loop, daemon=True).start()
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
        if name in ("party", "ytmusic") and self.bus is not None:
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
    MUTE_PAD = (6, 11)    # dedicated mute, middle of the bottom row
    HOME_PAD = (6, 0)     # close/home button — returns to the home grid from any app
    APP_PREV = (0, 0)
    APP_NEXT = (11, 0)
    MAC_PREV = (0, 2)     # 2 rows below the arcade-nav corners
    MAC_NEXT = (11, 2)
    FF_PREV = (0, 4)      # 2 rows below the mac pads
    FF_NEXT = (11, 4)

    def _mute_poll_loop(self) -> None:
        from volume import read_muted
        while True:
            if self._volume_active():
                self.muted = read_muted()
            time.sleep(1.5)

    def _volume_active(self) -> bool:
        if self.volume is None:
            return False
        if self.cfg.get("volume_everywhere"):
            return True
        # active where a press isn't otherwise doing interactive work
        return self.in_center or self.app_name in ("home", "ambient", "party", "ytmusic")

    def _placed(self):
        """All enabled apps as (name, cls, icon), in home order (across pages)."""
        return [REGISTRY[n] for n in self.layout_names if n in REGISTRY]

    def _home_pages(self) -> int:
        n = len(self._placed())
        if n <= len(HOME_SLOTS):
            return 1
        per = len(HOME_SLOTS) - 1                      # last slot = page-turn pad
        return (n + per - 1) // per

    def _active(self):
        """Yield (grid_pos, name, cls, icon) for the apps on the current page."""
        placed = self._placed()
        if len(placed) <= len(HOME_SLOTS):
            for i, (nm, cls, icon) in enumerate(placed):
                yield HOME_SLOTS[i], nm, cls, icon
            return
        per = len(HOME_SLOTS) - 1
        page = self.home_page % self._home_pages()
        for i, (nm, cls, icon) in enumerate(placed[page * per:(page + 1) * per]):
            yield HOME_SLOTS[i], nm, cls, icon

    def _cycle_order(self):
        return ["home"] + [nm for nm, _c, _i in self._placed()]

    def _cycle_app(self, delta: int) -> None:
        order = self._cycle_order()
        try:
            i = order.index(self.app_name)
        except ValueError:
            i = 0
        self.auto_ambient_from = None
        self.marquee_return_at = 0.0
        self.enter(order[(i + delta) % len(order)])

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
        # dedicated mute pad (middle of the bottom row)
        if self._volume_active() and (x, y) == self.MUTE_PAD:
            from volume import set_muted
            self.muted = not self.muted
            set_muted(self.muted)
            self.vol_shown_until = now + 1.2
            return
        # app-cycle pads (top corners) — always, except while dismissing alerts
        if self.cfg.get("nav_pads") and not self.in_center and (x, y) in (self.APP_PREV, self.APP_NEXT):
            self._cycle_app(1 if (x, y) == self.APP_NEXT else -1)
            return
        # mac-app switch pads (top edge, inside the nav pads) — like Cmd-Tab
        if self.cfg.get("mac_nav_pads") and not self.in_center and (x, y) in (self.MAC_PREV, self.MAC_NEXT):
            macapps.switch(1 if (x, y) == self.MAC_NEXT else -1)
            self.vol_shown_until = now + 0.6      # brief flash on the pad
            return
        # firefox tab-switch pads (side edges) — like Cmd-Option-Arrow
        if self.cfg.get("firefox_tab_pads") and not self.in_center and (x, y) in (self.FF_PREV, self.FF_NEXT):
            firefox.switch_tab(1 if (x, y) == self.FF_NEXT else -1)
            self.vol_shown_until = now + 0.6
            return
        # close/home pad (top-centre) — leave any app back to the home grid
        if not self.in_center and self.app_name != "home" and (x, y) == self.HOME_PAD:
            self.auto_ambient_from = None
            self.enter("home")
            return
        if self.in_center:                          # a press marks the alert read
            self.center.press(x, y)
            return
        if self.auto_ambient_from:                     # wake from auto-ambient
            back = self.auto_ambient_from
            self.auto_ambient_from = None
            self.enter(back)
            return
        if self.app_name == "ambient":                 # tap the idle clock -> home menu
            self.enter("home")
            return
        if self.app_name == "home":
            if self._home_pages() > 1:              # page-turn pad (last slot)
                tx, ty = HOME_SLOTS[-1]
                if tx - 1 <= x <= tx + 2 and ty <= y <= ty + 1:
                    self.home_page = (self.home_page + 1) % self._home_pages()
                    return
            for (bx, by), name, _cls, _icon in self._active():
                if bx - 1 <= x <= bx + 2 and by <= y <= by + 1:
                    self.enter(name)
                    return
            return
        self.app.on_press(x, y)

    # -- loop ----------------------------------------------------------------
    def update(self, dt):
        now = time.monotonic()
        if LAYOUT_PATH.exists():                        # hot-reload the home layout
            m = LAYOUT_PATH.stat().st_mtime
            if m != self.layout_mtime:
                self.layout_mtime = m
                self.layout_names = load_layout_names()
                log("home layout reloaded from apps.json")
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
        if (self.app_name == "ambient" and loud       # only the idle screen auto-switches,
                and now - self.last_press > 3.0):     # and only when actually idle (not mid-navigation)
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
            for (x, y), _name, _cls, icon in self._active():
                screen.set(x, y, icon[0]); screen.set(x + 1, y, icon[1])
                screen.set(x, y + 1, icon[2]); screen.set(x + 1, y + 1, icon[3])
            pulse = int(40 + 30 * (0.5 + 0.5 * __import__("math").sin(now * 2)))
            pages = self._home_pages()
            if pages > 1:                               # page-turn pad + page dots
                tx, ty = HOME_SLOTS[-1]
                screen.set(tx, ty, (90, 90, 110)); screen.set(tx + 1, ty, (150, 150, 190))
                screen.set(tx, ty + 1, (150, 150, 190)); screen.set(tx + 1, ty + 1, (90, 90, 110))
                cur = self.home_page % pages
                for p in range(pages):
                    screen.set(3 + p, 11, (pulse + 80,) * 3 if p == cur else (30, 30, 30))
            else:
                screen.set(6, 11, (0, pulse, pulse // 2))   # heartbeat
            if self.notify:
                self.notify.draw_overlay(screen, now)
        self._draw_volume(screen, now)              # dedicated volume pads on top
        if self.app_name != "home" and not self.in_center:   # close/home pad (top-centre)
            screen.set(*self.HOME_PAD, (230, 230, 230))
        if self.cfg.get("nav_pads"):                # arcade app prev/next (top corners)
            screen.set(*self.APP_PREV, (180, 60, 220))   # ‹ prev (purple)
            screen.set(*self.APP_NEXT, (180, 60, 220))   # › next
        if self.cfg.get("mac_nav_pads"):            # mac app prev/next (2 rows below nav)
            screen.set(*self.MAC_PREV, (255, 120, 0))    # ‹ mac prev (orange)
            screen.set(*self.MAC_NEXT, (255, 120, 0))    # › mac next
        if self.cfg.get("firefox_tab_pads"):        # firefox tab prev/next (2 rows below mac)
            screen.set(*self.FF_PREV, (0, 200, 220))     # ‹ tab prev (cyan)
            screen.set(*self.FF_NEXT, (0, 200, 220))     # › tab next
        if self.pixoo:
            self.pixoo.set_board_frame(screen.px)

    def _draw_volume(self, screen, now: float) -> None:
        if not self._volume_active():
            return
        dx, dy = self.VOL_DOWN
        ux, uy = self.VOL_UP
        screen.set(dx, dy, (0, 120, 255))           # always lit − (blue)
        screen.set(ux, uy, (0, 230, 80))            # always lit + (green)
        mx, my = self.MUTE_PAD                      # always lit mute (red when muted)
        screen.set(mx, my, (220, 0, 0) if self.muted else (0, 150, 170))
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
