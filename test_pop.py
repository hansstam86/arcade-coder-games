"""Offline tests: pop! groups, scoring, gravity animation, endgame, rendering."""
import math
import random

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from pop import COLORS, Pop


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def run_frames(game, seconds: float, dt: float = 0.01) -> None:
    for _ in range(int(seconds / dt)):
        game.update(dt)


loop = GameLoop(Pop)
game = loop.game
game.next_check = 1e18

# --- flood fill: orthogonal only, colour-true --------------------------------------
game.new_game()
game.grid = [[0] * W for _ in range(H)]
for x in range(3):                       # a 3x2 red block at (0,0)-(2,1)
    for y in range(2):
        game.grid[y][x] = 1
game.grid[2][3] = 1                      # truly diagonal from (2,1): NOT connected
game.grid[0][3] = 1                      # row continuation: connected via (2,0)
group = game._flood(0, 0)
assert len(group) == 7, f"the 3x2 block plus the row continuation ({len(group)})"
assert (3, 2) not in group, "diagonals do not connect"
assert game._flood(9, 9) == [], "empty cells have no group"
print("flood OK (orthogonal, colour-true, diagonal-excluded)")

# --- popping: classic (n-2)^2 scoring, group removal --------------------------------
game.new_game()
game.grid = [[0] * W for _ in range(H)]
for x in range(5):                       # five reds in a row
    game.grid[0][x] = 1
game.on_press(0, 0)
assert game.state == "popping", "a valid pop enters the burst"
assert game.score == 9, f"(5-2)^2 = 9 ({game.score})"
assert all(game.grid[0][x] == 0 for x in range(5)), "the group is removed from the grid"
print("pop scoring OK (five tiles -> +9)")

# --- gravity: one cell per micro-step, trails, converges ----------------------------
run_frames(game, 0.5)                     # burst finishes, falling begins
assert game.state in ("falling", "play", "cleared"), \
    f"after the flash the board falls — on an empty board it clears outright ({game.state})"
# build a single floating tile to watch it step down
game.state = "play"
game.grid = [[0] * W for _ in range(H)]
game.grid[0][0] = 3                       # one tile at the top of column 0
moved = game._gravity_step()
assert moved and game.grid[1][0] == 3 and game.grid[0][0] == 0, "one step = one cell"
assert game.ghosts.get((0, 0)) == 3, "the vacated cell leaves a trail ghost"
for _ in range(20):
    if not game._gravity_step():
        break
assert game.grid[H - 1][0] == 3, "gravity settles at the floor"
assert not game.has_moves()
game._settle()
assert game.state == "over" and game.score == 9 + 1000, \
    "a lone tile left behind ends the run (after the earlier perfect-clear bonus)"
game.state = "play"
print("gravity OK (micro-steps, ghost trails, floor settle)")

# --- nope: lone tiles blink, nothing pops ---------------------------------------------
game.new_game()
game.grid = [[0] * W for _ in range(H)]
game.grid[5][5] = 2
game.grid[7][7] = 2                        # isolated singles
game.on_press(5, 5)
assert game.state == "play" and game.score == 0, "singles do not pop"
assert game.nope_cell is not None, "the press blinks 'nope'"
print("nope OK (lone tiles refuse politely)")

# --- endgames: stuck board dims, perfect clear celebrates ----------------------------
game.new_game()
game.grid = [[((x + y) % 2) + 1 for x in range(W)] for y in range(H)]
assert not game.has_moves(), "checkerboard: no two neighbours share a colour"
game._settle()
assert game.state == "over", "a dead board ends the run"
game.on_press(3, 3)                        # any press restarts
assert game.state == "play" and game.score == 0
print("game over OK (checkerboard dies, any press restarts)")

game.new_game()
game.grid = [[0] * W for _ in range(H)]
for y in range(H):                         # one full column of reds = one group of 12
    game.grid[y][0] = 1
game.score = 5
game.on_press(0, 0)
assert game.score == 5 + (12 - 2) ** 2, f"12 tiles score (12-2)^2 = 100 ({game.score})"
run_frames(game, 0.5)
run_frames(game, 2.0)
assert game.state == "cleared", f"emptying the board is a PERFECT CLEAR ({game.state})"
assert game.score == 5 + 100 + 1000, f"plus the clear bonus ({game.score})"
print("perfect clear OK (+1000, rainbow state)")

# --- rendering -------------------------------------------------------------------------
game.new_game()
game.rnd = random.Random(4)
game.grid = [[1] * W for _ in range(H)]
game.state = "play"
frame = loop.tick()
assert px(frame, 5, 5) == COLORS[0], "tiles render in their candy colour"
game.grid[5][5] = 0
game.ghosts = {(5, 5): 1}
frame = loop.tick()
assert px(frame, 5, 5) == tuple(int(c * 0.22) for c in COLORS[0]), "ghost trails render dim"
game.ghosts = {}
game.state = "popping"                      # the burst flashes white early
game.popped = [(5, 5, 1)]
game.pop_until = game.t + 0.34
frame = loop.tick()
assert sum(px(frame, 5, 5)) > 500, "the burst starts near-white"
game.state = "cleared"
frame = loop.tick()
assert sum(px(frame, 5, 5)) > 300, "perfect clear renders the rainbow"
print("rendering OK (tiles, ghosts, burst flash, rainbow clear)")
print("all pop! tests OK")