#!/usr/bin/env python3
"""Rhythm game — falling notes, and the EP-133 IS the instrument.

Four 3-wide lanes; notes fall toward the hit line (row 10-11). Press the lane
as a note lands: a good hit fires that lane's EP-133 pad, so playing
accurately builds the beat out loud. Misses stay silent and cost health
(top row). Tempo and density climb as you survive.

BLE adds ~0.2s of input latency; `offset` in rhythm.json compensates and the
judgment windows are generous. Tune offset if hits feel consistently early
or late (bigger offset = you can press later).

  python rhythm.py            # emulator (tighter timing, real MIDI)
  python rhythm_hw.py         # real board via the app bundle
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "rhythm.json"
PORT_CONTAINS = ["EP-133", "EP133", "K.O", "KO II"]

DEFAULT = {
    "bpm_start": 80,
    "bpm_max": 140,
    "lane_notes": [36, 38, 42, 39],
    "lane_colors": [[240, 90, 0], [220, 200, 0], [0, 190, 190], [200, 0, 60]],
    "channel": 0,
    "velocity": 110,
    "offset": 0.20,          # expected input latency (s)
    "perfect": 0.14,
    "good": 0.30,
    "fall_rows_per_sec": 6.0,
}

STEPS = 12  # sixteenths per bar

# per-difficulty pools of (step, lane) patterns for one bar
PATTERNS = [
    # sparse
    [[(0, 0), (6, 1)], [(0, 0), (4, 2), (8, 1)], [(0, 3), (6, 0)]],
    # medium
    [[(0, 0), (3, 2), (6, 1), (9, 2)], [(0, 0), (4, 1), (6, 0), (10, 3)],
     [(0, 3), (2, 2), (6, 1), (8, 2), (10, 0)]],
    # busy
    [[(0, 0), (2, 2), (4, 1), (6, 0), (8, 2), (10, 1)],
     [(0, 0), (3, 1), (4, 2), (6, 0), (7, 2), (9, 1), (10, 2)],
     [(0, 3), (2, 0), (4, 1), (5, 2), (6, 3), (8, 0), (10, 1), (11, 2)]],
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Note:
    __slots__ = ("lane", "hit_time", "state")

    def __init__(self, lane: int, hit_time: float) -> None:
        self.lane = lane
        self.hit_time = hit_time
        self.state = "falling"   # falling | hit | missed


class Rhythm(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        else:
            CONFIG_PATH.write_text(json.dumps(DEFAULT, indent=2) + "\n")
        self.port = None
        self.next_port_try = 0.0
        self.pending_off: list[tuple[float, int]] = []
        self.reset(time.monotonic())

    def reset(self, now: float) -> None:
        self.notes: list[Note] = []
        self.bpm = self.cfg["bpm_start"]
        self.bar = 0
        self.next_bar_time = now + 2.5      # lead-in
        self.health = 12
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.flash: dict[int, tuple[str, float]] = {}   # lane -> (kind, until)
        self.over_at = 0.0
        log(f"rhythm: new run — {self.bpm} bpm, hit the lane when the light lands!")

    # -- MIDI ---------------------------------------------------------------
    def _open_port(self, now: float) -> None:
        if self.port is not None or now < self.next_port_try:
            return
        self.next_port_try = now + 5.0
        try:
            import mido

            names = mido.get_output_names()
        except Exception:
            return
        wanted = [n for n in names if any(k.lower() in n.lower() for k in PORT_CONTAINS)]
        name = wanted[0] if wanted else (names[0] if names else None)
        if name:
            try:
                self.port = mido.open_output(name)
                log(f"MIDI out: {name}")
            except Exception as exc:  # noqa: BLE001
                log(f"could not open {name!r}: {exc!r}")

    def _play(self, lane: int, now: float) -> None:
        if self.port is None:
            return
        import mido

        note = self.cfg["lane_notes"][lane]
        try:
            self.port.send(mido.Message("note_on", note=note,
                                        velocity=self.cfg["velocity"],
                                        channel=self.cfg["channel"]))
            self.pending_off.append((now + 0.12, note))
        except Exception:
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.next_port_try = 0.0

    # -- chart --------------------------------------------------------------
    def _spawn_bar(self, start_time: float) -> None:
        difficulty = min(2, self.bar // 6)
        pattern = random.choice(PATTERNS[difficulty])
        step_dur = 60.0 / self.bpm / 4.0
        for step, lane in pattern:
            self.notes.append(Note(lane, start_time + step * step_dur))
        self.bar += 1
        if self.bar % 2 == 0:
            self.bpm = min(self.cfg["bpm_max"], self.bpm + 2)

    # -- input --------------------------------------------------------------
    def on_press(self, x, y):
        now = time.monotonic()
        if self.over_at:
            if now - self.over_at > 1.5:
                self.reset(now)
            return
        lane = min(3, x // 3)
        press_time = now - self.cfg["offset"]
        candidates = [n for n in self.notes
                      if n.lane == lane and n.state == "falling"
                      and abs(press_time - n.hit_time) <= self.cfg["good"]]
        if not candidates:
            return                      # stray press: no penalty (BLE jitter mercy)
        note = min(candidates, key=lambda n: abs(press_time - n.hit_time))
        err = abs(press_time - note.hit_time)
        note.state = "hit"
        self._play(lane, now)
        if err <= self.cfg["perfect"]:
            self.score += 2
            kind = "perfect"
        else:
            self.score += 1
            kind = "good"
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        if self.combo % 8 == 0 and self.health < 12:
            self.health += 1
        self.flash[lane] = (kind, now + 0.3)
        log(f"{kind}! lane {lane} (±{err*1000:.0f}ms) score {self.score} combo {self.combo}")

    # -- loop ---------------------------------------------------------------
    def update(self, dt):
        now = time.monotonic()
        self._open_port(now)
        for off_t, note in list(self.pending_off):
            if now >= off_t:
                try:
                    import mido

                    if self.port:
                        self.port.send(mido.Message("note_off", note=note,
                                                    channel=self.cfg["channel"]))
                except Exception:
                    pass
                self.pending_off.remove((off_t, note))
        if self.over_at:
            return
        while self.next_bar_time < now + 3.0:   # keep 3s of chart ahead
            self._spawn_bar(self.next_bar_time)
            self.next_bar_time += STEPS * (60.0 / self.bpm / 4.0)
        for n in self.notes:
            if n.state == "falling" and now - self.cfg["offset"] - n.hit_time > self.cfg["good"]:
                n.state = "missed"
                self.combo = 0
                self.health -= 1
                self.flash[n.lane] = ("miss", now + 0.35)
        self.notes = [n for n in self.notes if n.state == "falling"
                      or now - n.hit_time < 0.4]
        if self.health <= 0:
            self.over_at = now
            log(f"game over — score {self.score}, best combo {self.best_combo}")

    def draw(self, screen):
        now = time.monotonic()
        if self.over_at:
            screen.clear()
            for i in range(min(self.score, 144)):
                screen.set(i % 12, i // 12, (0, 180, 0))
            if int(now * 2) % 2:
                for x in range(12):
                    screen.set(x, 11, (0, 60, 220))   # press to restart
            return
        screen.clear((2, 2, 5))
        speed = self.cfg["fall_rows_per_sec"]
        for lane in range(4):
            color = tuple(self.cfg["lane_colors"][lane])
            x0 = lane * 3
            # hit line
            fl = self.flash.get(lane)
            if fl and now < fl[1]:
                line = {"perfect": (255, 255, 255), "good": (0, 220, 0),
                        "miss": (220, 0, 0)}[fl[0]]
            else:
                line = tuple(v // 6 for v in color)
            for dx in range(3):
                screen.set(x0 + dx, 11, line)
            # falling notes
            for n in self.notes:
                if n.lane != lane or n.state != "falling":
                    continue
                y = 11 - (n.hit_time - now) * speed
                if 0 <= y < 12:
                    bright = color if y > 8 else tuple(int(v * 0.75) for v in color)
                    for dx in range(3):
                        screen.set(x0 + dx, int(y), bright)
        # health bar overlays the top row
        for x in range(12):
            if x < self.health:
                screen.set(x, 0, (0, 70, 10) if screen.get(x, 0) == (2, 2, 5) else screen.get(x, 0))
            else:
                screen.set(x, 0, (60, 0, 0))


if __name__ == "__main__":
    run(Rhythm)
