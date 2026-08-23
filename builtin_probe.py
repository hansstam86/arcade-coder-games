#!/usr/bin/env python3
"""Empirically determine which JS builtins survive in the stock firmware.

Uploads one tiny game per builtin and watches BLE notifications for
"dead strip" / other VM errors. No display needed.
"""
import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import CALLBACK_CHAR, COMMAND_CHAR
from snake_upload import GAME_CHAR, cmd_start_game, game_upload

ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]

TESTS = [
    ("t1", "arrows",       ';var f=(x)=>x+1;f(1);'),
    ("t2", "Array(n)",     ';var A=Array(4);'),
    ("t3", "fill",         ';var A=[1,2];A.fill(0);'),
    ("t4", "indexOf",      ';var A=[1,2];A.indexOf(1);'),
    ("t5", "unshift",      ';var A=[1,2];A.unshift(0);'),
    ("t6", "pop",          ';var A=[1,2];A.pop();'),
    ("t7", "forEach",      ';var A=[1,2];A.forEach(function(x){});'),
    ("t8", "length=",      ';var A=[1,2];A.length=1;'),
    ("t9", "push",         ';var A=[1,2];A.push(3);'),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ascii_run(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


async def main() -> None:
    notes: list[bytes] = []
    async with BleakClient(ADDRESS, timeout=25) as client:
        await client.start_notify(CALLBACK_CHAR, lambda _s, d: notes.append(bytes(d)))
        log("connected")
        results = {}
        for name, label, src in TESTS:
            notes.clear()
            await client.write_gatt_char(GAME_CHAR, game_upload(name, src), response=True)
            await asyncio.sleep(1.2)
            await client.write_gatt_char(COMMAND_CHAR, cmd_start_game(name, 8.0), response=True)
            await asyncio.sleep(2.5)
            msgs = [ascii_run(n) for n in notes]
            verdict = "STRIPPED" if any("dead strip" in m for m in msgs) else ("error?" if any("rror" in m for m in msgs) else "ok")
            results[label] = (verdict, msgs)
            log(f"{label:10} -> {verdict}   {msgs}")
        log("summary:")
        for label, (verdict, _m) in results.items():
            log(f"  {label:10} {verdict}")


if __name__ == "__main__":
    asyncio.run(main())
