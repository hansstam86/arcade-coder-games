#!/usr/bin/env python3
"""Noughts & Crosses (Tic-Tac-Toe) for the Arcade Coder.

A big 3x3 board: tap a cell to place your mark. X (red) goes first, then O
(cyan). Win three in a row and the line pulses; a full board is a draw. After
the game ends, tap anywhere to play again.

Two-player hot-seat by default. Tap the right-edge pad to toggle a perfect
CPU opponent (it plays O — the best you'll manage is a draw).

  python tictactoe.py         # emulator
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

W = H = 12
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),        # rows
         (0, 3, 6), (1, 4, 7), (2, 5, 8),        # cols
         (0, 4, 8), (2, 4, 6)]                   # diagonals
X_COL = (255, 40, 40)
O_COL = (0, 210, 220)
GRID = (34, 34, 44)
MODE_PAD = (11, 6)                               # toggle CPU opponent


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def winner_of(b):
    for a, c, d in LINES:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a], (a, c, d)
    if all(b):
        return 0, None                           # draw
    return None, None


def _score(b, o_turn):
    w, _ = winner_of(b)
    if w == 2:
        return 1
    if w == 1:
        return -1
    if w == 0:
        return 0
    mark = 2 if o_turn else 1
    vals = []
    for i in range(9):
        if b[i] == 0:
            b[i] = mark
            vals.append(_score(b, not o_turn))
            b[i] = 0
    return max(vals) if o_turn else min(vals)


def best_move(b):                                # O (2) to move — perfect play
    best, bs = None, -2
    for i in range(9):
        if b[i] == 0:
            b[i] = 2
            s = _score(b, False)
            b[i] = 0
            if s > bs:
                bs, best = s, i
    return best


class TicTacToe(Game):
    fps = 10

    def start(self):
        self.vs_cpu = False
        self._reset()
        log("noughts & crosses — X starts; right pad toggles CPU")

    def _reset(self):
        self.board = [0] * 9
        self.turn = 1                            # 1 = X, 2 = O
        self.winner = None                       # None playing, 0 draw, 1/2 win
        self.win_line = None
        self.over_at = 0.0

    def _finish(self):
        w, line = winner_of(self.board)
        if w is not None:
            self.winner, self.win_line = w, line
            self.over_at = time.monotonic()
            log("draw" if w == 0 else f"{'X' if w == 1 else 'O'} wins")
            return True
        return False

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if (x, y) == MODE_PAD:                   # toggle CPU + restart
            self.vs_cpu = not self.vs_cpu
            self._reset()
            log(f"mode: {'vs CPU' if self.vs_cpu else '2 players'}")
            return
        if self.winner is not None:              # game over -> tap to replay
            if time.monotonic() - self.over_at > 0.4:
                self._reset()
            return
        if x % 4 == 3 or y % 4 == 3 or x > 10 or y > 10:
            return                               # grid line / status area
        i = (y // 4) * 3 + (x // 4)
        if self.board[i] != 0:
            return
        self.board[i] = self.turn
        if self._finish():
            return
        self.turn = 2 if self.turn == 1 else 1
        if self.vs_cpu and self.turn == 2:       # CPU replies as O
            mv = best_move(self.board)
            if mv is not None:
                self.board[mv] = 2
                if not self._finish():
                    self.turn = 1

    def update(self, dt):
        pass

    # -- render --------------------------------------------------------------
    def _mark(self, screen, cell, mark, color):
        ox, oy = (cell % 3) * 4, (cell // 3) * 4
        if mark == 1:                            # X
            for dx, dy in ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)):
                screen.set(ox + dx, oy + dy, color)
        else:                                    # O (ring)
            for dx, dy in ((0, 0), (1, 0), (2, 0), (0, 1), (2, 1),
                           (0, 2), (1, 2), (2, 2)):
                screen.set(ox + dx, oy + dy, color)

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        for gx in (3, 7):                        # grid lines
            for gy in range(11):
                screen.set(gx, gy, GRID)
        for gy in (3, 7):
            for gx in range(11):
                screen.set(gx, gy, GRID)

        pulse = 0.5 + 0.5 * abs((now * 2) % 2 - 1)
        for i, v in enumerate(self.board):
            if not v:
                continue
            color = X_COL if v == 1 else O_COL
            if self.win_line and i in self.win_line:
                color = tuple(min(255, int(c * (0.5 + pulse))) for c in color)
            self._mark(screen, i, v, color)

        # status: bottom row = whose turn / result
        if self.winner is None:
            tc = X_COL if self.turn == 1 else O_COL
            for x in range(11):
                screen.set(x, 11, tuple(c // 3 for c in tc))
        elif self.winner == 0:                   # draw
            for x in range(11):
                screen.set(x, 11, (60, 60, 60))
        else:
            wc = X_COL if self.winner == 1 else O_COL
            for x in range(11):
                screen.set(x, 11, tuple(min(255, int(c * pulse)) for c in wc))

        # mode pad (right edge): green = 2P, blue = vs CPU
        screen.set(*MODE_PAD, (0, 130, 255) if self.vs_cpu else (0, 180, 80))


if __name__ == "__main__":
    run(TicTacToe)
