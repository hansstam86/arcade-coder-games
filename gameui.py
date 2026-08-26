"""Shared bits for the board-game apps."""

from __future__ import annotations

from marquee import render_columns

CPU_COL = (0, 150, 255)
P2_COL = (0, 220, 90)


def draw_mode_splash(screen, vs_cpu: bool) -> None:
    """Flash 'CPU' or '2P' centred over rows 3–7 on a dark band."""
    text = "CPU" if vs_cpu else "2P"
    color = CPU_COL if vs_cpu else P2_COL
    for r in range(3, 8):                       # dark band behind the text
        for x in range(12):
            screen.set(x, r, (2, 2, 6))
    cols = render_columns(text)
    x0 = (12 - len(cols)) // 2
    for i, colbits in enumerate(cols):
        x = x0 + i
        if 0 <= x < 12:
            for r in range(5):
                if colbits[r]:
                    screen.set(x, 3 + r, color)
