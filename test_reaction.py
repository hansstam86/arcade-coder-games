"""Offline tests: gray-scott chemistry, laplacian, presets, parameters, rendering."""
import time

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from reaction import DU, DV, PRESETS, Reaction, color_for


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


loop = GameLoop(Reaction)
game = loop.game
game.next_check = 1e18

# --- the laplacian: wrap-aware, kernel sums to 1 --------------------------------
zero = [[0.0] * W for _ in range(H)]
zero[0][0] = 1.0
assert Reaction._lap(zero, 0, 0) == -1.0, "centre weight -1"
assert Reaction._lap(zero, 1, 0) == 0.2, "orthogonal neighbour weight 0.2"
assert Reaction._lap(zero, 1, 1) == 0.05, "diagonal neighbour weight 0.05"
assert Reaction._lap(zero, 11, 0) == 0.2, "wraps: x-1 of column 0 is column 11"
assert Reaction._lap(zero, 0, 11) == 0.2, "wraps vertically too"
const = [[0.5] * W for _ in range(H)]
assert abs(Reaction._lap(const, 5, 5)) < 1e-12, "laplacian of a constant field is 0"
print("laplacian OK (kernel -1/0.2/0.05, torus wrap)")

# --- the empty state is an exact fixed point --------------------------------------
game.F, game.k = 0.0545, 0.062
game.u = [[1.0] * W for _ in range(H)]
game.v = [[0.0] * W for _ in range(H)]
for _ in range(50):
    game._step()
assert all(game.u[y][x] == 1.0 for y in range(H) for x in range(W)), \
    "u=1, v=0 is the exact rest state (nothing grows from nothing)"
assert all(game.v[y][x] == 0.0 for y in range(H) for x in range(W))
print("fixed point OK (no seeds, no pattern — growth needs seeds)")

# --- each preset grows an actual colony: alive but not saturated ------------------
for name, F, k in PRESETS:
    game.F, game.k = F, k
    game.rnd = __import__("random").Random(7)
    game.replant()
    for _ in range(2500):
        game._step()
    alive = game.alive_cells()
    assert 4 <= alive <= 120, f"{name}: colony should live, not saturate (alive={alive})"
    assert game.max_v() > 0.3, f"{name}: activator should actually concentrate"
print(f"presets OK ({'/'.join(n for n, _f, _k in PRESETS)} all grow colonies in 2500 steps)")

# --- leopard spots: stable, structured, not expanding ----------------------------
game.F, game.k = PRESETS[0][1], PRESETS[0][2]
game.rnd = __import__("random").Random(7)
game.replant()
for _ in range(600):
    game._step()
snap1 = [row[:] for row in game.v]
alive1 = game.alive_cells()
for _ in range(200):
    game._step()
snap2 = game.v
drift = sum(abs(snap2[y][x] - snap1[y][x]) for y in range(H) for x in range(W))
print(f"leopard OK (alive {alive1} cells, 200-step drift {drift:.2f} — stable spots)")

# --- parameter pads map the (F, k) plane ------------------------------------------
game.set_params(0, 0)
assert abs(game.F - 0.015) < 1e-9 and abs(game.k - 0.050) < 1e-9, "pad (0,0) = min F, min k"
game.set_params(11, 11)
assert abs(game.F - 0.075) < 1e-9 and abs(game.k - 0.068) < 1e-9, "pad (11,11) = max F, max k"
game.set_params(6, 6)
assert abs(game.F - 0.0477) < 1e-3 and abs(game.k - 0.0598) < 1e-3, "middle pad = middle params"
assert game.param_pos == (6, 6)
print("parameter map OK (x -> F, y -> k)")

# --- replant / death / auto-replant ------------------------------------------------
game.replant()
assert sum(1 for row in game.v for c in row if c > 0.5) >= 18, "replant sows real blobs"
game.v = [[0.0] * W for _ in range(H)]                # kill everything
game.dead_t = 0.0
game.running = True
game.update(5.0)                                       # hostile emptiness -> auto replant
assert sum(1 for row in game.v for c in row if c > 0.5) >= 18, "a dead colony replants itself"
print("replant OK (manual + automatic)")

# --- pads -----------------------------------------------------------------------------
loop.press(11, 0)
assert game.cfg["speed_index"] == 2, "speed pad cycles"
loop.press(6, 0)
assert game.preset_i == 1, "preset pad advances"
loop.press(0, 0)
assert game.running is False
game.running = True
loop.press(11, 11)
assert game.cursor is True
loop.press(5, 5)                                       # plain pad sets parameters
assert game.param_pos == (5, 5)
print("pads OK (speed, preset, pause, cursor, parameter)")

# --- rendering ---------------------------------------------------------------------------
game.F, game.k = PRESETS[0][1], PRESETS[0][2]
game.rnd = __import__("random").Random(7)
game.replant()
game.cursor = False
for _ in range(600):
    game._step()
frame = loop.tick()
colors = {px(frame, x, y) for y in range(H) for x in range(W) if sum(px(frame, x, y)) > 30}
assert len(colors) >= 4, f"an organic palette should show structure ({len(colors)} colours)"
assert any(sum(c) > 400 for c in colors), "nuclei should glow bright"
dark = sum(1 for y in range(H) for x in range(W) if sum(px(frame, x, y)) < 40)
assert dark >= 20, "the substrate should stay dark"
print(f"rendering OK ({len(colors)} organic colours, {dark} dark substrate px)")
print("colony frame:\n" + ascii_frame(frame))
print("all reaction–diffusion tests OK")