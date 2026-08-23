#!/usr/bin/env python3
"""MIDI visualizer — the Arcade Coder reacts while you play the EP-133.

Listens to the EP-133's MIDI output (USB). Every pad you play spawns a
colour-coded ripple on the board at that pad's position in the A/B/C/D band
layout (A 36-47 orange, B 48-59 yellow, C 60-71 white, D 72-83 red), with
brightness following velocity. The FX knobs (CC 12/13) tint the background.

  python midiviz.py           # emulator preview
  python midiviz_hw.py        # real board via the app bundle
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

PORT_CONTAINS = ["EP-133", "EP133", "K.O", "KO II"]
BAND_COLORS = [(240, 90, 0), (220, 200, 0), (230, 230, 230), (200, 0, 60)]
RIPPLE_SECONDS = 1.1
RIPPLE_SPEED = 9.0      # cells per second
GLOW_SECONDS = 0.45


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def note_position(note: int) -> tuple[float, float, tuple[int, int, int]]:
    """Map a note to a board position + colour via the EP-133 band layout."""
    if 36 <= note <= 83:
        band = (note - 36) // 12
        col = (note - 36) % 12
        return float(col), band * 3 + 1.0, BAND_COLORS[band]
    # out-of-range notes: place by pitch class / octave, cyan-ish
    return float(note % 12), float((note // 12) % 12), (0, 190, 190)


class Ripple:
    def __init__(self, x: float, y: float, color, velocity: int, t0: float) -> None:
        self.x, self.y, self.color, self.t0 = x, y, color, t0
        self.strength = 0.35 + 0.65 * (velocity / 127.0)


class MidiViz(Game):
    fps = 14

    def start(self):
        self.port = None
        self.next_port_try = 0.0
        self.ripples: list[Ripple] = []
        self.tint = [0.0, 0.0]      # CC12, CC13 as 0..1
        self.notes_seen = 0
        self.last_note_t = 0.0
        self._open_port(time.monotonic())

    def _open_port(self, now: float) -> None:
        if now < self.next_port_try:
            return
        self.next_port_try = now + 5.0
        try:
            import mido

            names = mido.get_input_names()
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI backend unavailable: {exc!r}")
            return
        wanted = [n for n in names if any(k.lower() in n.lower() for k in PORT_CONTAINS)]
        name = wanted[0] if wanted else (names[0] if names else None)
        if name is None:
            return
        try:
            self.port = mido.open_input(name)
            log(f"MIDI in: {name} — play the EP-133!")
        except Exception as exc:  # noqa: BLE001
            log(f"could not open MIDI input {name!r}: {exc!r}")

    @property
    def busy(self):
        return time.monotonic() - self.last_note_t < 120

    def on_press(self, x, y):
        # pressing the board makes light too — a splash where you touch
        self.ripples.append(Ripple(x, y, (0, 190, 190), 110, time.monotonic()))

    def update(self, dt):
        now = time.monotonic()
        if self.port is None:
            self._open_port(now)
            return
        try:
            for msg in self.port.iter_pending():
                if msg.type == "note_on" and msg.velocity > 0:
                    x, y, color = note_position(msg.note)
                    self.ripples.append(Ripple(x, y, color, msg.velocity, now))
                    self.notes_seen += 1
                    self.last_note_t = now
                    if self.notes_seen % 25 == 1:
                        log(f"notes seen: {self.notes_seen}")
                elif msg.type == "control_change" and msg.control in (12, 13):
                    self.tint[msg.control - 12] = msg.value / 127.0
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI read failed ({exc!r}); reopening")
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.next_port_try = 0.0
        self.ripples = [r for r in self.ripples if now - r.t0 < RIPPLE_SECONDS]

    def draw(self, screen):
        now = time.monotonic()
        # background tint from the FX knobs (very dim)
        bg = (int(10 * self.tint[0]), 0, int(10 * self.tint[1]))
        buf = [[float(bg[0]), float(bg[1]), float(bg[2])] for _ in range(144)]
        for r in self.ripples:
            age = now - r.t0
            fade = max(0.0, 1.0 - age / RIPPLE_SECONDS) * r.strength
            radius = age * RIPPLE_SPEED
            for i in range(144):
                d = math.hypot(i % 12 - r.x, i // 12 - r.y)
                ring = max(0.0, 1.0 - abs(d - radius))          # expanding ring
                glow = max(0.0, 1.0 - age / GLOW_SECONDS) * max(0.0, 1.0 - d / 1.6)
                k = fade * max(ring, glow)
                if k > 0:
                    for c in range(3):
                        buf[i][c] += r.color[c] * k
        for i in range(144):
            screen.px[i] = tuple(min(255, int(v)) for v in buf[i])
        if self.port is None and int(now * 2) % 2:
            for x, y in ((0, 0), (11, 0), (0, 11), (11, 11)):
                screen.set(x, y, (120, 0, 0))


if __name__ == "__main__":
    run(MidiViz)
