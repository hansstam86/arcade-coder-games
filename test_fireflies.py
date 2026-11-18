"""Offline tests: kuramoto dynamics, synchronization, pokes, rendering."""
import math
import random

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from fireflies import TWO_PI, Fireflies, _r, _status

N = 144


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def run_sim(game, seconds: float, dt: float = 0.05) -> None:
    n = int(seconds / dt)
    for _ in range(n):
        game.update(dt)


loop = GameLoop(Fireflies)
game = loop.game
game.next_rlog = 1e18                     # silence the periodic r log during tests

# --- the order parameter and its labels ----------------------------------------
assert _r([0.0] * 144) > 0.999, "identical phases give r = 1"
random.seed(7)
assert _r([random.random() * TWO_PI for _ in range(144)]) < 0.3, "random phases give low r"
assert _status(0.05) == "chaos" and _status(0.5) == "waves forming"
assert _status(0.9) == "nearly synced" and _status(0.99) == "SYNCHRONIZED"
print("order parameter OK")

# --- zero coupling: phases advance at their own omega, order stays low ----------
game.cfg["coupling"] = [0.0]
game.cfg["K_index"] = 0
game.uniform_omegas = False
game.rnd = random.Random(42)
game._roll_frequencies()
game._chaos()
r0 = game.order()
run_sim(game, 20.0)
assert game.order() < 0.4, f"with K=0 the swarm must stay disordered (r={game.order():.3f})"
print(f"K=0 OK (no sync without coupling; r stays {game.order():.3f})")

# --- strong coupling: consensus emerges from chaos ------------------------------
game.cfg["coupling"] = [0.8, 2.0, 4.0]
game.cfg["K_index"] = 2
game.rnd = random.Random(42)
game._roll_frequencies()
game._chaos()
assert game.order() < 0.4, "chaos pad starts disordered"
run_sim(game, 60.0)
r = game.order()
assert r > 0.9, f"strong local coupling must synchronize the swarm (r={r:.3f})"
print(f"synchronization OK (r {r0:.2f} -> {r:.3f} in 60s of sim time)")

# --- a poke desyncs one firefly and the wound heals ------------------------------
game.phases = [game.phases[0]] * 144                          # full consensus
game.omegas = [game.omegas[0]] * 144                          # and identical omegas
i_poke = 5 * 12 + 5
r_before = game.order()
assert r_before > 0.999, "starting from consensus"
game.phases[i_poke] = 3.0                                     # a wound in the consensus
r_wounded = game.order()
assert r_wounded < r_before, "the poke dents the order parameter (a 1/144 dent)"
run_sim(game, 30.0)
assert game.order() > 0.9995, f"the wound should heal (r={game.order():.4f})"
d = max(abs(((p - game.phases[i_poke] + math.pi) % TWO_PI) - math.pi)
        for p in (game.phases[i_poke - 1], game.phases[i_poke + 1]))
assert d < 0.2, f"the poked firefly should rejoin its neighbours (gap {d:.3f})"
print(f"poke healing OK (r {r_wounded:.2f} -> {game.order():.4f}, neighbour gap {d:.3f})")

# --- pads -------------------------------------------------------------------------
loop.press(6, 0)                                # chaos pad
assert game.order() < 0.4, "chaos pad scrambles everything"
loop.press(0, 11)                               # metronome pad
assert game.order() > 0.999, "metronome snaps every phase to 0"
loop.press(11, 0)                               # coupling pad cycles K_index 2 -> 0
assert game.cfg["K_index"] == 0
loop.press(0, 0)                                # pause
assert game.running is False
before = list(game.phases)
loop.tick()
assert game.phases == before, "paused swarm must not move"
game.running = True
loop.press(11, 11)                              # uniform frequencies toggle
assert game.uniform_omegas is True
assert len(set(game.omegas)) == 1, "uniform pad makes all omegas equal"
loop.press(4, 4)                                # plain pad pokes pixel (4,4)
poked = 4 * 12 + 4
game.rnd = random.Random(99)
game.phases[poked] = 0.0
loop.press(4, 4)
assert game.phases[poked] != 0.0, "poke pad scrambles that firefly's phase"
print("pads OK (chaos, metronome, coupling, pause, uniform, poke)")

# --- rendering ----------------------------------------------------------------------
game.phases = [0.0] * 144                       # all at flash peak, hue 0
frame = loop.tick()
c0 = px(frame, 5, 5)
assert c0[0] > 240 and c0[1] < 40 and c0[2] < 40, f"phase 0 should flash bright red ({c0})"
game.phases = [math.pi] * 144                   # all mid-cycle: no flash, hue 0.5
frame = loop.tick()
cpi = px(frame, 5, 5)
assert sum(cpi) < 70, f"phase pi should be nearly dark ({cpi})"
assert cpi != c0, "rendering must distinguish phases"
# desynchronized board shows many colors
game._chaos()
frame = loop.tick()
colors = {px(frame, x, y) for y in range(H) for x in range(W) if sum(px(frame, x, y)) > 40}
assert len(colors) >= 10, f"chaotic swarm should twinkle in many colours ({len(colors)})"
print(f"rendering OK (flash peak {c0}, dark phase {cpi}, {len(colors)} twinkling colours)")
print("all fireflies tests OK")