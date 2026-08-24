#!/usr/bin/env python3
"""Party mode — the board is a live spectrum analyzer / equalizer.

Two audio sources (party.json "source"):
  "system" (default): whatever the Mac is playing — Spotify, YouTube, the
      EP-133 through speakers — captured digitally via ScreenCaptureKit
      (sysaudio_helper, built from sysaudio.swift; needs the Screen Recording
      permission for the app bundle). No microphone, no loopback drivers.
  "input": an audio input device (the EP-133's USB audio stream by default,
      or anything matching `device_contains`).

If the system source can't start (permission missing), party mode falls back
to the input source and keeps retrying system every 10s.

  python party.py             # emulator
  (on the board: it's an ArcadeOS app)
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "party.json"
HELPER = ROOT / "sysaudio_helper"

DEFAULT = {
    "source": "system",
    "device_contains": ["USBAudio", "EP-133", "mic"],
    "bands_hz": [60, 5000],        # log-spaced range across the 12 columns
    "gain_decay": 0.995,           # auto-gain: rolling max decay per frame
    "fall_rows_per_frame": 0.55,   # how fast columns fall
    "palette": "rainbow",          # "rainbow" (animated per-band hue) or "heat"
    "rainbow_speed": 0.22,         # hue rotations per second
}

SAMPLE_RATE = 48000
BLOCK = 1024


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


import colorsys


def heat_color(row_from_bottom: int) -> tuple[int, int, int]:
    """green -> yellow -> orange -> red gradient going up (classic VU)."""
    t = row_from_bottom / 11.0
    if t < 0.5:
        k = t / 0.5
        return (int(255 * k), 220, 0)
    k = (t - 0.5) / 0.5
    return (255, int(220 * (1 - k)), 0)


def rainbow_color(col: int, row_from_bottom: int, phase: float) -> tuple[int, int, int]:
    """Each column its own hue (a full rainbow across the 12 bands), rotating
    over time. Vivid: high brightness floor so even low cells glow, and the
    top cells push toward white-hot for extra punch."""
    hue = (col / 12.0 + phase) % 1.0
    t = row_from_bottom / 11.0
    v = 0.78 + 0.22 * t                 # bright everywhere, full at the top
    s = 1.0 - 0.35 * t * t              # tips go white-hot
    r, g, b = colorsys.hsv_to_rgb(hue, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


# kept for backward-compat / other callers
def column_color(row_from_bottom: int) -> tuple[int, int, int]:
    return heat_color(row_from_bottom)


class Party(Game):
    fps = 15

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.levels = [0.0] * 12
        self.peaks = [0.0] * 12
        self.peak_t = [0.0] * 12
        self.gain = 1e-6
        self.bass = 0.0
        self.prev_bass = 0.0
        self.flash = 0.0              # beat-strobe intensity, decays each frame
        self.stream = None            # sounddevice input stream
        self.helper = None            # sysaudio subprocess
        self.active_source = None     # "system" | "input" | None
        self.status = "starting audio…"
        self.buf = None
        self.lock = threading.Lock()
        self.next_try = 0.0
        import numpy as np

        self._np = np
        self._open_audio()

    @property
    def busy(self):
        return any(v > 0.5 for v in self.levels)

    # -- system-audio source ---------------------------------------------------
    def _open_system(self) -> bool:
        if not HELPER.exists():
            self.status = "sysaudio_helper missing (run: swiftc -O sysaudio.swift -o sysaudio_helper)"
            return False
        try:
            self.helper = subprocess.Popen([str(HELPER)], stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
        except OSError as exc:
            self.status = f"helper failed to launch: {exc}"
            return False
        threading.Thread(target=self._read_helper, daemon=True).start()
        threading.Thread(target=self._read_helper_err, daemon=True).start()
        self.active_source = "system"
        self.status = "system audio (starting…)"
        return True

    def _read_helper(self) -> None:
        proc = self.helper
        np = self._np
        pending = b""
        want = BLOCK * 4
        while proc and proc.poll() is None:
            chunk = proc.stdout.read(want - len(pending))
            if not chunk:
                break
            pending += chunk
            if len(pending) >= want:
                samples = np.frombuffer(pending[:want], dtype=np.float32)
                pending = pending[want:]
                with self.lock:
                    self.buf = samples
        if self.active_source == "system":
            self.active_source = None
            self.status = "system audio stopped — grant Screen Recording to the app, retrying"
            log(f"party: {self.status}")

    def _read_helper_err(self) -> None:
        proc = self.helper
        while proc and proc.poll() is None:
            line = proc.stderr.readline()
            if not line:
                break
            text = line.decode(errors="replace").strip()
            if text:
                log(f"party/sysaudio: {text}")
                if "capturing" in text:
                    self.status = "system audio"

    # -- input-device source -----------------------------------------------------
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

    def _open_input(self) -> bool:
        try:
            import sounddevice as sd

            idx, name = self._pick_device()
            if idx is None:
                self.status = "no audio input found"
                return False

            def callback(indata, frames, t, status):
                mono = indata.mean(axis=1) if indata.ndim > 1 else indata[:, 0]
                with self.lock:
                    self.buf = mono.copy()

            self.stream = sd.InputStream(device=idx, channels=1,
                                         samplerate=SAMPLE_RATE, blocksize=BLOCK,
                                         callback=callback)
            self.stream.start()
            self.active_source = "input"
            self.status = f"listening: {name}"
            log(f"party: {self.status}")
            return True
        except Exception as exc:  # noqa: BLE001
            self.status = f"audio unavailable: {type(exc).__name__}"
            self.stream = None
            return False

    # -- source management ---------------------------------------------------
    def _open_audio(self) -> None:
        now = time.monotonic()
        if self.active_source is not None or now < self.next_try:
            return
        self.next_try = now + 10.0
        if self.cfg["source"] == "system":
            if self.helper is not None and self.helper.poll() is None:
                try:
                    self.helper.kill()
                except Exception:
                    pass
            if self._open_system():
                return
            log("party: system source unavailable, falling back to input")
        self._open_input()

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop(); self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.helper is not None:
            try:
                self.helper.kill()
            except Exception:
                pass
            self.helper = None
        self.active_source = None

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
        # if the system helper died (e.g. no permission yet), fall back / retry
        if self.active_source == "system" and self.helper and self.helper.poll() is not None:
            self.active_source = None
        self._open_audio()
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
        self.prev_bass = self.bass
        self.bass = 0.75 * self.bass + 0.25 * min(1.0, (bands[0] + bands[1]) / (2 * self.gain))
        # kick onset: a sharp rise in bass energy triggers a strobe flash
        if self.bass - self.prev_bass > 0.16 and self.bass > 0.45:
            self.flash = 1.0

    def draw(self, screen):
        now = time.monotonic()
        rainbow = self.cfg.get("palette", "rainbow") == "rainbow"
        phase = now * self.cfg.get("rainbow_speed", 0.06)
        if rainbow:                                # bass pulse cycles hue too
            import colorsys
            hr, hg, hb = colorsys.hsv_to_rgb(phase % 1.0, 1.0, 1.0)
            b = self.bass
            screen.clear((int(40 * b * hr), int(40 * b * hg), int(40 * b * hb)))
        else:
            b = int(14 * self.bass)
            screen.clear((b, 0, b // 2))           # bass-driven purple pulse
        for col in range(12):
            h = self.levels[col]
            for row in range(int(round(h))):
                if row < 12:
                    color = rainbow_color(col, row, phase) if rainbow else heat_color(row)
                    screen.set(col, 11 - row, color)
            pk = int(round(self.peaks[col]))
            if pk >= 1:
                screen.set(col, max(0, 12 - pk), (255, 255, 255))
        # beat strobe: flash the whole board white on kicks, then decay
        if self.flash > 0.01:
            f = self.flash
            screen.px = [tuple(min(255, int(v + (255 - v) * f)) for v in px)
                         for px in screen.px]
            self.flash *= 0.55
        if self.active_source is None and int(time.monotonic() * 2) % 2:
            for x, y in ((0, 0), (11, 0)):
                screen.set(x, y, (120, 0, 0))


if __name__ == "__main__":
    run(Party)
