"""Offline tests: wireworld rules, presets, brushes, rendering."""
import time

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from wireworld import (
    COPPER, EMPTY, HEAD, PRESETS, TAIL, Wireworld,
)

BRUSH_COLOR = {COPPER: (170, 100, 18), HEAD: (0, 230, 255), EMPTY: (60, 60, 60)}
COLORS = {COPPER: (170, 100, 18), HEAD: (0, 230, 255), TAIL: (235, 50, 10)}


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def heads(g):
    return sum(1 for y in range(H) for x in range(W) if g[y][x] == HEAD)


def key(g):
    return tuple(tuple(r) for r in g)


loop = GameLoop(Wireworld)
game = loop.game
game.running = False                       # drive _step by hand

# --- rules: state transitions ---------------------------------------------------
game.clear()
game.grid[5][5] = HEAD
game._step()
assert game.grid[5][5] == TAIL, "head -> tail"
game._step()
assert game.grid[5][5] == COPPER, "tail -> copper"
game._step()
assert game.grid[5][5] == COPPER, "lonely copper stays copper (0 head nbs)"
game._step()
assert game.grid[0][0] == EMPTY, "empty stays empty"

# --- rules: copper fires with 1 or 2 head neighbours, not with 3 ---------------
game.clear()
game.grid[1][2] = HEAD                      # head at cell (2,1)
assert game._neighbour_heads(2, 2) == 1
game.grid[1][4] = HEAD                      # head at cell (4,1)
assert game._neighbour_heads(3, 2) == 2
game.grid[1][3] = HEAD                      # head at cell (3,1)
assert game._neighbour_heads(3, 2) == 3, "diagonal + orthogonal heads all count"

# --- straight wire: pulse advances 1 cell/gen, never reflects -------------------
game.clear()
game.cfg["wrap"] = False
for x in range(W):
    game.grid[5][x] = COPPER
game.grid[5][3] = HEAD
game.grid[5][2] = TAIL
copper_total = sum(sum(1 for v in row if v in (COPPER, TAIL, HEAD)) for row in game.grid)
for gen, expect_x in ((1, 4), (2, 5), (3, 6)):
    game._step()
    assert game.grid[5][expect_x] == HEAD, f"pulse should be at x={expect_x}"
    assert game.grid[5][expect_x - 1] == TAIL, "tail trails the head"
    assert heads(game.grid) == 1, "exactly one head — no reflections, no splits"
assert sum(sum(1 for v in row if v) for row in game.grid) == copper_total, \
    "the wire footprint never changes"
for _ in range(20):                        # runs off the end of the wire
    game._step()
assert heads(game.grid) == 0, "pulse should die at the wire end without wrap"
print("rules OK (transitions, firing counts, straight propagation)")

# --- preset: clock ring — pulses forever, periodic, footprint invariant ---------
game.cfg["wrap"] = True
game.load_pattern(0)
assert sum(sum(1 for v in row if v) for row in game.grid) == 28, "clock ring has 28 wire cells"
ring_footprint = sum(1 for y in range(H) for x in range(W) if game.grid[y][x] != EMPTY)
seen = {key(game.grid): 0}
period = None
for t in range(1, 121):
    game._step()
    assert 1 <= heads(game.grid) <= 2, f"ring should carry one pulse (heads={heads(game.grid)} at t={t})"
    assert sum(1 for y in range(H) for x in range(W) if game.grid[y][x] != EMPTY) == ring_footprint
    k = key(game.grid)
    if k in seen and period is None:
        period = t - seen[k]
        break
    seen[k] = t
assert period and 4 < period <= 60, f"ring should be periodic (period={period})"
print(f"clock ring OK (period {period} generations, footprint invariant)")

# --- preset: data bus — four clean pulses on four straight loops -----------------
game.load_pattern(2)
assert sum(1 for y in range(H) for x in range(W) if game.grid[y][x] != EMPTY) == 48
for t in range(1, 61):
    game._step()
    assert heads(game.grid) == 4, f"each bus loop carries exactly one pulse (t={t}, heads={heads(game.grid)})"
print("data bus OK (4 pulses, no corners to disturb them)")

# --- preset: zigzag — the pulse survives the corners and reaches the end ---------
game.load_pattern(3)
assert sum(1 for y in range(H) for x in range(W) if game.grid[y][x] != EMPTY) == 36
end_hits = 0
for t in range(1, 121):
    game._step()
    assert heads(game.grid) <= 2, "corners may widen the pulse but never split it"
    if game.grid[9][10] == HEAD:
        end_hits += 1
assert end_hits > 0, "the zigzag pulse should reach the far end"
print("zigzag OK (corners pass the pulse cleanly)")

# --- pads ------------------------------------------------------------------------
game.running = True
game.load_pattern(0)
loop.press(0, 0)                            # pause pad
assert game.running is False
loop.press(11, 0)                            # speed pad
assert game.cfg["speed_index"] == 3
loop.press(6, 0)                             # preset pad: 0 -> 1
assert game.pattern_idx == 1 and sum(sum(1 for v in r if v) for r in game.grid) == 48
loop.press(0, 11)                            # clear pad
assert all(v == EMPTY for row in game.grid for v in row), "clear pad empties the board"

# --- brushes and live painting ----------------------------------------------------
assert game.brush == COPPER                 # default brush
loop.press(5, 5)                             # paint copper
assert game.grid[5][5] == COPPER
loop.press(11, 11)                           # brush pad -> electron
assert game.brush == HEAD
loop.press(5, 6)                             # paint an electron
assert game.grid[6][5] == HEAD               # on_press(x, y) stores grid[y][x]
loop.press(11, 11)                           # brush pad -> erase
assert game.brush == EMPTY
loop.press(5, 5)
assert game.grid[5][5] == EMPTY
loop.press(11, 11)                           # brush pad -> back to copper
assert game.brush == COPPER
print("pads OK (pause, speed, preset, clear, brush cycle, painting)")

# --- rendering -------------------------------------------------------------------
frame = loop.tick()
assert px(frame, 5, 6) == COLORS[HEAD], "electron head should be bright cyan"
assert px(frame, 11, 11) == BRUSH_COLOR[COPPER], "brush HUD shows the copper brush"
game.running = True
loop.press(11, 11)                           # brush -> electron
game.running = False
frame = loop.tick()
assert px(frame, 0, 0) == (230, 40, 40), "pause HUD red while paused"
assert px(frame, 11, 11) == BRUSH_COLOR[HEAD], "brush HUD now shows cyan"

game.load_pattern(0)
game.running = True
frame = loop.tick()
copper_px = sum(1 for y in range(H) for x in range(W) if px(frame, x, y) == COLORS[COPPER])
head_px = sum(1 for y in range(H) for x in range(W) if px(frame, x, y) == COLORS[HEAD])
assert copper_px >= 25, f"ring should render amber copper (got {copper_px})"
assert head_px >= 1, "ring should render at least one cyan head"
print("clock ring frame (running):\n" + ascii_frame(frame))
print("all wireworld tests OK")