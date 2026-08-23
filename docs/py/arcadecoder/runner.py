"""Backend-independent game loop shared by the emulator and BLE runners."""

from __future__ import annotations

import time

from . import Game, Screen


class GameLoop:
    """Drives a Game: instantiate, tick, deliver presses, auto-restart."""

    def __init__(self, game_cls: type[Game]) -> None:
        self.game_cls = game_cls
        self.screen = Screen()
        self._restart()

    def _restart(self) -> None:
        self.game = self.game_cls()
        self.game.start()
        self.last_update = time.monotonic()
        self.finished_at = 0.0

    def press(self, x: int, y: int) -> None:
        if not self.game.finished:
            self.game.on_press(x, y)

    def reset(self) -> None:
        """Restart the game from scratch (the emulator's reboot button)."""
        self.screen.clear()
        self._restart()

    def tick(self) -> list[str]:
        """Advance the game; returns the current frame as hex colours."""
        now = time.monotonic()
        if self.game.finished:
            if not self.finished_at:
                self.finished_at = now
            elif now - self.finished_at >= self.game.restart_delay:
                self._restart()
            return self.screen.to_hex()
        dt, self.last_update = now - self.last_update, now
        self.game.update(dt)
        self.game.draw(self.screen)
        return self.screen.to_hex()

    def frame_device_bytes(self) -> bytes:
        return self.screen.to_device_bytes()
