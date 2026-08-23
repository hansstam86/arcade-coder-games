#!/usr/bin/env python3
"""Control: start the saved 'sk' game (known dead-strip) + a known-exotic builtin."""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import CALLBACK_CHAR, COMMAND_CHAR
from snake_upload import GAME_CHAR, cmd_start_game, game_upload

ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ascii_run(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


async def main() -> None:
    async with BleakClient(ADDRESS, timeout=25) as client:
        await client.start_notify(
            CALLBACK_CHAR, lambda _s, d: log(f"NOTIFY: {ascii_run(bytes(d))} | {bytes(d).hex()}")
        )
        log("connected")
        log("== control 1: start saved 'sk' (expect dead strip error)")
        await client.write_gatt_char(COMMAND_CHAR, cmd_start_game("sk", 8.0), response=True)
        await asyncio.sleep(3)
        log("== control 2: JSON.stringify probe (likely stripped)")
        await client.write_gatt_char(GAME_CHAR, game_upload("tj", ';var s=JSON.stringify([1]);'), response=True)
        await asyncio.sleep(1.2)
        await client.write_gatt_char(COMMAND_CHAR, cmd_start_game("tj", 8.0), response=True)
        await asyncio.sleep(3)
        log("done")


if __name__ == "__main__":
    asyncio.run(main())
