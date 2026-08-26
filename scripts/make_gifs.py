#!/usr/bin/env python3
"""Generate a few 12x12 demo GIFs for the Arcade Coder gif player."""
import math
import random
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

# --- Pac-Man chomping across, eating dots ----------------------------------
frames = []
NF = 16
dots = [(8, 5), (8, 6), (10, 5), (10, 6)]
for k in range(NF):
    px = k / NF * 9
    mouth = abs(math.sin(k / NF * math.pi * 2)) * 0.9
    fr = [(0, 0, 12)] * (N * N)
    for dx, dy in dots:
        if dx > px + 2:
            fr[dy * N + dx] = (255, 255, 255)
    cx, cy, r = px + 2.5, 5.5, 2.7
    for y in range(N):
        for x in range(N):
            if math.hypot(x - cx, y - cy) <= r and abs(math.atan2(y - cy, x - cx)) >= mouth:
                fr[y * N + x] = (255, 220, 0)
    frames.append(fr)
save("pacman.gif", frames, 90)

# --- Space Invader ---------------------------------------------------------
INV1 = ["..X.....X...", "...X...X....", "..XXXXXXX...", ".XX.XXX.XX..",
        "XXXXXXXXXXX.", "X.XXXXXXX.X.", "X.X.....X.X.", "...XX.XX...."]
INV2 = ["..X.....X...", "X..X...X..X.", "X.XXXXXXX.X.", "XXX.XXX.XXX.",
        "XXXXXXXXXXX.", ".XXXXXXXXX..", "..X.....X...", ".X.......X.."]
frames = []
for k, (bmp, oy) in enumerate([(INV1, 2), (INV2, 2), (INV1, 3), (INV2, 3)]):
    col = (0, 220, 220)
    fr = [(2, 2, 8)] * (N * N)
    for y, rows in enumerate(bmp):
        for x, ch in enumerate(rows):
            if ch == "X" and 0 <= oy + y < N:
                fr[(oy + y) * N + x] = col
    frames.append(fr)
save("invader.gif", frames, 220)

# --- fire ------------------------------------------------------------------
random.seed(3)
heat = [[0.0] * N for _ in range(N + 1)]
frames = []
for k in range(28):
    for x in range(N):
        heat[N][x] = random.uniform(0.55, 1.0)
    for y in range(N):
        for x in range(N):
            below = heat[y + 1]
            v = (below[x] * 2 + below[(x - 1) % N] + below[(x + 1) % N]) / 4
            heat[y][x] = max(0.0, v - random.uniform(0.02, 0.11))
    fr = []
    for y in range(N):
        for x in range(N):
            v = heat[y][x]
            fr.append((int(255 * min(1, v * 1.6)), int(255 * max(0, v * 1.4 - 0.45)),
                       int(255 * max(0, v * 2.2 - 1.6))))
    frames.append(fr)
save("fire.gif", frames, 70)

# --- explosion -------------------------------------------------------------
frames = []
NF = 15
for k in range(NF):
    t = k / NF
    r = t * 7.5
    fr = [(0, 0, 6)] * (N * N)
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - 5.5, y - 5.5)
            if k < 2 and d < 2.2:
                fr[y * N + x] = (255, 255, 255)
            elif abs(d - r) < 1.5:
                fr[y * N + x] = hsv(max(0.0, 0.14 - 0.14 * t), 0.85, min(1.0, 1.1 - t))
    frames.append(fr)
save("explosion.gif", frames, 55)

# --- Matrix rain -----------------------------------------------------------
random.seed(5)
cols = [{"y": random.uniform(-N, 0), "sp": random.uniform(0.5, 1.3)} for _ in range(N)]
trail = [[0.0] * N for _ in range(N)]
frames = []
for k in range(26):
    for row in trail:
        for x in range(N):
            row[x] *= 0.68
    for x in range(N):
        c = cols[x]
        c["y"] += c["sp"]
        if c["y"] > N + 3:
            c["y"] = random.uniform(-6, 0); c["sp"] = random.uniform(0.5, 1.3)
        yy = int(c["y"])
        if 0 <= yy < N:
            trail[yy][x] = 1.0
    fr = []
    for y in range(N):
        for x in range(N):
            v = trail[y][x]
            fr.append((int(40 * v), int(235 * v), int(60 * v * v)))
    frames.append(fr)
save("matrix.gif", frames, 80)

# --- rainbow vortex --------------------------------------------------------
frames = []
NF = 20
for k in range(NF):
    t = k / NF * 2 * math.pi
    fr = []
    for y in range(N):
        for x in range(N):
            dx, dy = x - 5.5, y - 5.5
            d = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            hue = (a / (2 * math.pi) + d * 0.11 - k / NF) % 1
            v = 0.5 + 0.5 * math.sin(a * 3 + d * 1.2 - t * 2)
            fr.append(hsv(hue, 0.85, 0.25 + 0.5 * v))
    frames.append(fr)
save("vortex.gif", frames, 70)

print("done ->", OUT)
