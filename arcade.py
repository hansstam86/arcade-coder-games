#!/usr/bin/env python3
"""Arcade launcher for the Arcade Coder: menu + five games, one process.

Menu: press an icon to start a game. When a game ends: green block = play
again, blue block = back to menu.
"""

from __future__ import annotations

import asyncio
import random
import time

import minesweeper as ms
import whackamole as wm
from minesweeper import Board, N, W, H, dev, log

# ---------------------------------------------------------------------------
# framework
# ---------------------------------------------------------------------------


def solid(rgb):
    return dev(rgb) * N


def paint(buf, x, y, rgb):
    if 0 <= x < W and 0 <= y < H:
        buf[y * W + x] = rgb


def block(buf, x0, y0, w, h, rgb):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            paint(buf, x, y, rgb)


def to_bytes(buf):
    return b"".join(dev(c) for c in buf)


class App:
    """A game. Drive with press()/frame(); set self.over when finished."""

    name = "app"
    over = False

    def press(self, idx: int, now: float) -> None: ...
    def frame(self, now: float) -> bytes: ...


# ---------------------------------------------------------------------------
# Minesweeper wrapper (logic reused from minesweeper.py)
# ---------------------------------------------------------------------------


class Mines(App):
    name = "mines"

    def __init__(self) -> None:
        self.g = ms.Game()
        self.state = "play"
        self.t0 = 0.0

    def press(self, idx, now):
        if self.state != "play":
            return
        result = self.g.press(idx)
        if result == "boom":
            log("mines: BOOM\n" + self.g.ascii())
            self.state, self.t0 = "boom", now
        elif result == "win":
            log("mines: WIN")
            self.state, self.t0 = "win", now

    def frame(self, now):
        if self.state == "play":
            return self.g.framebuffer()
        t = now - self.t0
        if t > 3.5:
            self.over = True
        if self.state == "boom":
            if t < 2.0 and int(t / 0.4) % 2:
                return solid((120, 0, 0))
            return self.g.framebuffer(show_mines=True)
        # win
        if t < 2.0 and int(t / 0.4) % 2:
            return solid((0, 160, 0))
        return self.g.framebuffer()


# ---------------------------------------------------------------------------
# Whack-a-Mole wrapper (logic reused from whackamole.py)
# ---------------------------------------------------------------------------


class Moles(App):
    name = "moles"

    def __init__(self) -> None:
        self.g = wm.Game()
        self.ended = 0.0

    def press(self, idx, now):
        if not self.ended and self.g.whack(idx):
            log(f"moles: whack — {self.g.score}")

    def frame(self, now):
        if self.ended:
            if now - self.ended > 4.0:
                self.over = True
            return wm.score_frame(self.g.score)
        if now >= self.g.t_end:
            log(f"moles: round over — score {self.g.score}, missed {self.g.misses}")
            self.ended = now
            return wm.score_frame(self.g.score)
        self.g.tick(now)
        return self.g.framebuffer(now)


# ---------------------------------------------------------------------------
# Simon
# ---------------------------------------------------------------------------

SIMON_COLS = [(0, 180, 0), (200, 0, 0), (200, 180, 0), (0, 60, 220)]  # G R Y B


class Simon(App):
    name = "simon"

    def __init__(self) -> None:
        self.seq = [random.randrange(4)]
        self.state = "show"      # show | input | fail
        self.t0 = time.monotonic()
        self.pos = 0             # index in seq while showing / matching
        self.fail_t = 0.0

    @staticmethod
    def quadrant(idx: int) -> int:
        x, y = idx % W, idx // W
        return (0 if y < 6 else 2) + (0 if x < 6 else 1)

    def press(self, idx, now):
        if self.state != "input":
            return
        q = self.quadrant(idx)
        if q == self.seq[self.pos]:
            self.pos += 1
            self.flash = (q, now)
            if self.pos == len(self.seq):
                self.seq.append(random.randrange(4))
                self.state, self.t0, self.pos = "show", now + 0.7, 0
        else:
            log(f"simon: fail at length {len(self.seq) - 1}")
            self.state, self.fail_t = "fail", now

    flash = None  # (quadrant, t) echo of the player's press

    def quad_frame(self, lit: int | None, dim=28) -> bytes:
        buf = [(0, 0, 0)] * N
        for q, col in enumerate(SIMON_COLS):
            x0 = 0 if q % 2 == 0 else 6
            y0 = 0 if q < 2 else 6
            c = col if q == lit else tuple(v * dim // 200 for v in col)
            block(buf, x0, y0, 6, 6, c)
        return to_bytes(buf)

    def frame(self, now):
        if self.state == "fail":
            t = now - self.fail_t
            if t > 3.0:
                self.over = True
            if t < 1.2 and int(t / 0.3) % 2:
                return solid((120, 0, 0))
            score = len(self.seq) - 1
            buf = [(0, 0, 0)] * N
            for i in range(min(score, N)):
                buf[i] = (0, 160, 0)
            return to_bytes(buf)
        if self.state == "show":
            t = now - self.t0
            if t < 0:
                return self.quad_frame(None)
            step = int(t / 0.75)
            if step >= len(self.seq):
                self.state, self.pos = "input", 0
                return self.quad_frame(None)
            within = t - step * 0.75
            return self.quad_frame(self.seq[step] if within < 0.5 else None)
        # input: echo presses briefly
        if self.flash and now - self.flash[1] < 0.25:
            return self.quad_frame(self.flash[0])
        return self.quad_frame(None)


# ---------------------------------------------------------------------------
# Lights Out (5x5 of 2x2 blocks at x,y = 1..10)
# ---------------------------------------------------------------------------


class Lights(App):
    name = "lights"

    def __init__(self) -> None:
        self.grid = [[False] * 5 for _ in range(5)]
        for _ in range(8):  # scramble from solved => always solvable
            self.toggle(random.randrange(5), random.randrange(5))
        self.won_t = 0.0

    def toggle(self, i, j):
        for di, dj in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= i + di < 5 and 0 <= j + dj < 5:
                self.grid[j + dj][i + di] ^= True

    def press(self, idx, now):
        if self.won_t:
            return
        x, y = idx % W, idx // W
        if not (1 <= x <= 10 and 1 <= y <= 10):
            return
        self.toggle((x - 1) // 2, (y - 1) // 2)
        if not any(any(row) for row in self.grid):
            log("lights: solved!")
            self.won_t = now

    def frame(self, now):
        if self.won_t and now - self.won_t > 0.4:
            if now - self.won_t > 2.5:
                self.over = True
            if int((now - self.won_t) / 0.35) % 2:
                return solid((0, 160, 0))
        buf = [(0, 0, 0)] * N
        for j in range(5):
            for i in range(5):
                col = (220, 140, 0) if self.grid[j][i] else (6, 6, 20)
                block(buf, 1 + 2 * i, 1 + 2 * j, 2, 2, col)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Connect Four (6 columns x 6 rows of 2x2 discs, two players at the board)
# ---------------------------------------------------------------------------

P1 = (220, 0, 0)      # red
P2 = (0, 180, 180)    # cyan


class Four(App):
    name = "four"
    COLS = 12
    ROWS = 12

    def __init__(self) -> None:
        self.cols = [[] for _ in range(self.COLS)]  # each: players bottom-up
        self.turn = 0
        self.win_cells: list[tuple[int, int]] = []
        self.end_t = 0.0

    def cell(self, c, r):
        """player at column c, row r (bottom=0) or None"""
        return self.cols[c][r] if r < len(self.cols[c]) else None

    def press(self, idx, now):
        if self.end_t:
            return
        c = idx % W
        if len(self.cols[c]) >= self.ROWS:
            return
        self.cols[c].append(self.turn)
        if self.check_win(c, len(self.cols[c]) - 1):
            log(f"four: player {self.turn + 1} wins")
            self.end_t = now
        elif all(len(col) == self.ROWS for col in self.cols):
            log("four: draw")
            self.end_t = now
        else:
            self.turn ^= 1

    def check_win(self, c, r):
        me = self.cols[c][r]
        for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
            cells = [(c, r)]
            for s in (1, -1):
                k = 1
                while True:
                    cc, rr = c + dc * k * s, r + dr * k * s
                    if 0 <= cc < self.COLS and 0 <= rr < self.ROWS and self.cell(cc, rr) == me:
                        cells.append((cc, rr))
                        k += 1
                    else:
                        break
            if len(cells) >= 4:
                self.win_cells = cells
                return True
        return False

    def frame(self, now):
        blink = int(now / 0.35) % 2
        if self.end_t and now - self.end_t > 4.0:
            self.over = True
        buf = [(2, 2, 8)] * N  # faint board background
        for c in range(self.COLS):
            for r in range(len(self.cols[c])):
                col = P1 if self.cols[c][r] == 0 else P2
                if self.end_t and self.win_cells and (c, r) in self.win_cells and blink:
                    col = (255, 255, 255)
                paint(buf, c, self.ROWS - 1 - r, col)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Menu + end-choice screens
# ---------------------------------------------------------------------------

GAMES = [
    ("mines", Mines, (200, 200, 200), (1, 1)),
    ("moles", Moles, (230, 170, 0), (5, 1)),
    ("simon", Simon, (200, 0, 180), (9, 1)),
    ("lights", Lights, (220, 140, 0), (3, 7)),
    ("four", Four, (0, 180, 180), (7, 7)),
]


def menu_frame(now) -> bytes:
    buf = [(0, 0, 0)] * N
    for _name, _cls, col, (x, y) in GAMES:
        block(buf, x, y, 3, 3, col)
    return to_bytes(buf)


def menu_pick(idx) -> type | None:
    x, y = idx % W, idx // W
    for _name, cls, _col, (bx, by) in GAMES:
        if bx - 1 <= x <= bx + 3 and by - 1 <= y <= by + 3:
            return cls
    return None


def choice_frame(now) -> bytes:
    buf = [(0, 0, 0)] * N
    block(buf, 1, 4, 4, 4, (0, 170, 0))    # replay
    block(buf, 7, 4, 4, 4, (0, 60, 220))   # menu
    return to_bytes(buf)


def choice_pick(idx) -> str | None:
    x, y = idx % W, idx // W
    if 3 <= y <= 8:
        if 0 <= x <= 5:
            return "replay"
        if 6 <= x <= 11:
            return "menu"
    return None


# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------


async def run(board: Board) -> None:
    mode = "menu"          # menu | game | choice
    app: App | None = None
    last_cls: type | None = None
    last_frame = b""
    while not board.notify_queue.empty():
        board.notify_queue.get_nowait()
    log("menu up — press an icon: mines(white) moles(yellow) simon(magenta) lights(amber) four(cyan)")

    while True:
        now = time.monotonic()
        if mode == "menu":
            frame = menu_frame(now)
        elif mode == "game":
            frame = app.frame(now)
            if app.over:
                mode = "choice"
                while not board.notify_queue.empty():
                    board.notify_queue.get_nowait()
                frame = choice_frame(now)
                log("choice: green = play again, blue = menu")
        else:
            frame = choice_frame(now)
        if frame != last_frame:
            await board.send_frame(frame)
            last_frame = frame

        try:
            data = await asyncio.wait_for(board.notify_queue.get(), timeout=0.12)
        except asyncio.TimeoutError:
            if board.disconnected.is_set():
                raise ConnectionError("disconnected")
            continue
        presses = board.decode_presses(data)
        if not presses:
            continue
        for idx in presses:
            now = time.monotonic()
            if mode == "menu":
                cls = menu_pick(idx)
                if cls:
                    app, last_cls, mode = cls(), cls, "game"
                    log(f"starting {app.name}")
            elif mode == "game":
                app.press(idx, now)
            else:
                sel = choice_pick(idx)
                if sel == "replay":
                    app, mode = last_cls(), "game"
                    log(f"replay {app.name}")
                elif sel == "menu":
                    mode = "menu"
                    log("back to menu")
        last_frame = b""  # force redraw to wipe the firmware brush pixel


async def main() -> None:
    board = Board()
    while True:
        try:
            await board.connect()
            await board.start_paint()
            await run(board)
        except Exception as exc:  # noqa: BLE001
            log(f"error: {exc!r}; retrying in 4s")
        try:
            if board.client:
                await board.client.disconnect()
        except Exception:
            pass
        board.client = None
        board.sent_frames.clear()
        await asyncio.sleep(4)


if __name__ == "__main__":
    asyncio.run(main())
