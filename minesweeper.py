#!/usr/bin/env python3
"""Minesweeper for the Tech Will Save Us Arcade Coder, played on the real board.

Runs on a Mac over Bluetooth LE against the stock firmware:
  - starts the built-in `paint` module
  - renders game frames as compact-canvas paint commands (Huffman-only DEFLATE,
    because the stock inflater corrupts LZ77 backreferences)
  - reads physical button presses by diffing the canvas-state notifications the
    paint module sends on the callback characteristic

Protocol reverse engineering credit: the awesome-arcade-coder community and
LightyCoderDoodad (github.com/diggedypomme/LightyCoderDoodad).
"""

from __future__ import annotations

import asyncio
import json
import random
import struct
import sys
import time
import zlib
from pathlib import Path

SERVICE_UUID = "778d5426-fa29-4363-91fd-a9f5cfcfce85"
COMMAND_CHAR = "e18d056b-7dae-49c1-b5f2-17684801e446"
CALLBACK_CHAR = "21acb4a0-24d0-42f4-8e61-c827daf68d12"

CONFIG_PATH = Path(__file__).resolve().parent / "device_config.json"

W = H = 12
N = W * H
MINE_COUNT = 18

# ---------------------------------------------------------------------------
# Protobuf + compact canvas encoding
# ---------------------------------------------------------------------------


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field_varint(num: int, value: int) -> bytes:
    return _varint((num << 3) | 0) + _varint(value)


def _field_len(num: int, payload: bytes | str) -> bytes:
    if isinstance(payload, str):
        payload = payload.encode()
    return _varint((num << 3) | 2) + _varint(len(payload)) + payload


def _field_f32(num: int, value: float) -> bytes:
    return _varint((num << 3) | 5) + struct.pack("<f", value)


def cmd_start_builtin(module: str, timing: float = 1.0) -> bytes:
    payload = _field_len(1, module) + _field_f32(2, timing)
    return _field_varint(1, 2) + _field_len(4, payload)


def deflate_huffman_only(data: bytes) -> bytes:
    comp = zlib.compressobj(9, zlib.DEFLATED, -15, 8, zlib.Z_HUFFMAN_ONLY)
    return comp.compress(data) + comp.flush()


def inflate_raw(data: bytes) -> bytes:
    dec = zlib.decompressobj(wbits=-15)
    return dec.decompress(data) + dec.flush()


def cmd_paint_frame(device_rgb: bytes) -> bytes:
    """Command type 4 (paint), frame mode, from 432 device-order bytes."""
    assert len(device_rgb) == N * 3
    canvas = bytes([W, H]) + deflate_huffman_only(device_rgb)
    payload = _field_varint(1, 0) + _field_len(2, canvas)
    return _field_varint(1, 4) + _field_len(7, payload)


def extract_canvas(data: bytes) -> bytes | None:
    """Find a 12x12 compact canvas anywhere in a notification; inflate it."""
    for i in range(len(data) - 2):
        if data[i] == W and data[i + 1] == H:
            try:
                raw = inflate_raw(data[i + 2 :])
            except zlib.error:
                continue
            if len(raw) == N * 3:
                return raw
    return None


# ---------------------------------------------------------------------------
# Colours. Display RGB -> device byte order swaps red and blue.
# ---------------------------------------------------------------------------


def dev(rgb: tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    return bytes((b, g, r))


COL_OFF = (0, 0, 0)
COL_COVERED = (28, 28, 28)
COL_MINE = (255, 0, 0)
COL_WIN = (0, 200, 0)
NUMBER_COLS = {
    1: (0, 0, 220),      # blue
    2: (0, 200, 0),      # green
    3: (230, 200, 0),    # yellow
    4: (230, 90, 0),     # orange
    5: (220, 0, 180),    # magenta
    6: (0, 200, 200),    # cyan
    7: (255, 255, 255),  # white
    8: (255, 40, 40),    # light red
}


# ---------------------------------------------------------------------------
# Minesweeper game state
# ---------------------------------------------------------------------------


class Game:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.mines: set[int] = set()
        self.revealed: set[int] = set()
        self.counts = [0] * N
        self.placed = False
        self.over = False
        self.won = False

    @staticmethod
    def neighbors(idx: int):
        x, y = idx % W, idx // W
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    yield ny * W + nx

    def place_mines(self, safe_idx: int) -> None:
        forbidden = {safe_idx, *self.neighbors(safe_idx)}
        pool = [i for i in range(N) if i not in forbidden]
        self.mines = set(random.sample(pool, MINE_COUNT))
        for i in range(N):
            self.counts[i] = sum(1 for n in self.neighbors(i) if n in self.mines)
        self.placed = True

    def press(self, idx: int) -> str:
        """Returns 'boom', 'win', 'reveal' or 'noop'."""
        if self.over or idx in self.revealed:
            return "noop"
        if not self.placed:
            self.place_mines(idx)
        if idx in self.mines:
            self.over = True
            return "boom"
        # flood reveal
        stack = [idx]
        while stack:
            cur = stack.pop()
            if cur in self.revealed or cur in self.mines:
                continue
            self.revealed.add(cur)
            if self.counts[cur] == 0:
                stack.extend(n for n in self.neighbors(cur) if n not in self.revealed)
        if len(self.revealed) == N - len(self.mines):
            self.over = True
            self.won = True
            return "win"
        return "reveal"

    def framebuffer(self, show_mines: bool = False) -> bytes:
        buf = bytearray()
        for i in range(N):
            if show_mines and i in self.mines:
                buf += dev(COL_MINE)
            elif i in self.revealed:
                c = self.counts[i]
                buf += dev(NUMBER_COLS[c]) if c else dev(COL_OFF)
            else:
                buf += dev(COL_COVERED)
        return bytes(buf)

    def ascii(self) -> str:
        rows = []
        for y in range(H):
            row = ""
            for x in range(W):
                i = y * W + x
                if i in self.mines and self.over:
                    row += "*"
                elif i in self.revealed:
                    row += str(self.counts[i]) if self.counts[i] else "."
                else:
                    row += "#"
            rows.append(row)
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# BLE plumbing
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Board:
    def __init__(self) -> None:
        self.client = None
        self.notify_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.frag = b""
        self.frag_time = 0.0
        # recent framebuffers we've sent, newest last (diff targets)
        self.sent_frames: list[bytes] = []
        self.disconnected = asyncio.Event()

    def on_notify(self, _sender, data: bytearray) -> None:
        self.notify_queue.put_nowait(bytes(data))

    def on_disconnect(self, _client) -> None:
        log("BLE disconnected")
        self.disconnected.set()

    async def find_address(self) -> str:
        if CONFIG_PATH.exists():
            try:
                addr = json.loads(CONFIG_PATH.read_text()).get("address")
                if addr:
                    log(f"using saved address {addr}")
                    return addr
            except Exception:
                pass
        from bleak import BleakScanner

        log("scanning for Arcade Coder...")
        for attempt in range(30):
            devices = await BleakScanner.discover(timeout=6.0, return_adv=True)
            for address, (device, adv) in devices.items():
                name = device.name or adv.local_name or ""
                uuids = [u.lower() for u in (adv.service_uuids or [])]
                if SERVICE_UUID in uuids or "arcade" in name.lower() or "coder" in name.lower():
                    log(f"found {name or '(unnamed)'} at {address}")
                    CONFIG_PATH.write_text(json.dumps({"address": address, "name": name}, indent=2))
                    return address
            log(f"scan {attempt + 1}: board not found (is it powered on?), retrying...")
            await asyncio.sleep(4)
        raise RuntimeError("Arcade Coder not found after repeated scans")

    async def connect(self) -> None:
        from bleak import BleakClient

        address = await self.find_address()
        self.disconnected.clear()
        client = BleakClient(address, disconnected_callback=self.on_disconnect)
        await asyncio.wait_for(client.connect(), timeout=25)
        await asyncio.sleep(1.5)  # allow service discovery to settle
        await client.start_notify(CALLBACK_CHAR, self.on_notify)
        self.client = client
        log("connected, notifications on")

    async def send_command(self, payload: bytes) -> None:
        # the command characteristic only supports write-with-response
        # (props=['write']); CoreBluetooth silently drops response=False writes
        await asyncio.wait_for(
            self.client.write_gatt_char(COMMAND_CHAR, payload, response=True), timeout=8
        )

    async def start_paint(self) -> None:
        await self.send_command(cmd_start_builtin("paint"))
        log("paint module started")
        await asyncio.sleep(0.8)

    async def send_frame(self, device_rgb: bytes) -> None:
        await self.send_command(cmd_paint_frame(device_rgb))
        self.sent_frames.append(device_rgb)
        self.sent_frames = self.sent_frames[-4:]

    def decode_presses(self, data: bytes) -> list[int] | None:
        """Return pressed pixel indices, or None if the payload isn't a canvas."""
        canvas = extract_canvas(data)
        if canvas is None:
            # maybe a fragmented notification: try joining with the previous one
            now = time.monotonic()
            if self.frag and now - self.frag_time < 2.0:
                canvas = extract_canvas(self.frag + data)
            if canvas is None:
                self.frag = self.frag + data if self.frag and now - self.frag_time < 2.0 else data
                self.frag_time = now
                return None
        self.frag = b""
        best: list[int] | None = None
        for frame in reversed(self.sent_frames):
            changed = [i for i in range(N) if canvas[i * 3 : i * 3 + 3] != frame[i * 3 : i * 3 + 3]]
            if best is None or len(changed) < len(best):
                best = changed
        if best is None:
            return []
        if len(best) > 4:
            log(f"ignoring notification with {len(best)} changed pixels (stale repaint?)")
            return []
        # a real press paints the paint module's brush colour onto the canvas;
        # anything else is a stale-frame artifact (e.g. a timer bar that moved)
        BRUSH = bytes((5, 20, 220))
        return [i for i in best if canvas[i * 3 : i * 3 + 3] == BRUSH]


# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------


def solid(rgb: tuple[int, int, int]) -> bytes:
    return dev(rgb) * N


async def animate_boom(board: Board, game: Game) -> None:
    reveal = game.framebuffer(show_mines=True)
    for _ in range(3):
        await board.send_frame(reveal)
        await asyncio.sleep(0.45)
        await board.send_frame(solid((120, 0, 0)))
        await asyncio.sleep(0.25)
    await board.send_frame(reveal)
    await asyncio.sleep(2.5)


async def animate_win(board: Board, game: Game) -> None:
    for _ in range(3):
        await board.send_frame(solid(COL_WIN))
        await asyncio.sleep(0.35)
        await board.send_frame(game.framebuffer())
        await asyncio.sleep(0.35)
    await asyncio.sleep(1.5)


async def animate_intro(board: Board) -> None:
    # quick expanding diamond so you can see a new game starting
    cx, cy = 5.5, 5.5
    for radius in range(0, 10, 2):
        buf = bytearray()
        for i in range(N):
            x, y = i % W, i // W
            d = abs(x - cx) + abs(y - cy)
            buf += dev((0, 60, 90)) if d <= radius else dev(COL_OFF)
        await board.send_frame(bytes(buf))
        await asyncio.sleep(0.12)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def run_game(board: Board) -> None:
    game = Game()
    await animate_intro(board)
    await board.send_frame(game.framebuffer())
    log("new game — 12x12, %d mines. Press any pad!" % MINE_COUNT)

    while True:
        get = asyncio.create_task(board.notify_queue.get())
        done, _ = await asyncio.wait(
            {get, asyncio.create_task(board.disconnected.wait())},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if board.disconnected.is_set():
            get.cancel()
            raise ConnectionError("disconnected")
        data = get.result()
        presses = board.decode_presses(data)
        if presses is None:
            log(f"notify (unparsed, {len(data)}B): {data.hex()}")
            continue
        if not presses:
            continue
        for idx in presses:
            x, y = idx % W, idx // W
            result = game.press(idx)
            log(f"press ({x},{y}) -> {result}")
            if result == "boom":
                log("BOOM! game over\n" + game.ascii())
                await animate_boom(board, game)
                game = Game()
                await animate_intro(board)
                await board.send_frame(game.framebuffer())
                log("new game — press any pad!")
                break
            elif result == "win":
                log("WIN! board cleared\n" + game.ascii())
                await animate_win(board, game)
                game = Game()
                await animate_intro(board)
                await board.send_frame(game.framebuffer())
                log("new game — press any pad!")
                break
        else:
            # repaint (also wipes the brush pixel the firmware painted)
            await board.send_frame(game.framebuffer())
        # drain any burst of queued notifications that arrived mid-update
        while not board.notify_queue.empty():
            extra = board.notify_queue.get_nowait()
            extra_presses = board.decode_presses(extra)
            if extra_presses:
                for idx in extra_presses:
                    result = game.press(idx)
                    log(f"press ({idx % W},{idx // W}) -> {result} (burst)")
                await board.send_frame(game.framebuffer())


async def main() -> None:
    board = Board()
    while True:
        try:
            await board.connect()
            await board.start_paint()
            await run_game(board)
        except (ConnectionError, TimeoutError, asyncio.TimeoutError) as exc:
            log(f"connection problem: {exc!r}; retrying in 4s")
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
