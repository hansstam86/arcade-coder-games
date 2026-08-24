"""Mirror the Arcade Coder's 12x12 display onto a paired Divoom Pixoo (16x16).

The Pixoo is driven over its Bluetooth serial port (see pixoo.py). A background
thread opens the port, then streams the latest board frame scaled to 16x16,
BLE-paced and colour-reduced so each image is small. If the port isn't present
(Pixoo not paired) it retries quietly; the board is never blocked.
"""

from __future__ import annotations

import threading
import time

from pixoo import Pixoo, SIZE, find_port

BOARD = 12


def scale_12_to_16(px12):
    out = []
    for oy in range(SIZE):
        row = (oy * BOARD // SIZE) * BOARD
        for ox in range(SIZE):
            out.append(px12[row + (ox * BOARD // SIZE)])
    return out


def quantize(pixels, levels=4):
    step = 255 // (levels - 1)
    return [tuple(round(c / step) * step for c in p) for p in pixels]


class PixooMirror:
    def __init__(self, brightness=80, fps=4, quant_levels=4, max_colors=16) -> None:
        self._frame = None
        self._lock = threading.Lock()
        self._stop = False
        self.connected = False
        self.brightness = brightness
        self.min_interval = 1.0 / max(1, fps)
        self.quant_levels = quant_levels
        self.max_colors = max_colors
        threading.Thread(target=self._run, daemon=True).start()

    def set_board_frame(self, px12) -> None:
        frame = quantize(scale_12_to_16(list(px12)), self.quant_levels)
        with self._lock:
            self._frame = frame

    def _run(self) -> None:
        while not self._stop:
            if find_port() is None:
                self.connected = False
                time.sleep(3.0)
                continue
            px = Pixoo()
            if not px.open():
                time.sleep(3.0)
                continue
            self.connected = True
            try:
                px.brightness(self.brightness)
            except Exception:
                pass
            last = None
            while not self._stop:
                t0 = time.monotonic()
                with self._lock:
                    frame = self._frame
                if frame is not None and frame != last:
                    try:
                        px.image(frame, max_colors=self.max_colors)
                        last = frame
                    except Exception:
                        break
                time.sleep(max(0.0, self.min_interval - (time.monotonic() - t0)))
            self.connected = False
            px.close()
            if not self._stop:
                time.sleep(2.0)

    def stop(self) -> None:
        self._stop = True
