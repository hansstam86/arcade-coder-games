"""On-board notification center for ArcadeOS — a tap-to-act surface.

Notifications queue up and STAY on the board (overriding the equalizer/idle)
until you act on each one. The message scrolls, a coloured border marks the
source, and the bottom holds three action buttons:

    [ OPEN (green) ][ SNOOZE (blue) ][ DISMISS (red) ]

OPEN brings the sending app to the front, SNOOZE hides it and brings it back
in a few minutes, DISMISS marks it read. When the queue empties, ArcadeOS
returns to whatever it was doing.
"""

from __future__ import annotations

import math
import subprocess
import threading
import time

from marquee import render_columns

W = H = 12
SCROLL_SPEED = 7.0   # pixels/sec
SNOOZE_SECONDS = 300  # 5 minutes


class NotifCenter:
    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.snoozed: list[dict] = []
        self.cols: list[list[int]] = []
        self.scroll = 0.0
        self.last = time.monotonic()
        self.seen_total = 0
        self.flash = None            # (kind, until) tap feedback
        self.lock = threading.Lock()

    # -- queue ---------------------------------------------------------------
    def add(self, app: str, title: str, body: str, color, bundle=None) -> None:
        parts = [p.strip() for p in (title, body) if p and p.strip()]
        text = (app + ("  " + "  ".join(parts) if parts else "")).upper()
        with self.lock:
            self.queue.append({"text": text, "color": tuple(color),
                               "app": app, "bundle": bundle})
            self.seen_total += 1
            if len(self.queue) == 1:
                self._load()

    def _load(self) -> None:
        self.cols = render_columns("  " + self.queue[0]["text"] + "  ")
        self.scroll = -float(W)
        self.last = time.monotonic()

    def tick(self, now: float) -> None:
        """Re-surface any snoozed notifications whose timer has elapsed."""
        with self.lock:
            due = [s for s in self.snoozed if now >= s["wake"]]
            if not due:
                return
            self.snoozed = [s for s in self.snoozed if now < s["wake"]]
            empty = not self.queue
            for s in due:
                self.queue.append(s["item"])
            if empty and self.queue:
                self._load()

    def has_unread(self) -> bool:
        return bool(self.queue)

    def unread(self) -> int:
        return len(self.queue)

    # -- actions -------------------------------------------------------------
    def _open(self, item) -> None:
        b, app = item.get("bundle"), item.get("app")
        try:
            if b and "." in str(b):
                subprocess.Popen(["open", "-b", str(b)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app:
                subprocess.Popen(["open", "-a", str(app)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def press(self, x: int, y: int) -> None:
        with self.lock:
            if not self.queue:
                return
            if y < 10:                                   # only the action bar acts
                return
            item = self.queue[0]
            kind = "open" if x <= 3 else "snooze" if x <= 7 else "dismiss"
            self.flash = (kind, time.monotonic() + 0.2)
            if kind == "open":
                self._open(item)
                self.queue.pop(0)
            elif kind == "snooze":
                self.queue.pop(0)
                self.snoozed.append({"item": item, "wake": time.monotonic() + SNOOZE_SECONDS})
            else:
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
            queue_colors = [q["color"] for q in self.queue]
            flash = self.flash
        color = n["color"]
        screen.clear(tuple(c // 10 for c in color))          # dim tint bg

        dt = now - self.last                                  # scrolling text, rows 3..7
        self.last = now
        self.scroll += SCROLL_SPEED * dt
        total = max(1, len(cols))
        if self.scroll >= total:
            self.scroll = -float(W) * 0.5
        base = int(self.scroll)
        for sx in range(W):
            ci = base + sx
            if 0 <= ci < total:
                bits = cols[ci]
                for r in range(5):
                    if bits[r]:
                        screen.set(sx, 3 + r, (255, 255, 255))

        blink = int(now * 3) % 2                               # queue dots (row 0)
        for i, qc in enumerate(queue_colors[:W]):
            screen.set(i, 0, (255, 255, 255) if (i == 0 and blink) else qc)

        for y in range(1, 9):                                 # source-colour side borders
            screen.set(0, y, tuple(c // 2 for c in color))
            screen.set(W - 1, y, tuple(c // 2 for c in color))

        # action bar (rows 10–11): OPEN | SNOOZE | DISMISS
        fk = flash[0] if (flash and now < flash[1]) else None

        def bcol(kind, base3):
            return (255, 255, 255) if fk == kind else base3
        for yy in (10, 11):
            for xx in range(0, 4):
                screen.set(xx, yy, bcol("open", (0, 150, 55)))
            for xx in range(4, 8):
                screen.set(xx, yy, bcol("snooze", (40, 80, 210)))
            for xx in range(8, 12):
                screen.set(xx, yy, bcol("dismiss", (200, 40, 40)))
        # tiny white glyphs: ▲ open, ᶻ snooze, ✕ dismiss
        for cx, cy in ((2, 10), (1, 11), (3, 11)):
            screen.set(cx, cy, (255, 255, 255))               # up-chevron
        for cx, cy in ((5, 10), (6, 10), (5, 11), (6, 11)):
            screen.set(cx, cy, (200, 220, 255))               # "later" block
        for cx, cy in ((8, 10), (11, 10), (9, 11), (10, 11)):
            screen.set(cx, cy, (255, 255, 255))               # x corners
