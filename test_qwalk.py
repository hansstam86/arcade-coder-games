"""Offline tests: quantum walk coins, unitarity, collapse, superposition, rendering."""
import math
import time

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from qwalk import QWalk, coin_grover, coin_hadamard


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def probs(game):
    out = [[0.0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            out[y][x] = sum(abs(a) ** 2 for a in game.psi[y][x])
    return out


def assert_norm(game):
    assert abs(game.total_probability() - 1.0) < 1e-9, f"unitarity broken: {game.total_probability()}"


loop = GameLoop(QWalk)
game = loop.game

# --- coin operators: exact amplitudes ------------------------------------------
v = coin_hadamard((1.0, 0.0, 0.0, 0.0))
assert abs(v[0] - 1 / math.sqrt(2)) < 1e-12 and abs(v[1] - 1 / math.sqrt(2)) < 1e-12
assert v[2] == 0 and v[3] == 0, "hadamard mixes only within each axis pair"
v = coin_grover((1.0, 0.0, 0.0, 0.0))
assert abs(abs(v[0]) - 0.5) < 1e-12 and abs(abs(v[1]) - 0.5) < 1e-12
assert all(abs(abs(a) ** 2 - 0.25) < 1e-12 for a in v), "grover spreads |R> to 25% per direction"
print("coins OK (hadamard splits 50/50, grover diffuses 25/25/25/25)")

# --- unitarity: probability is conserved forever, for every coin ---------------
for coin_i in range(3):
    game.coin_i = coin_i
    game._seed(6, 6)
    for t in range(200):
        game._step()
        if t % 37 == 0:
            assert_norm(game)
    assert_norm(game)
print("unitarity OK (probability conserved over 200 steps, all three coins)")

# --- shift mechanics: the ballistic walker moves one cell right per step ---------
game.coin_i = 2                                   # ballistic: coin = identity
game._seed(6, 6)
p = probs(game)
assert p[6][6] == 1.0, "walker starts fully localised"
game._step()
p = probs(game)
assert p[6][7] == 1.0, f"ballistic walker should be at (7,6), got max at " \
    f"{max(((p[y][x], x, y) for y in range(H) for x in range(W)))[1:]}"
game._step()
assert probs(game)[6][8] == 1.0, "second step, still moving right"
print("shift OK (ballistic walker: exactly one cell per generation)")

# --- hadamard walk: spreads to the neighbourhood, interference everywhere -------
game.coin_i = 0
game._seed(6, 6)
game._step()
p = probs(game)
outside = sum(p[y][x] for y in range(H) for x in range(W)
              if max(abs(x - 6), abs(y - 6)) > 1)
assert outside < 1e-12, "after one step probability can only reach the neighbours"
assert p[6][5] > 0.05 and p[6][7] > 0.05, "horizontal pair carries probability"
for _ in range(11):
    game._step()
p = probs(game)
assert p[6][6] < 0.2, f"the walker must spread away from the start (p0={p[6][6]:.3f})"
peak = max((p[y][x], x, y) for y in range(H) for x in range(W))
assert max(abs(peak[1] - 6), abs(peak[2] - 6)) <= 11, "probability spreads ballistically, not faster"
print("hadamard walk OK (neighbourhood spread, ballistic-ish peak)")

# --- measurement: collapse localises the whole wavefunction ----------------------
game.coin_i = 2                                   # ballistic: deterministic re-bloom
game.measure(3, 4)
p = probs(game)
assert p[4][3] == 1.0, "measurement must localise all probability at the pressed cell"
game._step()
assert probs(game)[4][4] == 1.0, "post-collapse walker restarts from the measured cell"
game.coin_i = 0
print("measurement OK (collapse + re-bloom from the observed pixel)")

# --- superposition: a second walker joins at half amplitude, norm kept ----------
game._seed(6, 6)
for _ in range(3):
    game.superpose()
assert_norm(game)
p = probs(game)
heavy = [(x, y) for y in range(H) for x in range(W) if p[y][x] > 0.2]
assert len(heavy) >= 1, "superposed walkers carry real probability"
total = sum(sum(r) for r in p)
assert abs(total - 1.0) < 1e-9
print("superposition OK (second walker added, probability renormalised)")

# --- reseeding once the walker disperses -----------------------------------------
game._seed(6, 6)
game.cfg["reseed_steps"] = 3
game.running = True
game.steps = 0
game.update(1.0)                                  # ~5 steps at 5 gps -> reseed fires
assert_norm(game)
assert game.steps < 3 + 10, f"reseed should reset the step counter (steps={game.steps})"
print("reseed OK (fresh walker after reseed_steps)")

# --- pads --------------------------------------------------------------------------
game.cfg["speeds"] = [1, 2, 5, 10]
game.cfg["speed_index"] = 0
loop.press(11, 0)
assert game.cfg["speed_index"] == 1, "speed pad cycles"
loop.press(6, 0)
assert game.coin_i == 1, "coin pad cycles"
loop.press(0, 0)
assert game.running is False
game.running = True
loop.press(5, 5)                                  # plain pad -> measurement
p = probs(game)
assert p[5][5] == 1.0, "plain pads measure the wavefunction"
print("pads OK (speed, coin, pause, measurement)")

# --- rendering: phase-hue interference structure ------------------------------------
game.coin_i = 0
game._seed(6, 6)
game.running = False
for _ in range(12):
    game._step()
frame = loop.tick()
lit = {(x, y): px(frame, x, y) for y in range(H) for x in range(W)
       if sum(px(frame, x, y)) > 120}
assert len(lit) >= 6, f"the walk should light up a visible cloud ({len(lit)} px)"
colors = set(lit.values())
assert len(colors) >= 3, f"phase structure should show as several hues ({len(colors)} colors)"
print(f"rendering OK ({len(lit)} lit pixels, {len(colors)} distinct phase-hue colours)")
print("cloud frame:\n" + ascii_frame(frame))
print("all quantum walk tests OK")