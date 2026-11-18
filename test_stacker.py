"""Offline tests: stacker drops, overlap trimming, perfect streaks, states."""
import time

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from stacker import Stacker


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


loop = GameLoop(Stacker)
game = loop.game
game.next_check = 1e18

# --- new game: centred base, sliding row above it -------------------------------
game.new_game()
assert game.tower == {11: (3, 6)}, f"base row centred and full start width ({game.tower})"
assert game.state == "slide" and game.top_y == 11 and game.w == 6
print("new game OK (centred 6-wide base, row sliding at y=10)")

# --- sliding stays in bounds and bounces -----------------------------------------
game.pos, game.dir = 0.0, 1
for _ in range(400):
    game.update(0.05)
    w = min(W, game.w)
    assert -1e-9 <= game.pos <= W - w + 1e-9, f"position out of bounds ({game.pos})"
assert game.dir in (-1, 1)
print("sliding OK (stays in bounds, ping-pongs)")

# --- perfect drop keeps full width, streak grows ----------------------------------
game.new_game()
game.pos = 3.2                                   # rounds to 3, exactly on the base
game.dir = 1
game.drop()
assert game.state == "flash", "a landed row enters the flash beat"
assert game.tower[10] == (3, 6), f"perfect drop keeps full width ({game.tower.get(10)})"
assert game.streak == 1 and game.perfects == 1
assert game.top_y == 10 and game.w == 6
print("perfect drop OK (full width, streak counts)")

# --- partial drop trims the overhang, streak resets -------------------------------
game.new_game()
game.pos = 6.2                                   # rounds to 6: overlap 6..9 -> width 3
game.drop()
assert game.tower[10] == (6, 3), f"only the overlap survives ({game.tower.get(10)})"
assert game.streak == 0
assert len(game.lost_cells) == 3, "the lost overhang is remembered for the red flash"
print("partial drop OK (trimmed to overlap, overhang tracked)")

# --- a complete miss is game over --------------------------------------------------
game.new_game()
game.pos = 11.0                                  # 11..16 vs base 3..9: no overlap
game.drop()
assert game.state == "over"
assert game.tower[10] is None if 10 in game.tower else 10 not in game.tower, "missed row never lands"
assert game.top_y == 11, "the tower stands where it was"
print("miss OK (game over, tower stands)")

# --- three perfects blossom the tower wider ---------------------------------------
game.new_game()
w0 = game.w
for i in range(3):                               # three perfect drops in a row
    assert game.state in ("slide", "flash")
    if game.state == "flash":
        game.anim_t = 0.0
        game.update(0.01)
    tx, tw = game.tower[game.top_y]
    game.pos = float(tx)
    game.drop()
assert game.w == w0 + 1, f"bonus streak widens the tower ({game.w} vs {w0})"
assert game.streak == 0, "streak spent on the blossom"
print("bonus OK (3 perfects -> tower blossoms a cell wider)")

# --- climbing: reach the top row and win ---------------------------------------------
game.new_game()
for _ in range(H - 1):                          # 11 clean drops, each perfectly aligned
    if game.state == "flash":
        game.anim_t = 0.0
        game.update(0.01)
    if game.state in ("over", "win"):
        break
    tx, tw = game.tower[game.top_y]
    game.pos = float(tx)
    game.drop()
assert game.state == "win", f"reaching y=0 wins (state={game.state})"
print("win OK (topped out -> rainbow cascade)")

# --- any press restarts after over/win ----------------------------------------------
game.state = "over"
game.on_press(5, 5)
assert game.state == "slide" and game.top_y == 11, "any pad restarts a finished game"

# --- speed rises with height ----------------------------------------------------------
game.new_game()
s_low = game._speed()
game.tower[10] = (3, 6)
game.top_y = 10
game.w = 6
s_high = game._speed()
assert s_high > s_low, "each row climbed makes the row slide faster"
print(f"speed OK ({s_low:g} at the base -> {s_high:g} one row up)")

# --- rendering ---------------------------------------------------------------------------
game.new_game()
game.pos = 3.0
frame = loop.tick()
assert all(sum(px(frame, cx, 10)) > 600 for cx in range(3, 9)), \
    "the sliding row renders white-hot"
base = {px(frame, cx, 11) for cx in range(3, 9)}
assert len(base) == 1, f"the base row is one flat colour ({base})"
top_of_base = px(frame, 3, 11)
frame_rows = px(frame, 3, 11)
game.drop()                                     # perfect drop -> flash
frame = loop.tick()
assert sum(px(frame, 3, 10)) > 400, "a perfect row pulses gold"
game.state = "over"                              # miss blink red
game.miss_row = (10, 2, 4)
game.anim_t = 0.5
frame = loop.tick()
assert px(frame, 2, 10)[0] > 100, "the missed row blinks red"
print("rendering OK (white slider, flat rainbow rows, gold perfects, red misses)")
print("all stacker tests OK")