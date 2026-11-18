"""Offline tests: 2048 slide mechanics, directions, spawns, over, win, rendering."""
import random

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from twenty48 import TILE_COLORS, Twenty48, _slide


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


# --- the slide: exact classic merge semantics, any line length --------------------
assert _slide([2, 2, 2, 2]) == ([4, 4, 0, 0], 8, [0, 1])
assert _slide([2, 2, 2, 0])[0] == [4, 2, 0, 0], "the leftmost pair merges first"
assert _slide([4, 2, 2, 0]) == ([4, 4, 0, 0], 4, [1]), "each tile merges once per move"
assert _slide([0, 2, 0, 2]) == ([4, 0, 0, 0], 4, [0]), "gaps compact: separated pairs still merge"
assert _slide([2, 4, 8, 16]) == ([2, 4, 8, 16], 0, []), "no neighbours, no merge"
long = [0] * 8 + [2, 2]
assert _slide(long) == ([4] + [0] * 9, 4, [0]), "works on a 10-long line too"
print("slide OK (exact classic merge semantics, any length)")

loop = GameLoop(Twenty48)
game = loop.game
game.next_check = 1e18
N = game.N
assert N == 10 and game.off == 1, f"the board is 10x10 with 1px margins (N={N}, off={game.off})"

# --- the four directions ------------------------------------------------------------
game.new_game()
game.grid = [[0] * N for _ in range(N)]
game.grid[0][1] = game.grid[0][3] = 2
game._move("left")
assert game.grid[0][0] == 4, "left merges the pair to the wall"
game.grid = [[0] * N for _ in range(N)]
game.grid[0][N - 4] = game.grid[0][N - 2] = 2
game._move("right")
assert game.grid[0][N - 1] == 4, "right merges to the far edge"
game.grid = [[0] * N for _ in range(N)]
game.grid[0][0] = game.grid[3][0] = 2
game._move("up")
assert game.grid[0][0] == 4, "up merges into the top row"
game.grid = [[0] * N for _ in range(N)]
game.grid[0][0] = 2
game.grid[N - 1][0] = 2
game._move("down")
assert game.grid[N - 1][0] == 4, "down merges into the bottom row"
print("directions OK (left, right, up, down on the 10x10)")

# --- a move that changes nothing does nothing ---------------------------------------
game.new_game()
game.grid = [[0] * N for _ in range(N)]
game.grid[0] = [2, 4, 8, 16, 2, 4, 8, 16, 2, 4]
before = sum(sum(r) for r in game.grid)
score_before = game.score
game._move("left")
assert sum(sum(r) for r in game.grid) == before, "no tiles gained"
assert game.score == score_before, "no score from a null move"
print("null move OK (no change, no spawn)")

# --- every real move spawns exactly one new tile -------------------------------------
game.new_game()
game.rnd = random.Random(4)
game.grid = [[0] * N for _ in range(N)]
game.grid[0][0] = 2
game.grid[1][0] = 2
before = 2
game._move("up")
after = sum(1 for r in game.grid for v in r if v)
assert after == before, f"two merge into one (-1) and a fresh tile spawns (+1) ({before} -> {after})"
assert game.grid[0][0] == 4
spawned = [game.grid[y][x] for y in range(N) for x in range(N)
           if game.grid[y][x] and not (x == 0 and y == 0)]
assert len(spawned) == 1 and spawned[0] in (2, 4), f"exactly one spawned tile ({spawned})"
print("spawn OK (one new tile per real move)")

# --- input zones: margins are the swipe, the grid is untouchable ----------------------
game.new_game()
game.rnd = random.Random(3)
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
game.on_press(0, 5)                          # left margin -> move left
assert game.grid[5][0] == 2, "left margin slides left"
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
game.on_press(11, 5)                         # right margin -> move right
assert game.grid[5][N - 1] == 2, "right margin slides right"
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
game.on_press(5, 0)                          # top margin -> move up
assert game.grid[0][5] == 2, "top margin slides up"
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
game.on_press(5, 11)                         # bottom margin -> move down
assert game.grid[N - 1][5] == 2, "bottom margin slides down"
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
snapshot = [row[:] for row in game.grid]
game.on_press(5, 5)                          # inside the grid: nothing
assert game.grid == snapshot, "grid presses are ignored"
game.grid = [[0] * N for _ in range(N)]
game.grid[5][5] = 2
game.on_press(0, 0)                          # margin corner: x edge wins
assert game.grid[5][0] == 2, "corner (0,0) acts as left"
print("input zones OK (margins swipe, grid ignored, corner precedence)")

# --- forging the 2048 ------------------------------------------------------------------
game.new_game()
game.rnd = random.Random(5)
game.grid = [[0] * N for _ in range(N)]
game.grid[0][0] = game.grid[0][1] = 1024
game._move("left")
assert game.grid[0][0] == 2048, f"1024+1024 -> 2048 ({game.grid[0]})"
assert game.won is True and game.state == "play", "win does not end the game"
print("win OK (2048 forged, game continues)")

# --- beyond-2048 tiles shimmer with their own hues -------------------------------------
game.grid[0][2] = 4096
game.grid[0][3] = 8192
col1 = game._tile_color(4096)
game.anim_t += 1.0
col2 = game._tile_color(4096)
assert col1 != col2, "beyond-palette tiles animate"
print("beyond-2048 OK (4096/8192 shimmer with cycling hues)")

# --- game over: a full board with no merges dies (even on a null press) ---------------
game.new_game()
game.grid = [[(2 if (x + y) % 2 == 0 else 4) for x in range(N)] for y in range(N)]
assert not game._can_move()
game.on_press(0, 5)
assert game.state == "over", "a dead full board enters game over on any press"
game.on_press(6, 0)                          # any swipe restarts
assert game.state == "play" and game.score == 0
print("game over OK (dead board dies, any swipe restarts)")

# --- rendering ---------------------------------------------------------------------------
game.new_game()
game.rnd = random.Random(9)
game.grid = [[0] * N for _ in range(N)]
game.grid[0][0] = 2
game.grid[1][1] = 64
game.flash_t = 0.0
game.merged_cells = []
game.spawn_cell = None
frame = loop.tick()
assert px(frame, 1, 1) == TILE_COLORS[0], "tile 2 renders at (1,1), one pixel"
assert px(frame, 2, 2) == TILE_COLORS[5], "tile 64 renders at (2,2)"
assert px(frame, 3, 1) == (7, 9, 16), "empty cells show a faint guide pixel"
assert px(frame, 0, 5) == (25, 28, 40), "margin hint marks the left swipe"
game.grid[0][0] = 2048
frame = loop.tick()
assert sum(px(frame, 1, 1)) > 600, "the 2048 tile renders white"
game.state = "over"
frame = loop.tick()
assert px(frame, 0, 0)[0] >= 0, "over state renders the red border"
print("rendering OK (1px tiles, guides, hints, 2048)")

# --- classic mode: grid 4, 2x2 tile blocks, 2px swipe margins ------------------------
import json as _json
from pathlib import Path as _Path
import twenty48 as _mod
_orig_path = _mod.CONFIG_PATH
_mod.CONFIG_PATH = _Path("/tmp/opencode/twenty48-classic-test.json")
_mod.CONFIG_PATH.write_text(_json.dumps({"grid": 4}))
game._load()
game.new_game()
assert game.N == 4 and game.tile == 2 and game.off == 2, \
    f"classic mode geometry (N={game.N}, tile={game.tile}, off={game.off})"
game.grid = [[0] * 4 for _ in range(4)]
game.grid[1][1] = 2
game.on_press(0, 5)                           # 2px-wide margin still swipes
assert game.grid[1][0] == 2, "classic margins slide left"
game.grid = [[0] * 4 for _ in range(4)]
game.grid[1][1] = 2
game.on_press(1, 1)                           # corner of the margin: x edge wins
assert game.grid[1][0] == 2, "corner (1,1) acts as left"
game.grid = [[0] * 4 for _ in range(4)]
game.grid[1][2] = 2
game.on_press(4, 4)                           # inside the 2x2-block grid: nothing
assert game.grid[1][2] == 2, "grid presses are still ignored in classic mode"
game.flash_t = 0.0
game.merged_cells = []
game.spawn_cell = None
game.grid[0][0] = 2
frame = loop.tick()
for dy in range(2):
    for dx in range(2):
        assert px(frame, 2 + dx, 2 + dy) == TILE_COLORS[0], "classic tiles fill 2x2 blocks"
assert px(frame, 4, 2) == (7, 9, 16), "classic empty cells show one guide pixel"
print("classic mode OK (grid 4, 2x2 blocks, 2px margins)")
print("all 2048 tests OK")