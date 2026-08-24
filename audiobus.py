"""Shared system-audio bus — one capture, many consumers.

ArcadeOS owns a single AudioBus so it can both (a) measure the audio level
continuously (to switch into the equalizer when sound plays and back to
ambient when it's quiet) and (b) feed the party visualizer its samples.
Only one ScreenCaptureKit capture can run at a time, so everything shares
this one.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "sysaudio_helper"
BLOCK = 1024


class AudioBus:
    def __init__(self, device_contains=None) -> None:
        self.device_contains = device_contains or ["USBAudio", "EP-133", "mic"]
        self._buf = None                 # latest np block (consumed by get_block)
        self.level = 0.0                 # absolute recent energy (mean abs), decayed
        self.active_source = None        # "system" | "input" | None
        self.helper = None
        self.stream = None
        self._stop = False
        self._lock = threading.Lock()
        self.next_try = 0.0
        import numpy as np

        self._np = np
        threading.Thread(target=self._supervise, daemon=True).start()

    # -- consumers ----------------------------------------------------------
    def get_block(self):
        """Pop the latest sample block (np.float32) or None if none new."""
        with self._lock:
            b, self._buf = self._buf, None
            return b

    def _publish(self, samples) -> None:
        np = self._np
        energy = float(np.mean(np.abs(samples))) if len(samples) else 0.0
        with self._lock:
            self._buf = samples
            # fast attack, slow release so brief gaps don't read as silence
            self.level = energy if energy > self.level else self.level * 0.92 + energy * 0.08

    # -- capture supervision ------------------------------------------------
    def _supervise(self) -> None:
        while not self._stop:
            if self.active_source is None and time.monotonic() >= self.next_try:
                self.next_try = time.monotonic() + 10.0
                if not self._open_system():
                    self._open_input()
            time.sleep(0.5)

    def _open_system(self) -> bool:
        if not HELPER.exists():
            return False
        try:
            self.helper = subprocess.Popen([str(HELPER)], stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
        except OSError:
            return False
        threading.Thread(target=self._read_helper, daemon=True).start()
        self.active_source = "system"
        return True

    def _read_helper(self) -> None:
        proc, np = self.helper, self._np
        pending, want = b"", BLOCK * 4
        while proc and proc.poll() is None and not self._stop:
            chunk = proc.stdout.read(want - len(pending))
            if not chunk:
                break
            pending += chunk
            if len(pending) >= want:
                self._publish(np.frombuffer(pending[:want], dtype=np.float32))
                pending = pending[want:]
        if self.active_source == "system":
            self.active_source = None

    def _open_input(self) -> bool:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            idx = None
            for key in self.device_contains:
                for i, d in enumerate(devices):
                    if d["max_input_channels"] > 0 and key.lower() in d["name"].lower():
                        idx = i
                        break
                if idx is not None:
                    break
            if idx is None:
                for i, d in enumerate(devices):
                    if d["max_input_channels"] > 0:
                        idx = i
                        break
            if idx is None:
                return False

            def callback(indata, frames, t, status):
                mono = indata.mean(axis=1) if indata.ndim > 1 else indata[:, 0]
                self._publish(mono.copy())

            self.stream = sd.InputStream(device=idx, channels=1, samplerate=48000,
                                         blocksize=BLOCK, callback=callback)
            self.stream.start()
            self.active_source = "input"
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self._stop = True
        if self.helper:
            try:
                self.helper.kill()
            except Exception:
                pass
        if self.stream:
            try:
                self.stream.stop(); self.stream.close()
            except Exception:
                pass
