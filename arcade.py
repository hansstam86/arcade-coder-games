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
# Colour Sudoku (9x9 grid + palette row; guided: wrong colours flash red)
# ---------------------------------------------------------------------------

SUD_COLS = {
    1: (220, 0, 0),      # red
    2: (0, 200, 0),      # green
    3: (0, 60, 230),     # blue
    4: (220, 200, 0),    # yellow
    5: (200, 0, 180),    # magenta
    6: (0, 190, 190),    # cyan
    7: (240, 90, 0),     # orange
    8: (230, 230, 230),  # white
    9: (255, 60, 120),   # pink
}
GIVENS = 38


def gen_sudoku() -> list[list[int]]:
    grid = [[0] * 9 for _ in range(9)]

    def ok(r, c, v):
        if any(grid[r][x] == v for x in range(9)):
            return False
        if any(grid[y][c] == v for y in range(9)):
            return False
        br, bc = r // 3 * 3, c // 3 * 3
        return all(grid[br + y][bc + x] != v for y in range(3) for x in range(3))

    def fill(pos=0):
        if pos == 81:
            return True
        r, c = divmod(pos, 9)
        vals = list(range(1, 10))
        random.shuffle(vals)
        for v in vals:
            if ok(r, c, v):
                grid[r][c] = v
                if fill(pos + 1):
                    return True
                grid[r][c] = 0
        return False

    fill()
    return grid


class Sudoku(App):
    name = "sudoku"

    def __init__(self) -> None:
        self.sol = gen_sudoku()
        cells = [(r, c) for r in range(9) for c in range(9)]
        self.given = set(random.sample(cells, GIVENS))
        self.placed: set[tuple[int, int]] = set()
        self.sel = 1
        self.wrong: dict[tuple[int, int], float] = {}
        self.win_t = 0.0

    def press(self, idx, now):
        if self.win_t:
            return
        x, y = idx % W, idx // W
        if y == 11 and x < 9:
            self.sel = x + 1
            return
        if x < 9 and y < 9:
            cell = (y, x)
            if cell in self.given or cell in self.placed:
                return
            if self.sol[y][x] == self.sel:
                self.placed.add(cell)
                if len(self.placed) + len(self.given) == 81:
                    log("sudoku: solved!")
                    self.win_t = now
            else:
                self.wrong[cell] = now + 0.6

    def frame(self, now):
        if self.win_t and now - self.win_t > 0.3:
            if now - self.win_t > 3.0:
                self.over = True
            if int((now - self.win_t) / 0.35) % 2:
                return solid((0, 170, 0))
        blink = int(now / 0.3) % 2
        buf = [(0, 0, 0)] * N
        self.wrong = {c: t for c, t in self.wrong.items() if t > now}
        for r in range(9):
            for c in range(9):
                box_dark = ((r // 3) + (c // 3)) % 2 == 0
                if (r, c) in self.wrong:
                    col = (200, 0, 0)
                elif (r, c) in self.given:
                    col = SUD_COLS[self.sol[r][c]]
                elif (r, c) in self.placed:
                    col = tuple(v * 11 // 20 for v in SUD_COLS[self.sol[r][c]])
                else:
                    col = (0, 0, 0) if box_dark else (5, 5, 9)
                paint(buf, c, r, col)
        for v in range(1, 10):  # palette
            col = SUD_COLS[v]
            if v == self.sel and blink:
                col = tuple(min(255, c + 60) for c in col)
            paint(buf, v - 1, 11, col)
        block(buf, 10, 10, 2, 2, SUD_COLS[self.sel])  # selected swatch
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Memory Pairs (4x4 cards of 2x2 pads, 8 colour pairs)
# ---------------------------------------------------------------------------

PAIR_COLS = [(220, 0, 0), (0, 200, 0), (0, 60, 230), (220, 200, 0),
             (0, 190, 190), (200, 0, 180), (230, 230, 230), (240, 90, 0)]


class Pairs(App):
    name = "pairs"

    def __init__(self) -> None:
        deck = list(range(8)) * 2
        random.shuffle(deck)
        self.cards = deck                      # 16 cards, index 0..15
        self.matched: set[int] = set()
        self.up: list[int] = []                # currently flipped (0..2)
        self.hide_t = 0.0                      # when to flip mismatches back
        self.win_t = 0.0
        self.moves = 0

    @staticmethod
    def card_at(idx: int) -> int | None:
        x, y = idx % W, idx // W
        if (x - 1) % 3 == 2 or (y - 1) % 3 == 2:   # gaps
            return None
        i, j = (x - 1) // 3, (y - 1) // 3
        if 0 <= i < 4 and 0 <= j < 4 and x >= 1 and y >= 1:
            return j * 4 + i
        return None

    def press(self, idx, now):
        if self.win_t:
            return
        if self.hide_t:                        # mismatch showing: flip back now
            self.up, self.hide_t = [], 0.0
        card = self.card_at(idx)
        if card is None or card in self.matched or card in self.up:
            return
        self.up.append(card)
        if len(self.up) == 2:
            self.moves += 1
            a, b = self.up
            if self.cards[a] == self.cards[b]:
                self.matched |= {a, b}
                self.up = []
                if len(self.matched) == 16:
                    log(f"pairs: solved in {self.moves} moves")
                    self.win_t = now
            else:
                self.hide_t = now + 1.1

    def frame(self, now):
        if self.hide_t and now >= self.hide_t:
            self.up, self.hide_t = [], 0.0
        if self.win_t:
            if now - self.win_t > 3.0:
                self.over = True
            if int((now - self.win_t) / 0.35) % 2:
                return solid((0, 160, 0))
        buf = [(0, 0, 0)] * N
        for card in range(16):
            i, j = card % 4, card // 4
            if card in self.matched:
                col = tuple(v // 4 for v in PAIR_COLS[self.cards[card]])
            elif card in self.up:
                col = PAIR_COLS[self.cards[card]]
            else:
                col = (14, 14, 14)
            block(buf, 1 + 3 * i, 1 + 3 * j, 2, 2, col)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Tetris (12x12; press left/right thirds to move, middle to rotate)
# ---------------------------------------------------------------------------

TET = {
    "I": ([(-1, 0), (0, 0), (1, 0), (2, 0)], (0, 190, 190)),
    "O": ([(0, 0), (1, 0), (0, 1), (1, 1)], (220, 200, 0)),
    "T": ([(-1, 0), (0, 0), (1, 0), (0, 1)], (160, 0, 220)),
    "S": ([(0, 0), (1, 0), (-1, 1), (0, 1)], (0, 200, 0)),
    "Z": ([(-1, 0), (0, 0), (0, 1), (1, 1)], (220, 0, 0)),
    "J": ([(-1, 0), (0, 0), (1, 0), (1, 1)], (0, 60, 230)),
    "L": ([(-1, 0), (0, 0), (1, 0), (-1, 1)], (240, 90, 0)),
}


class Tetris(App):
    name = "tetris"

    def __init__(self) -> None:
        self.field: list[list[tuple | None]] = [[None] * W for _ in range(H)]
        self.lines = 0
        self.dead_t = 0.0
        self.next_fall = time.monotonic() + self.fall_interval()
        self.spawn()

    def fall_interval(self) -> float:
        return max(0.25, 0.8 - self.lines * 0.03)

    def spawn(self) -> None:
        self.kind = random.choice(list(TET))
        self.cells, self.col = TET[self.kind]
        self.cells = list(self.cells)
        self.px, self.py = 5, 0
        if self.collides(self.cells, self.px, self.py):
            log(f"tetris: game over — {self.lines} lines")
            self.dead_t = time.monotonic()

    def collides(self, cells, px, py) -> bool:
        for dx, dy in cells:
            x, y = px + dx, py + dy
            if not (0 <= x < W and 0 <= y < H) or self.field[y][x]:
                return True
        return False

    def press(self, idx, now):
        if self.dead_t:
            return
        x = idx % W
        if x < 4:
            if not self.collides(self.cells, self.px - 1, self.py):
                self.px -= 1
        elif x >= 8:
            if not self.collides(self.cells, self.px + 1, self.py):
                self.px += 1
        elif self.kind != "O":
            rot = [(-dy, dx) for dx, dy in self.cells]
            for shift in (0, -1, 1, -2, 2):
                if not self.collides(rot, self.px + shift, self.py):
                    self.cells, self.px = rot, self.px + shift
                    break

    def lock(self) -> None:
        for dx, dy in self.cells:
            self.field[self.py + dy][self.px + dx] = self.col
        full = [y for y in range(H) if all(self.field[y])]
        for y in full:
            del self.field[y]
            self.field.insert(0, [None] * W)
        self.lines += len(full)
        if full:
            log(f"tetris: {self.lines} lines")
        self.spawn()

    def frame(self, now):
        if self.dead_t:
            if now - self.dead_t > 3.5:
                self.over = True
            buf = [(0, 0, 0)] * N
            for i in range(min(self.lines, N)):
                buf[i] = (0, 160, 0)
            return to_bytes(buf)
        while now >= self.next_fall and not self.dead_t:
            if self.collides(self.cells, self.px, self.py + 1):
                self.lock()
            else:
                self.py += 1
            self.next_fall += self.fall_interval()
        buf = [(0, 0, 2)] * N
        for y in range(H):
            for x in range(W):
                if self.field[y][x]:
                    buf[y * W + x] = self.field[y][x]
        if not self.dead_t:
            for dx, dy in self.cells:
                paint(buf, self.px + dx, self.py + dy, self.col)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Reaction Duel (2 players, top vs bottom half, first to 5)
# ---------------------------------------------------------------------------


class Duel(App):
    name = "duel"

    def __init__(self) -> None:
        self.scores = [0, 0]           # [top, bottom]
        self.state = "wait"            # wait | armed | over
        self.t_target = time.monotonic() + random.uniform(1.2, 3.2)
        self.targets = None            # ((x,y) top, (x,y) bottom)
        self.flash = None              # (player, until)
        self.end_t = 0.0

    def new_round(self, now):
        self.state = "wait"
        self.t_target = now + random.uniform(1.2, 3.2)
        self.targets = None

    def score(self, player, now):
        self.scores[player] += 1
        self.flash = (player, now + 0.7)
        if self.scores[player] >= 5:
            log(f"duel: player {'top' if player == 0 else 'bottom'} wins {self.scores}")
            self.state, self.end_t = "over", now
        else:
            self.new_round(now)

    def press(self, idx, now):
        if self.state == "over":
            return
        x, y = idx % W, idx // W
        player = 0 if y < 6 else 1
        if self.state == "wait":               # false start: other player scores
            self.score(1 - player, now)
            return
        tx, ty = self.targets[player]
        if tx <= x <= tx + 1 and ty <= y <= ty + 1:
            self.score(player, now)

    def frame(self, now):
        if self.state == "wait" and now >= self.t_target:
            x = random.randrange(0, W - 1)
            ty = random.randrange(1, 4)
            self.targets = ((x, ty), (W - 2 - x, 11 - ty - 1))
            self.state = "armed"
        if self.state == "over" and now - self.end_t > 3.5:
            self.over = True
        buf = [(0, 0, 0)] * N
        for i in range(self.scores[0]):
            paint(buf, 1 + i * 2, 0, (220, 0, 0))
        for i in range(self.scores[1]):
            paint(buf, 1 + i * 2, 11, (0, 60, 230))
        if self.state == "armed" and self.targets:
            for tx, ty in self.targets:
                block(buf, tx, ty, 2, 2, (255, 255, 255))
        if self.flash and now < self.flash[1]:
            row = 0 if self.flash[0] == 0 else 11
            for x in range(W):
                buf[row * W + x] = (220, 0, 0) if self.flash[0] == 0 else (0, 60, 230)
        if self.state == "over":
            winner = 0 if self.scores[0] >= 5 else 1
            col = (220, 0, 0) if winner == 0 else (0, 60, 230)
            if int(now / 0.35) % 2:
                block(buf, 0, 0 if winner == 0 else 6, 12, 6, col)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Snake (button-steered: press where you want it to go)
# ---------------------------------------------------------------------------


class Snake(App):
    name = "snake"

    def __init__(self) -> None:
        self.body = [(5, 5), (4, 5), (3, 5)]   # head first
        self.d = (1, 0)
        self.pending = None
        self.food = (9, 5)
        self.eaten = 0
        self.grow = 0
        self.step = 0.30
        self.next_step = time.monotonic() + self.step
        self.dead_t = 0.0

    def place_food(self):
        while True:
            p = (random.randrange(W), random.randrange(H))
            if p not in self.body:
                self.food = p
                return

    def press(self, idx, now):
        if self.dead_t:
            return
        x, y = idx % W, idx // W
        hx, hy = self.body[0]
        dx, dy = x - hx, y - hy
        if dx == dy == 0:
            return
        nd = (1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
        if (nd[0] + self.d[0], nd[1] + self.d[1]) != (0, 0):   # no reversing
            self.pending = nd

    def frame(self, now):
        if self.dead_t:
            if now - self.dead_t > 3.5:
                self.over = True
            buf = [(0, 0, 0)] * N
            for i in range(min(self.eaten, N)):
                buf[i] = (0, 160, 0)
            return to_bytes(buf)
        while now >= self.next_step and not self.dead_t:
            if self.pending:
                self.d, self.pending = self.pending, None
            hx, hy = self.body[0]
            nh = ((hx + self.d[0]) % W, (hy + self.d[1]) % H)
            if nh in self.body:
                log(f"snake: dead at {self.eaten} food")
                self.dead_t = now
                break
            self.body.insert(0, nh)
            if nh == self.food:
                self.eaten += 1
                self.grow += 2
                self.step = max(0.15, self.step * 0.96)
                self.place_food()
            if self.grow:
                self.grow -= 1
            else:
                self.body.pop()
            self.next_step += self.step
        buf = [(0, 0, 0)] * N
        for i, (x, y) in enumerate(self.body):
            buf[y * W + x] = (60, 255, 60) if i == 0 else (0, 170, 0)
        fx, fy = self.food
        buf[fy * W + fx] = (255, 0, 0)
        return to_bytes(buf)


# ---------------------------------------------------------------------------
# Menu + end-choice screens
# ---------------------------------------------------------------------------

GAMES = [
    ("mines", Mines, (200, 200, 200), (1, 1)),
    ("moles", Moles, (230, 170, 0), (4, 1)),
    ("simon", Simon, None, (7, 1)),
    ("lights", Lights, (220, 140, 0), (10, 1)),
    ("four", Four, (0, 190, 190), (1, 5)),
    ("sudoku", Sudoku, None, (4, 5)),
    ("pairs", Pairs, None, (7, 5)),
    ("tetris", Tetris, (160, 0, 220), (10, 5)),
    ("duel", Duel, None, (1, 9)),
    ("snake", Snake, (0, 200, 0), (4, 9)),
]

ICON_QUADS = {
    "simon": [(0, 180, 0), (200, 0, 0), (200, 180, 0), (0, 60, 220)],
    "sudoku": [(200, 0, 180), (240, 90, 0), (255, 60, 120), (0, 190, 190)],
    "pairs": [(255, 60, 120), (14, 14, 14), (14, 14, 14), (255, 60, 120)],
    "duel": [(220, 0, 0), (220, 0, 0), (0, 60, 230), (0, 60, 230)],
}


def menu_frame(now) -> bytes:
    buf = [(0, 0, 0)] * N
    for name, _cls, col, (x, y) in GAMES:
        if name in ICON_QUADS:
            q = ICON_QUADS[name]
            paint(buf, x, y, q[0]); paint(buf, x + 1, y, q[1])
            paint(buf, x, y + 1, q[2]); paint(buf, x + 1, y + 1, q[3])
        else:
            block(buf, x, y, 2, 2, col)
    return to_bytes(buf)


def menu_pick(idx) -> type | None:
    x, y = idx % W, idx // W
    best, best_d = None, 99
    for _name, cls, _col, (bx, by) in GAMES:
        dx = max(bx - x, 0, x - (bx + 1))
        dy = max(by - y, 0, y - (by + 1))
        d = max(dx, dy)
        if d < best_d:
            best, best_d = cls, d
    return best if best_d <= 1 else None


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
    log("menu up — 10 games: mines moles simon lights four sudoku pairs tetris duel snake")

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
