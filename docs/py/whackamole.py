#!/usr/bin/env python3
"""Whack-a-Mole on the Arcade Coder — Mac-driven over BLE stock paint mode.

Reuses the minesweeper BLE plumbing: frames out via paint commands, physical
pad presses back via canvas-state notifications (diffed against sent frames).
"""

from __future__ import annotations

import asyncio
import random
import time

from minesweeper import Board, W, H, N, dev, log

ROUND_SECONDS = 45.0
PLAY_ROWS = 11          # rows 0..10 are the mole field; row 11 is the timer bar

COL_BG = (0, 0, 0)
COL_MOLE = (230, 170, 0)      # yellow
COL_MISS = (200, 0, 0)        # expired mole flash
COL_TIMER = (0, 40, 120)      # bottom bar
COL_SCORE = (0, 200, 0)


class Mole:
    def __init__(self, x: int, y: int, expiry: float) -> None:
        self.x, self.y, self.expiry = x, y, expiry

    def cells(self) -> list[int]:
        return [self.y * W + self.x]


class Game:
    def __init__(self) -> None:
        self.moles: list[Mole] = []
        self.score = 0
        self.misses = 0
        self.t_end = time.monotonic() + ROUND_SECONDS
        self.next_spawn = time.monotonic() + 0.6
        self.flash: dict[int, float] = {}  # cell -> until (red miss flashes)

    def max_concurrent(self) -> int:
        return min(4, 1 + self.score // 8)

    def spawn_interval(self) -> float:
        return max(0.7, 1.8 - self.score * 0.03)

    def lifetime(self) -> float:
        return max(1.1, 3.0 - self.score * 0.05)

    def occupied(self) -> set[int]:
        return {c for m in self.moles for c in m.cells()}

    def spawn(self) -> None:
        taken = self.occupied()
        for _ in range(40):
            x = random.randrange(0, W)
            y = random.randrange(0, PLAY_ROWS)
            mole = Mole(x, y, time.monotonic() + self.lifetime())
            if not (set(mole.cells()) & taken):
                self.moles.append(mole)
                return

    def tick(self, now: float) -> None:
        for mole in list(self.moles):
            if now >= mole.expiry:
                self.moles.remove(mole)
                self.misses += 1
                for c in mole.cells():
                    self.flash[c] = now + 0.4
        if now >= self.next_spawn and len(self.moles) < self.max_concurrent():
            self.spawn()
            self.next_spawn = now + self.spawn_interval()
        self.flash = {c: t for c, t in self.flash.items() if t > now}

    def whack(self, idx: int) -> bool:
        for mole in self.moles:
            if idx in mole.cells():
                self.moles.remove(mole)
                self.score += 1
                return True
        return False

    def framebuffer(self, now: float) -> bytes:
        buf = [COL_BG] * N
        for c, _t in self.flash.items():
            buf[c] = COL_MISS
        for mole in self.moles:
            for c in mole.cells():
                buf[c] = COL_MOLE
        remaining = max(0.0, self.t_end - now)
        bar = round(W * remaining / ROUND_SECONDS)
        for x in range(bar):
            buf[11 * W + x] = COL_TIMER
        return b"".join(dev(c) for c in buf)


def score_frame(score: int) -> bytes:
    buf = [COL_BG] * N
    for i in range(min(score, N)):
        buf[i] = COL_SCORE
    return b"".join(dev(c) for c in buf)


async def run_game(board: Board) -> None:
    while True:
        game = Game()
        log("new round — whack the yellow moles! 45 seconds")
        while not board.notify_queue.empty():  # drop stale pre-round presses
            board.notify_queue.get_nowait()
        last_frame = b""
        while True:
            now = time.monotonic()
            if now >= game.t_end:
                break
            game.tick(now)
            frame = game.framebuffer(now)
            if frame != last_frame:
                await board.send_frame(frame)
                last_frame = frame
            # poll notifications with a short timeout to keep the clock running
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
                if game.whack(idx):
                    log(f"WHACK at ({idx % W},{idx // W}) — score {game.score}")
                else:
                    log(f"miss press at ({idx % W},{idx // W})")
            last_frame = b""  # force redraw (also wipes the firmware brush pixel)
        log(f"round over — score {game.score}, missed moles {game.misses}")
        await board.send_frame(score_frame(game.score))
        await asyncio.sleep(4.0)


async def main() -> None:
    board = Board()
    while True:
        try:
            await board.connect()
            await board.start_paint()
            await run_game(board)
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
