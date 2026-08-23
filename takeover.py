#!/usr/bin/env python3
"""Try to wrestle the board out of testmode into paint mode."""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import CALLBACK_CHAR, COMMAND_CHAR, cmd_paint_frame, cmd_start_builtin, dev

ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


BRIGHT = cmd_paint_frame(dev((0, 180, 0)) * 144)  # solid green


async def main() -> None:
    async with BleakClient(ADDRESS, timeout=25) as client:
        await client.start_notify(CALLBACK_CHAR, lambda _s, d: log(f"NOTIFY {len(d)}B: {bytes(d).hex()}"))
        log("connected")
        for attempt in range(5):
            await client.write_gatt_char(COMMAND_CHAR, cmd_start_builtin("paint"), response=True)
            await asyncio.sleep(1.2)
            await client.write_gatt_char(COMMAND_CHAR, BRIGHT, response=True)
            log(f"attempt {attempt + 1}: start paint + solid green frame sent")
            await asyncio.sleep(2.0)
        log("done — if the board is solid green, takeover worked; if still cycling, it needs a power cycle or home-button press")
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
