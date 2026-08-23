"""arcadecoder — write games for the TWSU Arcade Coder in a few lines.

    from arcadecoder import Game, run

    class MyGame(Game):
        fps = 10
        def on_press(self, x, y): ...
        def update(self, dt): ...
        def draw(self, screen): screen.set(x, y, (255, 0, 0))

    run(MyGame)

`python mygame.py` runs the browser emulator (no hardware needed).
`python mygame.py --hw` runs the same game on a real board over BLE
(on macOS, launch through an app bundle that owns Bluetooth permission —
see the repo README).
"""

from __future__ import annotations

import sys

W = H = 12
N = W * H

__all__ = ["Game", "Screen", "run", "W", "H", "N"]


class Screen:
    """12x12 display-RGB framebuffer. (0,0) is top-left."""

    def __init__(self) -> None:
        self.px: list[tuple[int, int, int]] = [(0, 0, 0)] * N

    def clear(self, rgb=(0, 0, 0)) -> None:
        self.px = [rgb] * N

    def set(self, x: int, y: int, rgb) -> None:
        if 0 <= x < W and 0 <= y < H:
            self.px[y * W + x] = rgb

    def get(self, x: int, y: int):
        return self.px[y * W + x]

    def rect(self, x0: int, y0: int, w: int, h: int, rgb) -> None:
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.set(x, y, rgb)

    def to_device_bytes(self) -> bytes:
        # hardware colour order swaps red and blue
        return b"".join(bytes((b, g, r)) for (r, g, b) in self.px)

    def to_hex(self) -> list[str]:
        return [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in self.px]


class Game:
    """Subclass this. The runner calls start/on_press/update/draw."""

    fps = 10          # draw() cadence (frames are only sent when they change)
    restart_delay = 2.5  # seconds to show the final frame before auto-restart

    def __init__(self) -> None:
        self.finished = False

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None: ...

    def on_press(self, x: int, y: int) -> None: ...

    def update(self, dt: float) -> None: ...

    def draw(self, screen: Screen) -> None: ...

    def end(self) -> None:
        """Call from your game to finish; the runner restarts after a pause."""
        self.finished = True


def run(game_cls: type[Game], backend: str | None = None) -> None:
    """Run a Game. backend: 'emu' (default), 'hw', or None to read argv."""
    if backend is None:
        backend = "hw" if "--hw" in sys.argv else "emu"
    if backend == "hw":
        from .ble import run_ble

        run_ble(game_cls)
    else:
        from .emulator import run_emulator

        run_emulator(game_cls)
