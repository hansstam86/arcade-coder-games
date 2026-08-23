#!/usr/bin/env python3
"""Upload and run native XS-JavaScript games on the Arcade Coder's stock VM.

Runs three stages so the user can report what worked:
  1. probe "chk": full-screen 12x12 costume (framebuffer rendering technique)
  2. probe "tlt": a light that moves when the board is tilted
  3. the actual game "snek": accelerometer-steered snake

Constraints from community reverse engineering: whole Game protobuf must fit
one <=512B write; no column-zero `var`; no IIFEs; state lives on Engine.*.
"""
import asyncio
import json
import struct
import time
from pathlib import Path

from bleak import BleakClient

from minesweeper import COMMAND_CHAR, CALLBACK_CHAR, _field_len, _field_varint

GAME_CHAR = "27f450db-9197-4e02-85fd-9cba87639a28"
ADDRESS = json.loads((Path(__file__).parent / "device_config.json").read_text())["address"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def game_upload(name: str, source: str) -> bytes:
    return _field_len(1, name) + _field_len(2, name) + _field_len(3, source)


def cmd_start_game(name: str, freq: float) -> bytes:
    name_payload = _field_len(1, name)
    freq_payload = b"\x0d" + struct.pack("<f", freq)  # field1 fixed32
    return _field_varint(1, 0) + _field_len(2, name_payload) + _field_len(3, freq_payload)


# NOTE on style: the stock loader extracts column-zero `var` lines into a
# broken separate context, so each source is one line starting with ';var' —
# the leading ';' defeats the extractor while keeping ordinary function-scope
# locals that all callbacks close over. No IIFEs (they crash the VM).

# --- stage 1: full-screen costume probe (green/blue checkerboard) -----------
CHK = (
    ';var E=Engine,G=Array(432),S,i;'
    'E.spriteClasses.push([S=new E.Sprite(E.makeGameCostume(1,1,[0,0,0]),1,1,0,0)]);'
    'E.WhenGameUpdates(function(){G.fill(0);for(i=0;i<144;i++)G[i*3+((i+(i/12|0))%2)]=99;'
    'S.costume=E.makeGameCostume(12,12,G)});'
)

# --- stage 2: tilt probe (white light glides in tilt direction) -------------
# deliberately uses arrow functions so this probe also validates them for snek
TLT = (
    ';var E=Engine,S;'
    'E.spriteClasses.push([S=new E.Sprite(E.makeGameCostume(1,1,[99,99,99]),6,6,0,0)]);'
    '["LEFT","RIGHT","FORWARD","BACK"].forEach((d,i)=>E.WhenTilted(d,()=>{'
    'S.speedX=[-1,1,0,0][i];S.speedY=[0,0,-1,1][i]}));'
    'E.WhenGameUpdates(()=>{if(S.x<1)S.x=12;if(S.x>12)S.x=1;if(S.y<1)S.y=12;if(S.y>12)S.y=1});'
)

# --- stage 3: snake ---------------------------------------------------------
# Ultra-conservative builtin surface after the firmware's "dead strip" error:
# only `push` (community-proven), plain loops/assignments, and the Engine API.
# body B = flat indices 0..143 (head first); D = flat-index delta per tilt
# (torus wrap: exiting an edge re-enters opposite side, horizontal wrap shifts
# one row — acceptable v1 quirk). Hitting your own body resets the snake.
# F=(F*7+31)%144 is an affine bijection mod 144 = cheap food "randomness".
# Collision check reads the previous frame in G before it is cleared.
SNEK = (
    ';var E=Engine,D=1,B=[66],L=3,F=6,G=[],S,j,n;'
    'E.spriteClasses.push([S=new E.Sprite(E.makeGameCostume(1,1,[0,0,0]),1,1,0,0)]);'
    'E.T=function(d,u){E.WhenTilted(d,function(){D=u})};'
    'E.T("LEFT",-1);E.T("RIGHT",1);E.T("FORWARD",-12);E.T("BACK",12);'
    'E.WhenGameUpdates(function(){n=(B[0]+D+144)%144;'
    'if(G[n*3+1])B=[];'
    'for(j=432;j--;)G[j]=0;'
    'for(j=B.length;j;j--)B[j]=B[j-1];'
    'B[0]=n;'
    'if(n==F)L++,F=(F*7+31)%144;'
    'if(B[L])B.length=L;'
    'for(j=B.length;j--;)G[B[j]*3+1]=99;'
    'G[F*3+2]=99;'
    'S.costume=E.makeGameCostume(12,12,G)});'
)

STAGES = [("chk", CHK, 4.0, 12), ("tlt", TLT, 6.0, 25), ("sk", SNEK, 5.0, 5)]


async def main() -> None:
    for name, src, _f, _w in STAGES:
        size = len(game_upload(name, src))
        log(f"stage {name}: source {len(src)} chars, upload {size} bytes")
        assert size <= 512, f"{name} exceeds single-write ceiling"

    async with BleakClient(ADDRESS, timeout=25) as client:
        await client.start_notify(CALLBACK_CHAR, lambda _s, d: log(f"NOTIFY {len(d)}B: {bytes(d).hex()}"))
        log("connected")
        for name, src, freq, wait in STAGES:
            await client.write_gatt_char(GAME_CHAR, game_upload(name, src), response=True)
            log(f"uploaded {name}")
            await asyncio.sleep(2.0)
            await client.write_gatt_char(COMMAND_CHAR, cmd_start_game(name, freq), response=True)
            log(f"== started {name} at {freq:g} Hz — WATCH THE BOARD ({wait}s)")
            await asyncio.sleep(wait)
        log("all stages done — snek is left running")
        await asyncio.sleep(600)


if __name__ == "__main__":
    asyncio.run(main())
