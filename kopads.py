#!/usr/bin/env python3
"""KO-pads — play a Teenage Engineering EP-133 K.O. II from the Arcade Coder.

The 12x12 grid becomes four 3-row bands = EP-133 groups A/B/C/D; the 12
columns are the 12 pads of each group. Pressing a pad sends the matching MIDI
note (A: 36-47, B: 48-59, C: 60-71, D: 72-83 — the EP-133's documented
mapping; it receives on all channels by default).

Connect the EP-133 to this computer over USB-C. The app finds its MIDI port
automatically (and keeps retrying if it's not plugged in yet — the board
pulses dim red until MIDI is up).

  python kopads.py            # emulator (clicks send real MIDI too)
  python kopads_hw.py         # real board via the app bundle

Optional kopads.json overrides bands, notes, velocity, and colours.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "kopads.json"

DEFAULT = {
    "port_contains": ["EP-133", "EP133", "K.O", "KO II"],
    "channel": 0,           # 0-based; EP-133 receives on all channels
    "velocity": 100,
    "note_seconds": 0.25,
    "bands": [
        {"group": "A", "base_note": 36, "color": [240, 90, 0]},
        {"group": "B", "base_note": 48, "color": [220, 200, 0]},
        {"group": "C", "base_note": 60, "color": [230, 230, 230]},
        {"group": "D", "base_note": 72, "color": [200, 0, 60]},
    ],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class PadButton:
    """A free-form button in custom layout mode."""

    def __init__(self, spec: dict) -> None:
        self.x, self.y = int(spec["x"]), int(spec["y"])
        self.w, self.h = int(spec.get("w", 2)), int(spec.get("h", 2))
        self.label = spec.get("label", "pad")
        self.color = tuple(spec.get("color", [240, 90, 0]))
        self.midi = spec.get("midi", {})
        self.toggled = False

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h


class KOPads(Game):
    fps = 10

    def start(self):
        self._load()
        self.port = None
        self.next_port_try = 0.0
        self.next_mtime_check = 0.0
        self.active: dict[int, float] = {}   # note -> off time
        self.flashes: dict[tuple[int, int], float] = {}  # (band, col) -> until
        self._open_port(time.monotonic())
        try:
            from kopads_web import ensure_server

            ensure_server()
        except Exception as exc:  # noqa: BLE001
            log(f"config editor not started: {exc!r}")

    def _load(self) -> None:
        cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text()))
            self.cfg_mtime = CONFIG_PATH.stat().st_mtime
        else:
            self.cfg_mtime = 0.0
        self.cfg = cfg
        self.overrides = {
            (o["band"], o["col"]): o for o in cfg.get("overrides", [])
        }
        self.custom = (
            [PadButton(b) for b in cfg.get("buttons", [])]
            if cfg.get("layout") == "custom" else None
        )

    # -- MIDI plumbing -------------------------------------------------------
    def _open_port(self, now: float) -> None:
        if now < self.next_port_try:
            return
        self.next_port_try = now + 5.0
        try:
            import mido

            names = mido.get_output_names()
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI backend unavailable: {exc!r}")
            return
        wanted = [n for n in names if any(k.lower() in n.lower() for k in self.cfg["port_contains"])]
        name = wanted[0] if wanted else (names[0] if names else None)
        if name is None:
            return
        try:
            self.port = mido.open_output(name)
            log(f"MIDI out: {name}")
        except Exception as exc:  # noqa: BLE001
            log(f"could not open MIDI port {name!r}: {exc!r}")

    def _send_msg(self, msg) -> None:
        if self.port is None:
            return
        try:
            self.port.send(msg)
        except Exception as exc:  # noqa: BLE001
            log(f"MIDI send failed ({exc!r}); reopening port")
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.next_port_try = 0.0

    def _send(self, kind: str, note: int, velocity: int | None = None,
              channel: int | None = None) -> None:
        import mido

        self._send_msg(mido.Message(
            kind, note=note,
            velocity=self.cfg["velocity"] if velocity is None else velocity,
            channel=self.cfg["channel"] if channel is None else channel))

    def _send_cc(self, cc: int, value: int, channel: int | None = None) -> None:
        import mido

        self._send_msg(mido.Message(
            "control_change", control=cc, value=value,
            channel=self.cfg["channel"] if channel is None else channel))

    def _fire(self, midi: dict, now: float) -> str:
        """Send a custom-button MIDI event; returns a log description."""
        channel = midi.get("channel")
        if midi.get("type") == "cc":
            value = int(midi.get("value", 127))
            self._send_cc(int(midi.get("cc", 1)), value, channel)
            return f"cc {midi.get('cc', 1)} = {value}"
        note = int(midi.get("note", 60))
        self._send("note_on", note, midi.get("velocity"), channel)
        self.active[(channel if channel is not None else self.cfg["channel"], note)] = (
            now + float(midi.get("note_seconds", self.cfg["note_seconds"])))
        return f"note {note}"

    # -- game hooks ----------------------------------------------------------
    def on_press(self, x, y):
        now = time.monotonic()
        if self.custom is not None:
            for btn in self.custom:
                if not btn.contains(x, y):
                    continue
                midi = dict(btn.midi)
                if midi.get("type") == "cc" and midi.get("mode") == "toggle":
                    btn.toggled = not btn.toggled
                    midi["value"] = midi.get("on_value", 127) if btn.toggled else midi.get("off_value", 0)
                desc = self._fire(midi, now)
                log(f"button '{btn.label}': {desc}" + ("" if self.port else "  (no MIDI device yet)"))
                self.flashes[("btn", id(btn))] = now + 0.22
                return
            return
        band = min(y // 3, 3)
        spec = self.cfg["bands"][band]
        override = self.overrides.get((band, x), {})
        note = override.get("note", spec["base_note"] + x)
        pad_names = [".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        log(f"group {spec['group']} pad {pad_names[x] if x < 12 else x} -> note {note}"
            + ("" if self.port else "  (no MIDI device yet)"))
        self._send("note_on", note)
        self.active[(self.cfg["channel"], note)] = time.monotonic() + float(self.cfg["note_seconds"])
        self.flashes[(band, x)] = time.monotonic() + 0.22

    def update(self, dt):
        now = time.monotonic()
        if self.port is None:
            self._open_port(now)
        if now >= self.next_mtime_check:
            self.next_mtime_check = now + 1.0
            try:
                if CONFIG_PATH.exists() and CONFIG_PATH.stat().st_mtime != self.cfg_mtime:
                    self._load()
                    log("kopads.json changed — reloaded")
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                log(f"config reload failed: {exc!r}")
                self.cfg_mtime = CONFIG_PATH.stat().st_mtime
        try:
            from kopads_web import test_notes

            while not test_notes.empty():
                ev = test_notes.get_nowait()
                if isinstance(ev, dict):
                    log(f"test event: {self._fire(ev, now)}")
                else:
                    log(f"test note {ev}")
                    self._send("note_on", ev)
                    self.active[(self.cfg["channel"], ev)] = now + float(self.cfg["note_seconds"])
        except Exception:
            pass
        for (channel, note), off_at in list(self.active.items()):
            if now >= off_at:
                self._send("note_off", note, channel=channel)
                del self.active[(channel, note)]
        self.flashes = {k: t for k, t in self.flashes.items() if t > now}

    def draw(self, screen):
        now = time.monotonic()
        if self.custom is not None:
            screen.clear((3, 3, 5))
            for btn in self.custom:
                color = btn.color
                if btn.midi.get("type") == "cc" and btn.midi.get("mode") == "toggle":
                    color = btn.color if btn.toggled else tuple(v // 4 for v in btn.color)
                if ("btn", id(btn)) in self.flashes:
                    color = (255, 255, 255)
                for dy in range(btn.h):
                    for dx in range(btn.w):
                        if btn.x + dx < 12 and btn.y + dy < 12:
                            screen.set(btn.x + dx, btn.y + dy, color)
            if self.port is None and int(now * 2) % 2:
                for x, y in ((0, 0), (11, 0), (0, 11), (11, 11)):
                    screen.set(x, y, (120, 0, 0))
            return
        for band in range(4):
            base = self.cfg["bands"][band]["color"]
            for col in range(12):
                # dim base colour; brighter guide columns every 3 pads
                scale = 32 if col % 3 else 55
                override = self.overrides.get((band, col))
                src_color = (override or {}).get("color", base)
                color = tuple(v * scale // 100 for v in src_color)
                if (band, col) in self.flashes:
                    color = (255, 255, 255)
                for row in range(3):
                    screen.set(col, band * 3 + row, color)
        if self.port is None and int(now * 2) % 2:  # pulse corners: no MIDI
            for x, y in ((0, 0), (11, 0), (0, 11), (11, 11)):
                screen.set(x, y, (120, 0, 0))


if __name__ == "__main__":
    run(KOPads)
