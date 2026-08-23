#!/usr/bin/env python3
"""Listen on ALL notify characteristics while the user tilts/shakes the board."""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import CALLBACK_CHAR, COMMAND_CHAR, cmd_paint_frame, cmd_start_builtin, dev

ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]
UNKNOWN_NOTIFY = "9bb6e8cc-94d3-4228-8cb7-86e40bf3bde5"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main() -> None:
    async with BleakClient(ADDRESS, timeout=25) as client:
        log("connected")

        def cb(tag):
            def handler(_s, d):
                log(f"NOTIFY[{tag}] {len(d)}B: {bytes(d).hex()}")
            return handler

        await client.start_notify(CALLBACK_CHAR, cb("stock"))
        try:
            await client.start_notify(UNKNOWN_NOTIFY, cb("unknown-svc"))
            log("subscribed to unknown service notify char too")
        except Exception as exc:
            log(f"could not subscribe unknown notify char: {exc!r}")

        # also read the readable chars once
        for uuid in (CALLBACK_CHAR, UNKNOWN_NOTIFY):
            try:
                val = await client.read_gatt_char(uuid)
                log(f"READ {uuid[:8]}: {bytes(val).hex()}")
            except Exception as exc:
                log(f"read {uuid[:8]} failed: {exc!r}")

        await client.write_gatt_char(COMMAND_CHAR, cmd_start_builtin("paint"), response=True)
        await asyncio.sleep(1.0)
        # visible cue: solid dim blue = "tilt now"
        await client.write_gatt_char(COMMAND_CHAR, cmd_paint_frame(dev((0, 0, 60)) * 144), response=True)
        log("== paint started, board dim blue. TILT the board every direction, then SHAKE it (60s window)")
        await asyncio.sleep(60)
        log("observation done")


if __name__ == "__main__":
    asyncio.run(main())
