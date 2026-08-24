#!/usr/bin/env python3
"""Party mode — the board dances to live audio.

Captures audio (the EP-133's USB audio stream by default — it's a USB audio
interface! — or any input matching `device_contains` in party.json) and
renders a 12-band log-spaced spectrum analyzer: colour gradient columns,
white peak-hold dots, and a bass-driven background pulse. Auto-gain keeps it
lively at any volume.

  python party.py             # emulator
  (on the board: it's an ArcadeOS app)
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "party.json"

DEFAULT = {
    "device_contains": ["USBAudio", "EP-133", "mic"],
    "bands_hz": [60, 5000],        # log-spaced range across the 12 columns
    "gain_decay": 0.995,           # auto-gain: rolling max decay per frame
    "fall_rows_per_frame": 0.55,   # how fast columns fall
}

SAMPLE_RATE = 48000
BLOCK = 1024


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def column_color(row_from_bottom: int) -> tuple[int, int, int]:
    """green -> yellow -> orange -> red gradient going up."""
    t = row_from_bottom / 11.0
    if t < 0.5:
        k = t / 0.5
        return (int(255 * k), 220, 0)
    k = (t - 0.5) / 0.5
    return (255, int(220 * (1 - k)), 0)


class Party(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.levels = [0.0] * 12       # current column heights (rows)
        self.peaks = [0.0] * 12        # peak-hold positions
        self.peak_t = [0.0] * 12
        self.gain = 1e-6               # rolling max for auto-gain
        self.bass = 0.0
        self.stream = None
        self.status = "starting audio…"
        self.buf = None
        self.lock = threading.Lock()
        self.next_try = 0.0
        self._open_stream()

    @property
    def busy(self):
        return any(v > 0.5 for v in self.levels)   # music playing = don't idle away

    # -- audio ----------------------------------------------------------------
    def _pick_device(self):
        import sounddevice as sd

        devices = sd.query_devices()
        for key in self.cfg["device_contains"]:
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0 and key.lower() in d["name"].lower():
                    return i, d["name"]
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                return i, d["name"]
        return None, None

    def _open_stream(self):
        now = time.monotonic()
        if self.stream is not None or now < self.next_try:
            return
        self.next_try = now + 5.0
        try:
            import numpy as np
            import sounddevice as sd

            idx, name = self._pick_device()
            if idx is None:
                self.status = "no audio input found"
                return
            self._np = np

            def callback(indata, frames, t, status):
                mono = indata.mean(axis=1) if indata.ndim > 1 else indata[:, 0]
                with self.lock:
                    self.buf = mono.copy()

            self.stream = sd.InputStream(device=idx, channels=1,
                                         samplerate=SAMPLE_RATE, blocksize=BLOCK,
                                         callback=callback)
            self.stream.start()
            self.status = f"listening: {name}"
            log(f"party: {self.status}")
        except Exception as exc:  # noqa: BLE001
            self.status = f"audio unavailable: {type(exc).__name__}"
            log(f"party: {self.status} ({exc})")
            self.stream = None

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop(); self.stream.close()
            except Exception:
                pass
            self.stream = None

    # -- analysis ---------------------------------------------------------------
    def _analyze(self, samples) -> list[float]:
        np = self._np
        windowed = samples * np.hanning(len(samples))
        mag = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(len(samples), 1.0 / SAMPLE_RATE)
        lo, hi = self.cfg["bands_hz"]
        edges = np.geomspace(lo, hi, 13)
        bands = []
        for b in range(12):
            sel = (freqs >= edges[b]) & (freqs < edges[b + 1])
            bands.append(float(mag[sel].mean()) if sel.any() else 0.0)
        return bands

    def update(self, dt):
        self._open_stream()
        with self.lock:
            samples, self.buf = self.buf, None
        if samples is None:
            for i in range(12):
                self.levels[i] = max(0.0, self.levels[i] - self.cfg["fall_rows_per_frame"])
            self.bass *= 0.85
            return
        bands = self._analyze(samples)
        self.gain = max(max(bands), self.gain * self.cfg["gain_decay"], 1e-6)
        now = time.monotonic()
        for i, v in enumerate(bands):
            h = min(1.0, v / self.gain) ** 0.6 * 12.0
            if h >= self.levels[i]:
                self.levels[i] = h
            else:
                self.levels[i] = max(h, self.levels[i] - self.cfg["fall_rows_per_frame"])
            if self.levels[i] >= self.peaks[i]:
                self.peaks[i] = self.levels[i]
                self.peak_t[i] = now
            elif now - self.peak_t[i] > 0.6:
                self.peaks[i] = max(0.0, self.peaks[i] - 0.35)
        self.bass = 0.75 * self.bass + 0.25 * min(1.0, (bands[0] + bands[1]) / (2 * self.gain))

    def draw(self, screen):
        b = int(14 * self.bass)
        screen.clear((b, 0, b // 2))               # bass-driven purple pulse
        for col in range(12):
            h = self.levels[col]
            for row in range(int(round(h))):
                if row < 12:
                    screen.set(col, 11 - row, column_color(row))
            pk = int(round(self.peaks[col]))
            if pk >= 1:
                screen.set(col, max(0, 12 - pk), (230, 230, 230))
        if self.stream is None and int(time.monotonic() * 2) % 2:
            for x, y in ((0, 0), (11, 0)):
                screen.set(x, y, (120, 0, 0))


if __name__ == "__main__":
    run(Party)
