#!/usr/bin/env python3
"""Drive a Divoom Pixoo (16x16) from macOS over its Bluetooth serial port.

On macOS the Pixoo 16's command protocol runs over Bluetooth Classic SPP, not
BLE: pair the Pixoo in System Settings and macOS exposes it as /dev/cu.Pixoo
(or /dev/tty.Pixoo). We write the framed Divoom protocol
(01 <len LE> <cmd+args> <crc LE> 02) to that serial port.

Image encoding verified byte-for-byte against jvandenbos/pixoo-python and
virtualabs/pixoo-client. Note: image commands (0x44) only take effect on a
fresh connection — reopen the port before sending an image.
"""

from __future__ import annotations

import glob
import math
import time

SIZE = 16
N = SIZE * SIZE


def find_port() -> str | None:
    for pat in ("/dev/cu.Pixoo*", "/dev/tty.Pixoo*", "/dev/cu.*Pixoo*"):
        hits = glob.glob(pat)
        if hits:
            return sorted(hits)[0]
    return None


def frame(cmd: int, args: list[int]) -> bytes:
    size = len(args) + 3
    buf = [0x01, size & 0xFF, (size >> 8) & 0xFF, cmd] + list(args)
    crc = sum(buf[1:]) & 0xFFFF
    buf += [crc & 0xFF, (crc >> 8) & 0xFF, 0x02]
    return bytes(buf)


def encode_image(pixels: list[tuple[int, int, int]], max_colors: int = 256) -> bytes:
    """pixels: 256 (r,g,b) row-major. Returns the framed 0x44 image command."""
    assert len(pixels) == N
    cap = max(2, min(256, max_colors))
    palette: list[tuple[int, int, int]] = []
    idx_of: dict[tuple[int, int, int], int] = {}
    indices: list[int] = []
    for p in pixels:
        if p in idx_of:
            indices.append(idx_of[p])
        elif len(palette) < cap:
            idx_of[p] = len(palette)
            palette.append(p)
            indices.append(idx_of[p])
        else:
            indices.append(min(range(len(palette)),
                               key=lambda k: sum((a - b) ** 2 for a, b in zip(p, palette[k]))))
    num_colors = len(palette)
    bitwidth = math.ceil(math.log10(num_colors) / math.log10(2)) if num_colors > 1 else 1
    enc, acc = [], ""
    for i in indices:
        acc = bin(i)[2:].rjust(bitwidth, "0") + acc
        if len(acc) >= 8:
            enc.append(acc[-8:])
            acc = acc[:-8]
    if acc:
        enc.append(acc.rjust(8, "0"))
    pixel_data = [int(c, 2) for c in enc]
    palette_data = [c for rgb in palette for c in rgb]
    frame_size = 7 + len(pixel_data) + len(palette_data)
    header = [0xAA, frame_size & 0xFF, (frame_size >> 8) & 0xFF, 0, 0, 0, num_colors & 0xFF]
    prefix = [0x00, 0x0A, 0x0A, 0x04]
    return frame(0x44, prefix + header + palette_data + pixel_data)


def cmd_brightness(level: int) -> bytes:
    return frame(0x74, [max(0, min(100, level))])


def cmd_color(r: int, g: int, b: int) -> bytes:
    return frame(0x6F, [r, g, b])


class Pixoo:
    """Serial (Bluetooth SPP) connection to a paired Pixoo 16."""

    def __init__(self, port: str | None = None) -> None:
        self.port = port
        self.ser = None

    def open(self) -> bool:
        import serial

        p = self.port or find_port()
        if not p:
            return False
        try:
            self.ser = serial.Serial(p, baudrate=115200, timeout=2)
            self.port = p
            time.sleep(0.3)
            return True
        except Exception:
            self.ser = None
            return False

    def _send(self, data: bytes) -> None:
        if self.ser is None:
            raise ConnectionError("Pixoo serial port not open")
        self.ser.write(data)
        self.ser.flush()

    def brightness(self, level: int) -> None:
        self._send(cmd_brightness(level))

    def color(self, r: int, g: int, b: int) -> None:
        self._send(cmd_color(r, g, b))

    def image(self, pixels, max_colors: int = 256) -> None:
        self._send(encode_image(pixels, max_colors))

    def close(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
