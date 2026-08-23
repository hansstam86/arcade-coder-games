#!/usr/bin/env python3
"""Diagnostic session against the Arcade Coder: services, testmode, known-good canvas."""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import (
    CALLBACK_CHAR,
    COMMAND_CHAR,
    SERVICE_UUID,
    cmd_paint_frame,
    cmd_start_builtin,
    _field_varint,
    _field_len,
    dev,
)

CONFIG = json.loads((Path(__file__).parent / "device_config.json").read_text())
ADDRESS = CONFIG["address"]

# hardware-proven captured canvas: bottom-right pixel red (community capture)
KNOWN_CANVAS = bytes.fromhex("0c0c6318050c4306b08adc0100")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def canvas_command(canvas: bytes) -> bytes:
    payload = _field_varint(1, 0) + _field_len(2, canvas)
    return _field_varint(1, 4) + _field_len(7, payload)


async def main() -> None:
    log(f"connecting to {ADDRESS}")
    async with BleakClient(ADDRESS, timeout=25) as client:
        log("connected; enumerating services")
        for service in client.services:
            log(f"service {service.uuid}")
            for ch in service.characteristics:
                log(f"  char {ch.uuid} props={ch.properties}")

        await client.start_notify(CALLBACK_CHAR, lambda _s, d: log(f"NOTIFY {len(d)}B: {bytes(d).hex()}"))
        log("notifications on")

        async def write(label: str, payload: bytes, response: bool) -> None:
            try:
                await asyncio.wait_for(
                    client.write_gatt_char(COMMAND_CHAR, payload, response=response), timeout=8
                )
                log(f"write OK ({label}, response={response}, {len(payload)}B)")
            except Exception as exc:
                log(f"write FAILED ({label}, response={response}): {exc!r}")

        # 1. testmode: built-in demo, should visibly light the matrix
        await write("start testmode", cmd_start_builtin("testmode"), True)
        log("== check the board: testmode should show a colour demo (10s wait)")
        await asyncio.sleep(10)

        # 2. paint + known-good captured canvas (bottom-right red)
        await write("start paint", cmd_start_builtin("paint"), True)
        await asyncio.sleep(2)
        await write("known-good canvas", canvas_command(KNOWN_CANVAS), True)
        log("== check the board: bottom-right pixel should be red (8s wait)")
        await asyncio.sleep(8)

        # 3. my generated frame: solid dim white
        await write("my solid frame", cmd_paint_frame(dev((40, 40, 40)) * 144), True)
        log("== check the board: whole matrix dim white (8s wait)")
        await asyncio.sleep(8)

        # 4. wait for a button press notification
        log("== press any pad on the board now (20s window)")
        await asyncio.sleep(20)
        log("diagnostic done")


if __name__ == "__main__":
    asyncio.run(main())
