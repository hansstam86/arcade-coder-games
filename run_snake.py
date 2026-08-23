#!/usr/bin/env python3
"""Upload + start the snake game on a freshly-booted (idle) board."""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import CALLBACK_CHAR, COMMAND_CHAR
from snake_upload import GAME_CHAR, SNEK, cmd_start_game, game_upload

ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]
FREQ = 8.0  # the only hardware-proven VM tick frequency


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main() -> None:
    for attempt in range(20):
        try:
            async with BleakClient(ADDRESS, timeout=25) as client:
                await client.start_notify(
                    CALLBACK_CHAR, lambda _s, d: log(f"NOTIFY {len(d)}B: {bytes(d).hex()}")
                )
                log("connected")
                await client.write_gatt_char(GAME_CHAR, game_upload("sk", SNEK), response=True)
                log("uploaded sk (%d bytes)" % len(game_upload("sk", SNEK)))
                await asyncio.sleep(2.5)
                await client.write_gatt_char(COMMAND_CHAR, cmd_start_game("sk", FREQ), response=True)
                log(f"== started sk at {FREQ:g} Hz — snake should be on the board")
                while True:
                    await asyncio.sleep(60)
                    log("still connected")
        except Exception as exc:
            log(f"session ended: {exc!r}; reconnecting in 5s")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
