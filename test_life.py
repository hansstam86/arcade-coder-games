"""Offline tests: game of life rules, pads, patterns, autoseed, rendering."""
import time

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from life import PATTERNS, Life


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def grid_key(g):
    return tuple(tuple(r) for r in g)


loop = GameLoop(Life)
game = loop.game

# --- rules: blinker oscillates with period 2 ----------------------------------
game.clear()
game.load_pattern(1)                              # blinker
game.running = False
h0 = grid_key(game.grid)
game._step()
h1 = grid_key(game.grid)
game._step()
h2 = grid_key(game.grid)
assert h1 != h0, "blinker must move"
assert h2 == h0, "blinker must return after 2 steps (period 2)"

# --- rules: block is a still life ----------------------------------------------
game.clear()
for cx, cy in ((5, 5), (6, 5), (5, 6), (6, 6)):
    game.grid[cy][cx] = 1
game._step()
assert grid_key(game.grid) == tuple(tuple(1 if x in (5, 6) and y in (5, 6) else 0 for x in range(W)) for y in range(H)), "block must be stable"

# --- rules: glider travels diagonally (wrapping on the torus) -----------------
game.clear()
game.load_pattern(0)  # glider, centred
game._step()
game._step()
game._step()
game._step()
xs = [x for y in range(H) for x in range(W) if game.grid[y][x]]
assert len(xs) == 5, f"glider keeps 5 cells (got {len(xs)})"
assert max(xs) > 3, "glider should have moved right over 4 steps"
game._step()
game._step()
game._step()
game._step()
moved = sum(1 for y in range(H) for x in range(W) if game.grid[y][x])
assert moved == 5, "glider still intact after 8 steps"
print("rules OK (blinker period 2, block stable, glider moves)")

# --- age colours: cells that survive gain age, newborns are green --------------
game.clear()
for cx, cy in ((5, 5), (6, 5), (5, 6), (6, 6)):
    game.grid[cy][cx] = 1
for _ in range(5):
    game._step()
assert game.age[5][5] == 5, f"survivor should age (got {game.age[5][5]})"
frame = loop.tick()
r, g, b = px(frame, 5, 5)
assert g < 100 and b > 200, f"aged cell should be cool-coloured, got {px(frame, 5, 5)}"

# --- pads ----------------------------------------------------------------------
game.running = True
game.load_pattern(1)                       # fresh blinker
loop.press(0, 0)                           # top-left: pause
assert game.running is False
loop.press(0, 11)                          # bottom-left: clear
assert grid_key(game.grid) == tuple((0,) * W for _ in range(H)), "clear pad empties the world"
loop.press(11, 11)                         # bottom-right: soup
density = sum(sum(r) for r in game.grid) / (W * H)
assert 0.05 < density < 0.6, f"soup should be random-ish (density {density:.2f})"
loop.press(11, 0)                          # top-right: speed cycle
assert game.cfg["speed_index"] == 3, "speed pad should cycle"
loop.press(6, 0)                           # top-centre: next pattern (0 -> 1)
assert game.pattern_idx == 1 and sum(sum(r) for r in game.grid) == 3, "pattern pad loads the blinker"
print("pads OK (pause, clear, soup, speed, pattern)")

# --- live toggling a cell --------------------------------------------------------
loop.press(3, 3)
assert game.grid[3][3] == 1, "pressing a dead cell births it"
loop.press(3, 3)
assert game.grid[3][3] == 0, "pressing a live cell kills it"

# --- autoseed: extinction and stasis reseed the world ---------------------------
game.cfg["autoseed"] = True
game.clear()
game.running = True
game.update(3.0)                            # 3s of dead world
assert any(any(r) for r in game.grid), "extinct world should reseed"
game.clear()
for cx, cy in ((5, 5), (6, 5), (5, 6), (6, 6)):   # a stable block: stasis
    game.grid[cy][cx] = 1
game.update(1.0)                            # prime the change detector
game.update(7.0)                            # 7s of no change afterwards
changed = grid_key(game.grid) != tuple(
    tuple(1 if x in (5, 6) and y in (5, 6) else 0 for x in range(W)) for y in range(H)
)
assert changed, "stagnant world should be sprinkled with fresh soup"
print("autoseed OK (extinct + stasis reseeding)")

# --- rendering: paused tint, HUD pixels ------------------------------------------
game.clear()
game.load_pattern(0)
game.running = False
frame = loop.tick()
assert px(frame, 0, 0) == (230, 40, 40), "pause HUD should be red when paused"
assert px(frame, 6, 5) == (20, 255, 30), f"a newborn glider cell should be bright green, got {px(frame, 6, 5)}"
print("glider frame (paused, tinted):\n" + ascii_frame(frame))
game.running = True
print("all game of life tests OK")