#!/usr/bin/env python3
"""Othello / Reversi for the Arcade Coder.

The classic 8x8 board, centred in the grid. Place a disc to flank a line of
your opponent's discs and they all flip to your colour. Dark (blue) moves
first, then Light (white). Legal squares glow faintly in your colour; if you
have no move your turn is passed automatically. When neither side can move the
game ends and the most discs wins — the frame pulses in the winner's colour.

The bottom row is a live score bar (blue vs white). Two-player hot-seat by
default; the right-edge pad toggles a CPU opponent (it plays Light).

  python othello.py           # emulator
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

N = 8
OX, OY = 2, 2                      # board's top-left on the 12x12 screen
DARK, LIGHT = 1, 2
DARK_COL = (40, 100, 255)
LIGHT_COL = (240, 240, 240)
EMPTY_COL = (0, 20, 9)
MODE_PAD = (11, 6)
DIRS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
WEIGHTS = [
    120, -20, 20, 5, 5, 20, -20, 120,
    -20, -40, -5, -5, -5, -5, -40, -20,
    20, -5, 15, 3, 3, 15, -5, 20,
    5, -5, 3, 3, 3, 3, -5, 5,
    5, -5, 3, 3, 3, 3, -5, 5,
    20, -5, 15, 3, 3, 15, -5, 20,
    -20, -40, -5, -5, -5, -5, -40, -20,
    120, -20, 20, 5, 5, 20, -20, 120,
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def flips_for(board, cell, player):
    if board[cell] != 0:
        return []
    opp = 3 - player
    c0, r0 = cell % N, cell // N
    out = []
    for dc, dr in DIRS:
        c, r, line = c0 + dc, r0 + dr, []
        while 0 <= c < N and 0 <= r < N and board[r * N + c] == opp:
            line.append(r * N + c)
            c += dc; r += dr
        if line and 0 <= c < N and 0 <= r < N and board[r * N + c] == player:
            out.extend(line)
    return out


def legal_moves(board, player):
    return [i for i in range(N * N) if board[i] == 0 and flips_for(board, i, player)]


def _apply(board, cell, player):
    b = board[:]
    b[cell] = player
    for f in flips_for(board, cell, player):
        b[f] = player
    return b


def _evaluate(board, player):
    opp = 3 - player
    score = 0
    for i in range(N * N):
        if board[i] == player:
            score += WEIGHTS[i]
        elif board[i] == opp:
            score -= WEIGHTS[i]
    score += 8 * (len(legal_moves(board, player)) - len(legal_moves(board, opp)))
    return score


def _negamax(board, player, depth):
    moves = legal_moves(board, player)
    opp = 3 - player
    if not moves:
        if not legal_moves(board, opp):
            diff = board.count(player) - board.count(opp)
            return 10000 * (1 if diff > 0 else -1 if diff < 0 else 0)
        return -_negamax(board, opp, depth)          # pass
    if depth == 0:
        return _evaluate(board, player)
    best = -1 << 30
    for m in moves:
        best = max(best, -_negamax(_apply(board, m, player), opp, depth - 1))
    return best


def best_move(board, player, depth=3):
    best, bs = None, -(1 << 31)
    for m in legal_moves(board, player):
        v = -_negamax(_apply(board, m, player), 3 - player, depth - 1)
        if v > bs:
            bs, best = v, m
    return best


class Othello(Game):
    fps = 10

    def start(self):
        self.vs_cpu = False
        self._reset()
        log("othello — Dark first; right pad toggles CPU")

    def _reset(self):
        self.board = [0] * (N * N)
        self.board[3 * N + 3] = self.board[4 * N + 4] = LIGHT
        self.board[3 * N + 4] = self.board[4 * N + 3] = DARK
        self.player = DARK
        self.winner = None          # None playing, 0 draw, 1/2 winner
        self.over_at = 0.0
        self.flash = None           # (cells, until) recently flipped

    def _finish(self):
        d, l = self.board.count(DARK), self.board.count(LIGHT)
        self.winner = 0 if d == l else (DARK if d > l else LIGHT)
        self.over_at = time.monotonic()
        log(f"game over — Dark {d} : Light {l}")

    def _place(self, cell, player):
        fl = flips_for(self.board, cell, player)
        if not fl:
            return False
        self.board[cell] = player
        for f in fl:
            self.board[f] = player
        self.flash = (fl + [cell], time.monotonic() + 0.3)
        return True

    def _next_turn(self):
        opp = 3 - self.player
        if legal_moves(self.board, opp):
            self.player = opp
        elif legal_moves(self.board, self.player):
            pass                                     # opponent passes
        else:
            self._finish()
            return
        if self.winner is None and self.vs_cpu and self.player == LIGHT:
            mv = best_move(self.board, LIGHT)
            if mv is not None:
                self._place(mv, LIGHT)
            self._next_turn()

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        if x == 11 and y in (5, 6):              # CPU toggle (right-edge button)
            self.vs_cpu = not self.vs_cpu
            self._reset()
            log(f"mode: {'vs CPU' if self.vs_cpu else '2 players'}")
            return
        if self.winner is not None:
            if time.monotonic() - self.over_at > 0.4:
                self._reset()
            return
        c, r = x - OX, y - OY
        if not (0 <= c < N and 0 <= r < N):
            return
        if self._place(r * N + c, self.player):
            self._next_turn()

    def update(self, dt):
        pass

    # -- render --------------------------------------------------------------
    def draw(self, screen):
        now = time.monotonic()
        screen.clear((0, 0, 0))
        pulse = 0.5 + 0.5 * abs((now * 2) % 2 - 1)
        legal = set(legal_moves(self.board, self.player)) if self.winner is None else set()
        flashing = self.flash[0] if (self.flash and now < self.flash[1]) else []

        for i in range(N * N):
            c, r = i % N, i // N
            v = self.board[i]
            if v == DARK:
                col = DARK_COL
            elif v == LIGHT:
                col = LIGHT_COL
            elif i in legal:                         # faint legal-move hint
                base = DARK_COL if self.player == DARK else LIGHT_COL
                col = tuple(int(ch * 0.16) for ch in base)
            else:
                col = EMPTY_COL
            if i in flashing:
                col = (255, 255, 255)
            screen.set(OX + c, OY + r, col)

        # frame shows whose turn (or pulses for the winner)
        if self.winner is None:
            fc = DARK_COL if self.player == DARK else LIGHT_COL
            frame = tuple(int(ch * 0.35) for ch in fc)
        elif self.winner == 0:
            frame = (70, 70, 70)
        else:
            wc = DARK_COL if self.winner == DARK else LIGHT_COL
            frame = tuple(min(255, int(ch * pulse)) for ch in wc)
        for k in range(1, 11):
            screen.set(1, k, frame); screen.set(10, k, frame)
            screen.set(k, 1, frame); screen.set(k, 10, frame)

        # bottom-row score bar: blue (dark) vs white (light)
        d, l = self.board.count(DARK), self.board.count(LIGHT)
        split = round(d / max(1, d + l) * 12)
        for x in range(12):
            screen.set(x, 11, DARK_COL if x < split else LIGHT_COL)

        # CPU toggle button (right edge) — pulses at the start to invite a tap
        mp = (0, 130, 255) if self.vs_cpu else (0, 190, 90)
        if self.board.count(DARK) + self.board.count(LIGHT) == 4:   # fresh game
            f = 0.35 + 0.65 * pulse
            mp = tuple(int(ch * f) for ch in mp)
        screen.set(11, 5, mp); screen.set(11, 6, mp)


if __name__ == "__main__":
    run(Othello)
