"""On-board notification center for ArcadeOS.

Notifications queue up and STAY on the board (overriding the equalizer/idle)
until you press a pad to mark each one read. Shows the current notification's
text scrolling, a coloured border for the source, an unread-count row, and a
pulsing "press to dismiss" bar. When the queue empties, ArcadeOS returns to
whatever it was doing.
"""

from __future__ import annotations

import threading
import time

from marquee import render_columns

W = H = 12
SCROLL_SPEED = 7.0   # pixels/sec


class NotifCenter:
    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.cols: list[list[int]] = []
        self.scroll = 0.0
        self.last = time.monotonic()
        self.seen_total = 0
        self.lock = threading.Lock()

    # -- queue ---------------------------------------------------------------
    def add(self, app: str, title: str, body: str, color) -> None:
        parts = [p.strip() for p in (title, body) if p and p.strip()]
        text = (app + ("  " + "  ".join(parts) if parts else "")).upper()
        with self.lock:
            self.queue.append({"text": text, "color": tuple(color)})
            self.seen_total += 1
            if len(self.queue) == 1:
                self._load()

    def _load(self) -> None:
        self.cols = render_columns("  " + self.queue[0]["text"] + "  ")
        self.scroll = -float(W)
        self.last = time.monotonic()

    def has_unread(self) -> bool:
        return bool(self.queue)

    def unread(self) -> int:
        return len(self.queue)

    def press(self, x: int, y: int) -> None:
        """Any press marks the current notification read."""
        with self.lock:
            if self.queue:
                self.queue.pop(0)
                if self.queue:
                    self._load()

    # -- render --------------------------------------------------------------
    def draw(self, screen, now: float) -> None:
        with self.lock:
            if not self.queue:
                return
            n = self.queue[0]
            cols = self.cols
        color = n["color"]
        screen.clear(tuple(c // 10 for c in color))          # dim tint bg

        # scrolling white text, rows 3..7
        dt = now - self.last
        self.last = now
        self.scroll += SCROLL_SPEED * dt
        total = max(1, len(cols))
        if self.scroll >= total:                              # loop until dismissed
            self.scroll = -float(W) * 0.5
        base = int(self.scroll)
        for sx in range(W):
            ci = base + sx
            if 0 <= ci < total:
                bits = cols[ci]
                for r in range(5):
                    if bits[r]:
                        screen.set(sx, 3 + r, (255, 255, 255))

        # top row: unread-count dots in the source colour
        for i in range(min(self.unread(), W)):
            screen.set(i, 0, color)

        # side borders (rows 1..9) mark the alert colour
        for y in range(1, 10):
            screen.set(0, y, tuple(c // 2 for c in color))
            screen.set(W - 1, y, tuple(c // 2 for c in color))

        # bottom row: pulsing "press to dismiss" bar
        pulse = 0.4 + 0.6 * (0.5 + 0.5 * __import__("math").sin(now * 4))
        bar = tuple(int(c * pulse) for c in color)
        for x in range(W):
            screen.set(x, 11, bar)
