"""Offline tests: prism optics, mixing, level solvability, interaction, rendering."""
import itertools
import time

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from prism import B, G, LEVELS, MASK_COLORS, R, Prism, reflect


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


# --- mirror reflection: right angles, both mirrors, both axes ---------------------
assert reflect(1, 0, "/") == (0, -1), "'/' sends rightward light up"
assert reflect(1, 0, "\\") == (0, 1), "'\\' sends rightward light down"
assert reflect(-1, 0, "/") == (0, 1), "'/' sends leftward light down"
assert reflect(0, 1, "\\") == (1, 0), "'\\' sends downward light right"
assert reflect(0, -1, "/") == (1, 0)
print("mirrors OK (right-angle reflection both ways)")

# --- every level: initial state unsolved, at least one solution exists ------------
for idx, (name, sources, mirrors, targets) in enumerate(LEVELS):
    game_for_check = Prism()
    game_for_check.start()
    game_for_check.load_level(idx)
    assert not game_for_check.satisfied(), f"level '{name}' must start unsolved"
    assert game_for_check.paths, "every level has beams"
    for _mask, path in game_for_check.paths:
        assert len(path) < 160, "beams must terminate (loop guard effective)"
    positions = [(x, y) for x, y, _m in mirrors]
    solutions = 0
    for combo in itertools.product("/\\", repeat=len(mirrors)):
        game_for_check.mirrors = dict(zip(positions, combo))
        game_for_check.recompute()
        if game_for_check.satisfied():
            solutions += 1
            # every target truly lit with its colour contained
            for tx, ty, req in targets:
                got = game_for_check.cells.get((tx, ty), 0)
                assert got & req == req, f"{name}: target {req} served by {got}"
    assert solutions >= 1, f"level '{name}' has no solution"
print(f"levels OK ({len(LEVELS)} levels: all start unsolved, all solvable by brute force)")

# --- additive mixing: crossing beams make new colours ------------------------------
loop = GameLoop(Prism)
game = loop.game
game.next_check = 1e18
game.load_level(1)                                  # make yellow
game.mirrors[(7, 3)] = "\\"
game.mirrors[(3, 7)] = "\\"
game.recompute()
assert game.cells[(7, 7)] == R | G, f"red + green = yellow ({game.cells.get((7, 7))})"
assert game.satisfied(), "the yellow target is lit"
assert game.cells[(3, 3)] == R | G, "beams crossing mid-flight also mix"
print("mixing OK (R+G=yellow where beams cross)")

# --- flipping a mirror reroutes the beam -------------------------------------------
game.load_level(0)
assert (8, 1) not in game.cells, "with '\\' the beam goes down, target dark"
game.on_press(8, 5)                                 # flip the mirror
assert game.mirrors[(8, 5)] == "/", "press flips \\ to /"
assert game.cells[(8, 1)] == R, "the beam now bends up and lights the target"
assert game.state == "won", "lighting all targets wins the level"
print("flip OK (mirror toggle reroutes light and solves the level)")

# --- non-mirror presses do nothing; wins auto-advance ------------------------------
game.load_level(0)
snap = dict(game.mirrors)
game.on_press(3, 3)                                # empty cell: nothing
assert game.mirrors == snap and game.state == "play"
game.on_press(8, 5)                                 # solve it
assert game.state == "won"
before = game.level_i
game.won_at = time.monotonic() - 3.0
game.update(0.01)
assert game.level_i == before + 1 and game.state == "play", "win advances after the beat"
print("flow OK (empty presses ignored, wins advance)")

# --- corner pads --------------------------------------------------------------------
game.load_level(2)
game.on_press(0, 0)
assert game.level_i == 1, "top-left goes back a level"
game.on_press(11, 11)
assert game.level_i == 2, "bottom-right skips forward"
game.on_press(0, 11)
assert game.level_i == 2 and game.state == "play", "bottom-left restarts the level"
print("corner pads OK (prev, skip, restart)")

# --- rendering ------------------------------------------------------------------------
game.load_level(0)
game.t = 0.31
frame = loop.tick()
c = px(frame, 4, 5)
assert all(abs(c[k] - MASK_COLORS[R][k]) < 15 for k in range(3)), \
    f"beam cells render pulsing red ({c})"
assert px(frame, 0, 5)[1] > MASK_COLORS[R][1] * 2, "the source renders pushed toward white"
m = px(frame, 8, 5)
assert m == (255, 255, 255), f"'\\' mirrors render bright white ({m})"
tgt = px(frame, 8, 1)
assert tgt == tuple(int(cc * 0.28) for cc in MASK_COLORS[R]), "unlit target asks dimly"
game.mirrors[(8, 5)] = "/"
game.recompute()
frame = loop.tick()
assert px(frame, 8, 5) == (170, 170, 190), "'/' mirrors render dim — orientation readable"
lit = px(frame, 8, 1)
assert sum(lit) > 3 * sum(tgt), "a lit target blazes"
game.t += 1.25                                      # pulse travels along the beam
frame = loop.tick()
boosted = [px(frame, x, 5) for x in range(0, 9)]
assert any(sum(cc) > sum(MASK_COLORS[R]) for cc in boosted), "comet pulses brighten the beam"
print("rendering OK (beams, sources, mirror states, dim asks, comet pulses)")
print("all prism tests OK")