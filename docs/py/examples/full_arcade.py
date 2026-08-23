#!/usr/bin/env python3
"""The complete 10-game arcade as an SDK app.

`python examples/full_arcade.py`        -> browser emulator
`python examples/full_arcade.py --hw`   -> real board over BLE

Wraps the arcade.py launcher (menu, games, replay/menu choice screen) in the
arcadecoder Game API. Game frames are produced in device byte order by the
arcade Apps and converted back to display RGB here.
"""
import time

import arcade as ac
from arcadecoder import Game, N, run


def device_to_screen(fb: bytes, screen) -> None:
    for i in range(N):
        b, g, r = fb[i * 3 : i * 3 + 3]
        screen.px[i] = (r, g, b)


class Arcade(Game):
    fps = 10

    def start(self):
        self.mode = "menu"          # menu | game | choice
        self.app = None
        self.last_cls = None

    def on_press(self, x, y):
        idx = y * 12 + x
        now = time.monotonic()
        if self.mode == "menu":
            cls = ac.menu_pick(idx)
            if cls:
                self.app, self.last_cls, self.mode = cls(), cls, "game"
        elif self.mode == "game":
            self.app.press(idx, now)
        elif self.mode == "choice":
            sel = ac.choice_pick(idx)
            if sel == "replay":
                self.app, self.mode = self.last_cls(), "game"
            elif sel == "menu":
                self.mode = "menu"

    def draw(self, screen):
        now = time.monotonic()
        if self.mode == "menu":
            fb = ac.menu_frame(now)
        elif self.mode == "game":
            fb = self.app.frame(now)
            if self.app.over:
                self.mode = "choice"
                fb = ac.choice_frame(now)
        else:
            fb = ac.choice_frame(now)
        device_to_screen(fb, screen)


if __name__ == "__main__":
    run(Arcade)
