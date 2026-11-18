"""Offline tests: grover operator, sin^2 dynamics, measurement, rounds, rendering."""
import math
import random
import time

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from grover import A0, BLUE, GOLD, OPTIMUM_K, Grover


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def norm(game):
    return sum(a * a for a in game.amps)


loop = GameLoop(Grover)
game = loop.game
game.target = 55                                   # (7, 4) — deterministic round
game.amps = [A0] * 144

# --- the operator is unitary and matches the sin^2((2k+1)theta) dynamics --------
theta = math.asin(1 / math.sqrt(144))
for k in range(1, 31):
    game.iterate()
    assert abs(norm(game) - 1.0) < 1e-9, f"norm broken at iteration {k}"
    expected = math.sin((2 * k + 1) * theta) ** 2
    got = game.amps[game.target] ** 2
    assert abs(got - expected) < 1e-9, f"iteration {k}: p(target) {got:.6f} != {expected:.6f}"
    if k == OPTIMUM_K:
        assert got > 0.95, f"peak near k=9 (got {got:.4f})"
game.amps = [A0] * 144
game.iters = 0
for _ in range(18):
    game.iterate()
assert game.amps[game.target] ** 2 < 0.02, "the wave breathes — p collapses again near k=18"
print("grover operator OK (unitary; matches sin^2((2k+1)theta) to 1e-9 for 30 steps)")

# --- over-rotation drives the field negative ------------------------------------
game.amps = [A0] * 144
game.iters = 0
for _ in range(12):
    game.iterate()
others = [game.amps[i] for i in range(144) if i != game.target]
assert all(a < 0 for a in others), "past the peak every other amplitude is negative"
print("over-rotation OK (field flips sign after the peak)")

# --- measurement: projective semantics -------------------------------------------
random.seed(1)
game.amps = [A0] * 144
game.iters = 0
game.state = "search"
game.measure(7, 4)                                  # wrong: target is pixel 55 = (7,4)? no: 55//12=4, 55%12=7 -> (7,4). use a different pixel
game.amps = [A0] * 144
game.state = "search"
game.measure(0, 11)                                 # definitely not the target
assert game.state == "miss", "measuring an unmarked pixel must miss"
game.amps = [A0] * 144
game.state = "search"
game.target = 0                                     # target IS the measured pixel
for _ in range(OPTIMUM_K):
    game.iterate()
saved = random.random
random.random = lambda: 0.99                        # inside p ~ 0.9998 -> success
game.measure(0, 0)
random.random = saved
assert game.state == "win", "measuring the peaked target should win"
print("measurement OK (wrong pixel misses, peaked target wins)")

# --- measuring too early can fail honestly ---------------------------------------
game.new_round()
game.target = 0
game.amps = [A0] * 144
game.state = "search"
game.iters = 0
saved = random.random
random.random = lambda: 0.5                         # p(target) = 1/144 < 0.5
game.measure(0, 0)
random.random = saved
assert game.state == "miss", "unrotated target has p=1/144 — measurement should miss"
print("honest early measurement OK (p=1/144 fails the sample)")

# --- rounds ------------------------------------------------------------------------
t0 = game.target
game.state = "win"
game.reveal_at = time.monotonic() - 10.0
game.update(0.01)                                   # reveal expired -> new round
assert game.state == "search" and game.iters == 0
assert abs(norm(game) - 1.0) < 1e-9
t1 = game.target
game.restart_round()
assert game.iters == 0 and abs(norm(game) - 1.0) < 1e-9 and game.target == t1, \
    "restart keeps the current target; new_round had picked a fresh one"
print("round flow OK (reveal -> new round, restart keeps the target)")

# --- pads ---------------------------------------------------------------------------
loop.press(6, 0)
assert game.iters == 1, "top-centre pad cranks one iteration"
loop.press(0, 0)
assert game.running is True
loop.press(11, 0)
assert game.cfg["speed_index"] == 2, "speed pad cycles"
loop.press(0, 11)
assert game.iters == 0, "restart pad resets the round"
print("pads OK (iterate, auto-run, speed, restart)")

# --- rendering ------------------------------------------------------------------------
game.target = 55
game.amps = [A0] * 144
game.iters = 0
game.state = "search"
game.running = False                                # keep HUD pause pixel red-free for field checks
frame = loop.tick()
dim = px(frame, 1, 1)
assert dim == tuple(int(c * A0 * 1.1) for c in GOLD), f"uniform field renders dim gold ({dim})"
for _ in range(OPTIMUM_K):
    game.iterate()
frame = loop.tick()
bright = px(frame, 7, 4)
assert sum(bright) > 500, f"the peaked target should blaze ({bright})"
frame_dark = px(frame, 2, 2)
assert sum(frame_dark) < 40, f"the drained field should be dark ({frame_dark})"
green_opt = px(frame, 0, 10)
assert green_opt == (0, 140, 60), "the optimum marker sits on the left column"
print(f"rendering OK (target blazes {bright}, field drains to {frame_dark})")

game.state = "win"
game.reveal_at = time.monotonic()
game.target = 55
frame = loop.tick()
assert px(frame, 7, 4)[1] > 150, "win reveal pulses the target green"
game.state = "miss"
game.reveal_at = time.monotonic()
game.target = 55
game.last_measured = 0
frame = loop.tick()
assert px(frame, 0, 0)[0] >= 0 and px(frame, 7, 4) == (255, 200, 60), \
    "miss reveal shows the target in gold"
print("reveals OK (win pulse, miss shows the target)")
print("all grover search tests OK")