#!/usr/bin/env python3
"""Step sequencer — the Arcade Coder drives the EP-133 K.O. II.

Rows 0-9 are ten tracks (each a MIDI note, default EP-133 group A pads),
columns are 12 sixteenth-note steps. Tap cells to toggle steps; a playhead
sweeps the grid and fires the MIDI notes with millisecond timing (a dedicated
thread, independent of the display's frame rate).

Bottom row: [0-1] play/stop (pulses on the beat while playing),
[3] tempo -5, [4] tempo +5, [11] clear pattern (press twice).

Pattern + settings live in seq.json (auto-saved, hot-editable).

  python seq.py             # emulator
  python seq_hw.py          # real board via the app bundle
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "seq.json"
PORT_CONTAINS = ["EP-133", "EP133", "K.O", "KO II"]

STEPS = 12
NTRACKS = 10
TRACK_COLORS = [
    (240, 90, 0), (220, 200, 0), (0, 200, 0), (0, 190, 190), (0, 90, 240),
    (150, 0, 220), (255, 60, 120), (200, 0, 0), (230, 230, 230), (120, 200, 60),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def default_config() -> dict:
    return {
        "bpm": 120,
        "channel": 0,
        "velocity": 110,
        "tracks": [{"note": 36 + i, "color": list(TRACK_COLORS[i])} for i in range(NTRACKS)],
        "pattern": [[0] * STEPS for _ in range(NTRACKS)],
    }


class SeqState:
    """Shared between the UI game and the timing thread."""

    def __init__(self) -> None:
        self.cfg = default_config()
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception as exc:  # noqa: BLE001
                log(f"seq.json unreadable, using defaults: {exc!r}")
        self.playing = False
        self.step = 0
        self.last_beat = 0.0
        self.port = None
        self.next_port_try = 0.0
        self.dirty_at = 0.0
        self.lock = threading.Lock()

    # -- MIDI ---------------------------------------------------------------
    def open_port(self, now: float) -> None:
        if self.port is not None or now < self.next_port_try:
            return
        self.next_port_try = now + 5.0
        try:
            import mido

            names = mido.get_output_names()
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI backend unavailable: {exc!r}")
            return
        wanted = [n for n in names if any(k.lower() in n.lower() for k in PORT_CONTAINS)]
        name = wanted[0] if wanted else (names[0] if names else None)
        if name is None:
            return
        try:
            self.port = __import__("mido").open_output(name)
            log(f"MIDI out: {name}")
        except Exception as exc:  # noqa: BLE001
            log(f"could not open MIDI port {name!r}: {exc!r}")

    def send(self, kind: str, note: int) -> None:
        if self.port is None:
            return
        import mido

        try:
            self.port.send(mido.Message(kind, note=note, velocity=self.cfg["velocity"],
                                        channel=self.cfg["channel"]))
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI send failed ({exc!r}); reopening")
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.next_port_try = 0.0

    def fire_step(self, step: int) -> list[int]:
        """Send note_on for every armed track at `step`; returns fired notes."""
        fired = []
        with self.lock:
            rows = [(t["note"], self.cfg["pattern"][i][step])
                    for i, t in enumerate(self.cfg["tracks"])]
        for note, armed in rows:
            if armed:
                self.send("note_on", note)
                fired.append(note)
        return fired

    # -- persistence --------------------------------------------------------
    def mark_dirty(self) -> None:
        self.dirty_at = time.monotonic()

    def maybe_save(self, now: float) -> None:
        if self.dirty_at and now - self.dirty_at > 1.0:
            self.dirty_at = 0.0
            with self.lock:
                CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
            log("pattern saved")


class Ticker(threading.Thread):
    """Precise step clock: fires MIDI independent of the display loop."""

    def __init__(self, state: SeqState) -> None:
        super().__init__(daemon=True)
        self.state = state
        self.pending_off: list[tuple[float, int]] = []

    def run(self) -> None:
        s = self.state
        next_t = time.monotonic()
        while True:
            now = time.monotonic()
            for off_t, note in list(self.pending_off):
                if now >= off_t:
                    s.send("note_off", note)
                    self.pending_off.remove((off_t, note))
            if not s.playing:
                next_t = now
                time.sleep(0.01)
                continue
            if now >= next_t:
                fired = s.fire_step(s.step)
                for note in fired:
                    self.pending_off.append((now + 0.12, note))
                if s.step % 4 == 0:
                    s.last_beat = now
                s.step = (s.step + 1) % STEPS
                step_dur = 60.0 / max(40, min(240, s.cfg["bpm"])) / 4.0
                next_t += step_dur
                if next_t < now - 0.5:      # fell far behind (sleep/suspend)
                    next_t = now + step_dur
            wait = next_t - time.monotonic() - 0.002
            time.sleep(min(0.004, max(0.0005, wait)) if s.playing else 0.004)


STATE = SeqState()
TICKER: Ticker | None = None


class Sequencer(Game):
    fps = 15

    def start(self):
        global TICKER
        self.s = STATE
        if TICKER is None:
            TICKER = Ticker(STATE)
            TICKER.start()
        self.clear_armed_at = 0.0
        log(f"sequencer up — {self.s.cfg['bpm']} bpm, "
            f"{sum(map(sum, self.s.cfg['pattern']))} steps armed")

    def on_press(self, x, y):
        s = self.s
        now = time.monotonic()
        if y < NTRACKS:
            with s.lock:
                s.cfg["pattern"][y][x] ^= 1
            s.mark_dirty()
            return
        if y == 11:
            if x in (0, 1):
                s.playing = not s.playing
                if not s.playing:
                    s.step = 0
                log("play" if s.playing else "stop")
            elif x == 3:
                s.cfg["bpm"] = max(40, s.cfg["bpm"] - 5)
                s.mark_dirty(); log(f"bpm {s.cfg['bpm']}")
            elif x == 4:
                s.cfg["bpm"] = min(240, s.cfg["bpm"] + 5)
                s.mark_dirty(); log(f"bpm {s.cfg['bpm']}")
            elif x == 11:
                if now - self.clear_armed_at < 3.0:
                    with s.lock:
                        s.cfg["pattern"] = [[0] * STEPS for _ in range(NTRACKS)]
                    s.mark_dirty()
                    self.clear_armed_at = 0.0
                    log("pattern cleared")
                else:
                    self.clear_armed_at = now
                    log("press clear again to wipe the pattern")

    def update(self, dt):
        now = time.monotonic()
        self.s.open_port(now)
        self.s.maybe_save(now)

    def draw(self, screen):
        s = self.s
        now = time.monotonic()
        play_col = s.step if s.playing else -1
        with s.lock:
            pattern = [row[:] for row in s.cfg["pattern"]]
        for t in range(NTRACKS):
            color = tuple(s.cfg["tracks"][t].get("color", TRACK_COLORS[t]))
            for x in range(STEPS):
                if pattern[t][x]:
                    c = color
                    if x == play_col:
                        c = tuple(min(255, v + 120) for v in color)
                elif x == play_col:
                    c = (22, 22, 26)
                else:
                    c = tuple(v // 14 for v in color)
                screen.set(x, t, c)
        for x in range(STEPS):                      # separator row
            screen.set(x, 10, (0, 0, 0))
        # transport row
        if s.playing:
            pulse = max(0.0, 1.0 - (now - s.last_beat) * 3.5)
            g = 80 + int(160 * pulse)
            play = (0, g, 0)
        else:
            play = (60, 8, 8)
        screen.set(0, 11, play); screen.set(1, 11, play)
        screen.set(3, 11, (0, 40, 120))             # tempo -
        screen.set(4, 11, (0, 90, 220))             # tempo +
        armed = now - self.clear_armed_at < 3.0
        screen.set(11, 11, (200, 0, 0) if armed and int(now * 3) % 2 else (40, 5, 5))
        if s.port is None and int(now * 2) % 2:
            screen.set(5, 11, (120, 0, 0)); screen.set(6, 11, (120, 0, 0))


if __name__ == "__main__":
    run(Sequencer)
