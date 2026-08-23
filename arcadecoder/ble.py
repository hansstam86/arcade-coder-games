"""BLE backend: run an SDK Game on a real Arcade Coder over stock firmware.

macOS note: run through an app bundle carrying NSBluetoothAlwaysUsageDescription
(TCC kills bare CoreBluetooth processes) — see the repo README.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from . import Game, N, W
from .protocol import (
    BRUSH,
    CALLBACK_CHAR,
    COMMAND_CHAR,
    SERVICE_UUID,
    cmd_paint_frame,
    cmd_start_builtin,
    extract_canvas,
)
from .runner import GameLoop

CONFIG_PATH = Path.cwd() / "device_config.json"
SEND_MIN_INTERVAL = 0.2  # sustained faster writes drop the BLE connection


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Board:
    def __init__(self) -> None:
        self.client = None
        self.notify_queue: asyncio.Queue[bytes] = asyncio.Queue()
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
                    return addr
            except Exception:
                pass
        from bleak import BleakScanner

        log("scanning for Arcade Coder...")
        for _ in range(30):
            devices = await BleakScanner.discover(timeout=6.0, return_adv=True)
            for address, (device, adv) in devices.items():
                name = device.name or adv.local_name or ""
                uuids = [u.lower() for u in (adv.service_uuids or [])]
                if SERVICE_UUID in uuids or "arcade" in name.lower() or "coder" in name.lower():
                    log(f"found {name or '(unnamed)'} at {address}")
                    CONFIG_PATH.write_text(json.dumps({"address": address, "name": name}, indent=2))
                    return address
            await asyncio.sleep(4)
        raise RuntimeError("Arcade Coder not found (is it powered on?)")

    async def connect(self) -> None:
        from bleak import BleakClient

        address = await self.find_address()
        self.disconnected.clear()
        client = BleakClient(address, disconnected_callback=self.on_disconnect)
        await asyncio.wait_for(client.connect(), timeout=25)
        await asyncio.sleep(1.5)
        await client.start_notify(CALLBACK_CHAR, self.on_notify)
        self.client = client
        log("connected")

    async def send_command(self, payload: bytes) -> None:
        # command char only supports write-with-response; CoreBluetooth
        # silently drops response=False writes on it
        await asyncio.wait_for(
            self.client.write_gatt_char(COMMAND_CHAR, payload, response=True), timeout=8
        )

    async def start_paint(self) -> None:
        await self.send_command(cmd_start_builtin("paint"))
        await asyncio.sleep(0.8)

    async def send_frame(self, device_rgb: bytes) -> None:
        await self.send_command(cmd_paint_frame(device_rgb))
        self.sent_frames.append(device_rgb)
        self.sent_frames = self.sent_frames[-4:]

    def decode_presses(self, data: bytes) -> list[int]:
        canvas = extract_canvas(data)
        if canvas is None:
            return []
        best: list[int] | None = None
        for frame in reversed(self.sent_frames):
            changed = [i for i in range(N) if canvas[i * 3 : i * 3 + 3] != frame[i * 3 : i * 3 + 3]]
            if best is None or len(changed) < len(best):
                best = changed
        if not best or len(best) > 4:
            return []
        return [i for i in best if canvas[i * 3 : i * 3 + 3] == BRUSH]


async def _run(game_cls: type[Game]) -> None:
    board = Board()
    while True:
        try:
            await board.connect()
            await board.start_paint()
            loop = GameLoop(game_cls)
            last_sent = b""
            last_send_t = 0.0
            while not board.notify_queue.empty():
                board.notify_queue.get_nowait()
            while True:
                now = time.monotonic()
                loop.tick()
                frame = loop.frame_device_bytes()
                if frame != last_sent and now - last_send_t >= SEND_MIN_INTERVAL:
                    await board.send_frame(frame)
                    last_sent, last_send_t = frame, now
                try:
                    data = await asyncio.wait_for(board.notify_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if board.disconnected.is_set():
                        raise ConnectionError("disconnected")
                    continue
                for idx in board.decode_presses(data):
                    loop.press(idx % W, idx // W)
                last_sent = b""  # repaint to wipe the firmware brush pixel
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


def run_ble(game_cls: type[Game]) -> None:
    asyncio.run(_run(game_cls))
