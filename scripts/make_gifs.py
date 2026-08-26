#!/usr/bin/env python3
"""Generate a few 12x12 demo GIFs for the Arcade Coder gif player."""
import math
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "gifs"
OUT.mkdir(exist_ok=True)
N = 12


def save(name, frames, ms):
    imgs = []
    for fr in frames:
        im = Image.new("RGB", (N, N))
        im.putdata(fr)
        imgs.append(im)
    imgs[0].save(OUT / name, save_all=True, append_images=imgs[1:],
                 duration=ms, loop=0, disposal=2)
    print("wrote", name, len(frames), "frames")


def hsv(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


# --- beating heart ---------------------------------------------------------
HEART = ["............", "..XX..XX....", ".XXXXXXXX...", ".XXXXXXXX...",
         ".XXXXXXXX...", "..XXXXXX....", "...XXXX.....", "....XX......",
         "............", "............", "............", "............"]
frames = []
for k in range(14):
    beat = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(k / 14 * 2 * math.pi))
    col = (int(255 * beat), int(40 * beat), int(70 * beat))
    frames.append([col if HEART[y][x] == "X" else (4, 0, 6)
                   for y in range(N) for x in range(N)])
save("heart.gif", frames, 70)

# --- bouncing rainbow ball -------------------------------------------------
frames = []
for k in range(24):
    t = k / 24
    bx = 1 + int((N - 3) * abs((t * 2) % 2 - 1))
    by = N - 2 - int((N - 3) * abs(math.sin(t * math.pi)))
    col = hsv(t, 0.9, 1.0)
    fr = [(2, 2, 8)] * (N * N)
    for dy in range(2):
        for dx in range(2):
            x, y = bx + dx, by + dy
            if 0 <= x < N and 0 <= y < N:
                fr[y * N + x] = col
    frames.append(fr)
save("bounce.gif", frames, 60)

# --- rainbow pinwheel ------------------------------------------------------
frames = []
for k in range(18):
    ang = k / 18 * 2 * math.pi
    fr = [(2, 2, 6)] * (N * N)
    for a in range(4):
        th = ang + a * math.pi / 2
        for r in range(6):
            x = int(5.5 + math.cos(th) * r)
            y = int(5.5 + math.sin(th) * r)
            if 0 <= x < N and 0 <= y < N:
                fr[y * N + x] = hsv((a / 4 + k / 18) % 1, 0.9, 1.0)
    frames.append(fr)
save("pinwheel.gif", frames, 70)

print("done ->", OUT)
