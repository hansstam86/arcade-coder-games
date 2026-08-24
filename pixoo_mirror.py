"""Mirror the Arcade Coder's 12x12 display onto a Divoom Pixoo (16x16) over BLE.

Runs its own asyncio loop in a background thread, holds a persistent Pixoo
connection (reconnecting as needed), and sends the latest board frame scaled
to 16x16 — paced for Bluetooth. The Pixoo must be in "app mode" (not its
standalone clock) to accept image data.

ArcadeOS pushes each rendered board frame via set_board_frame(); everything
else is decoupled so the board is never blocked by the Pixoo link.
"""

from __future__ import annotations

import asyncio
import threading
import time

from pixoo import Pixoo, SIZE  # SIZE = 16

BOARD = 12


def scale_12_to_16(px12):
    """Nearest-neighbour upscale of a 144-list of (r,g,b) to a 256-list."""
    out = []
    for oy in range(SIZE):
        sy = oy * BOARD // SIZE
        row = sy * BOARD
        for ox in range(SIZE):
            out.append(px12[row + (ox * BOARD // SIZE)])
    return out


def quantize(pixels, levels=6):
    """Reduce colour depth so busy frames keep a small palette (faster BLE)."""
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
        self.max_colors = max_colors     # keep the BLE image small enough to arrive
        threading.Thread(target=self._run, daemon=True).start()

    def set_board_frame(self, px12) -> None:
        frame = quantize(scale_12_to_16(list(px12)), self.quant_levels)
        with self._lock:
            self._frame = frame

    def _run(self) -> None:
        try:
            asyncio.run(self._loop())
        except Exception:
            pass

    async def _loop(self) -> None:
        while not self._stop:
            px = Pixoo()
            try:
                await px.connect()
                self.connected = True
                try:
                    await px.brightness(self.brightness)
                except Exception:
                    pass
                last = None
                while not self._stop and px.client and px.client.is_connected:
                    t0 = time.monotonic()
                    with self._lock:
                        frame = self._frame
                    if frame is not None and frame != last:
                        try:
                            await px.image(frame, max_colors=self.max_colors)
                            last = frame
                        except Exception:
                            break
                    await asyncio.sleep(max(0.0, self.min_interval - (time.monotonic() - t0)))
            except Exception:
                pass
            self.connected = False
            try:
                await px.disconnect()
            except Exception:
                pass
            if not self._stop:
                await asyncio.sleep(5)

    def stop(self) -> None:
        self._stop = True
