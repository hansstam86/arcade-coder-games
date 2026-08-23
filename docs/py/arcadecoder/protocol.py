"""Stock-firmware BLE protocol for the Arcade Coder.

Reverse engineering credit: the awesome-arcade-coder community and
LightyCoderDoodad (github.com/diggedypomme/LightyCoderDoodad).
"""

from __future__ import annotations

import struct
import zlib

SERVICE_UUID = "778d5426-fa29-4363-91fd-a9f5cfcfce85"
COMMAND_CHAR = "e18d056b-7dae-49c1-b5f2-17684801e446"
CALLBACK_CHAR = "21acb4a0-24d0-42f4-8e61-c827daf68d12"
GAME_CHAR = "27f450db-9197-4e02-85fd-9cba87639a28"

W = H = 12
N = W * H
BRUSH = bytes((5, 20, 220))  # what a physical press paints onto the canvas


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
    # the stock inflater corrupts LZ77 backreferences; Huffman-only is safe
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
