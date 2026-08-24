#!/usr/bin/env python3
"""Drive a Divoom Pixoo (16x16) over Bluetooth LE from the Mac.

Uses the Divoom "ISSC" transparent-UART BLE profile and the framed protocol
(01 <len LE> <payload> <crc LE> 02). Sends 16x16 static images as a palette-
indexed frame (command 0x44 00 0A 0A 04).

Protocol reference: community reverse engineering (fhem-Divoom,
node-divoom-timebox-evo). Details verified/tuned against the real device.
"""

from __future__ import annotations

import asyncio

WRITE_CHAR = "49535343-8841-43f4-a8d4-ecbe34729bb3"
SIZE = 16
N = SIZE * SIZE


def divoom_frame(payload: bytes) -> bytes:
    length = len(payload) + 2
    body = bytes([length & 0xFF, (length >> 8) & 0xFF]) + payload
    crc = sum(body) & 0xFFFF
    return bytes([0x01]) + body + bytes([crc & 0xFF, (crc >> 8) & 0xFF, 0x02])


import math


def _pack_pixels(indices: list[int], nbits: int) -> bytes:
    """Divoom bit packing: per index take 8-bit binary, reverse, keep first
    nbits; then group the bitstream into bytes, reverse each byte."""
    bitstream = ""
    for idx in indices:
        bitstream += format(idx, "08b")[::-1][:nbits]
    while len(bitstream) % 8:
        bitstream += "0"
    out = bytearray()
    for i in range(0, len(bitstream), 8):
        out.append(int(bitstream[i:i + 8][::-1], 2))
    return bytes(out)


def encode_image(pixels: list[tuple[int, int, int]], max_colors: int = 256) -> bytes:
    """pixels: 256 (r,g,b) row-major top-left first. Returns the framed bytes.
    Palette is capped at max_colors (extra colours snap to the nearest) so the
    BLE message stays small enough to arrive intact."""
    assert len(pixels) == N
    cap = max(2, min(256, max_colors))
    palette: list[tuple[int, int, int]] = []
    index: dict[tuple[int, int, int], int] = {}
    for p in pixels:
        if p not in index:
            if len(palette) >= cap:
                index[p] = min(range(len(palette)),
                               key=lambda k: sum((a - b) ** 2 for a, b in zip(p, palette[k])))
            else:
                index[p] = len(palette)
                palette.append(p)
    ncolors = len(palette)
    nbits = max(1, math.ceil(math.log2(ncolors))) if ncolors > 1 else 1
    indices = [index[p] if p in index
               else min(range(ncolors), key=lambda k: sum((a - b) ** 2 for a, b in zip(p, palette[k])))
               for p in pixels]
    packed = _pack_pixels(indices, nbits)
    pal_bytes = b"".join(bytes(c) for c in palette)
    nn = ncolors & 0xFF  # 256 -> 0x00
    # IMAGE_DATA = AA + LLLL + 000000 + NN + palette + pixels; LLLL counts all of it
    image_len = 1 + 2 + 3 + 1 + len(pal_bytes) + len(packed)
    image_data = (bytes([0xAA, image_len & 0xFF, (image_len >> 8) & 0xFF,
                         0x00, 0x00, 0x00, nn]) + pal_bytes + packed)
    payload = bytes([0x44, 0x00, 0x0A, 0x0A, 0x04]) + image_data
    return divoom_frame(payload)


def cmd_brightness(level: int) -> bytes:
    return divoom_frame(bytes([0x74, max(0, min(100, level))]))


class Pixoo:
    def __init__(self) -> None:
        self.client = None

    async def connect(self):
        from bleak import BleakScanner, BleakClient

        dev = await BleakScanner.find_device_by_filter(
            lambda d, adv: (d.name or "").lower().startswith("pixoo"), timeout=15.0)
        if not dev:
            raise RuntimeError("Pixoo not found")
        self.client = BleakClient(dev, timeout=25)
        await self.client.connect()
        await asyncio.sleep(1.0)

    async def _write(self, data: bytes):
        # chunk into 20-byte BLE writes
        for i in range(0, len(data), 20):
            await self.client.write_gatt_char(WRITE_CHAR, data[i:i + 20], response=False)
            await asyncio.sleep(0.01)

    async def image(self, pixels, max_colors: int = 256):
        await self._write(encode_image(pixels, max_colors))

    async def fill(self, rgb):
        await self.image([tuple(rgb)] * N)

    async def brightness(self, level):
        await self._write(cmd_brightness(level))

    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
