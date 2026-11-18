"""Offline tests: quantum garden lifecycle, twins, gust, wind, rendering."""
import time

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from qgarden import R_HOME, Plant, QGarden
from qwalk import COINS


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def probs_of(plant):
    return [[sum(abs(a) ** 2 for a in plant.psi[y][x]) for x in range(W)] for y in range(H)]


def garden_density(game):
    dens = [[0.0] * W for _ in range(H)]
    for p in game.plants:
        pp = probs_of(p)
        for y in range(H):
            for x in range(W):
                dens[y][x] += pp[y][x]
    return dens


loop = GameLoop(QGarden)
game = loop.game

# --- plants are born localised and unitary while in bloom ------------------------
game.plants = []
game.plant(2, 2)
assert len(game.plants) == 1
plant = game.plants[0]
p = probs_of(plant)
assert abs(p[2][2] - 1.0) < 1e-9, "a seed starts fully localised"
for t in range(plant.prime):
    assert plant.step(), "a plant must not die before its prime"
    assert abs(plant.total_probability() - 1.0) < 1e-9, f"bloom must stay unitary (t={t})"
p = probs_of(plant)
spread = sum(p[y][x] for y in range(H) for x in range(W)
             if max(abs(x - 2), abs(y - 2)) > 1)
assert spread > 0.1, f"a blooming plant spreads (spread={spread:.3f})"
print("bloom OK (localised birth, unitary spread, no early death)")

# --- decoherence: after the prime the cloud pulls back home ---------------------
outside_prime = 1.0 - plant.home_mass(R_HOME)
for _ in range(30):
    plant.step()
assert abs(plant.total_probability() - 1.0) < 1e-9, "renormalised after damping"
outside_wither = 1.0 - plant.home_mass(R_HOME)
assert outside_wither < outside_prime, (
    f"decoherence must pull the cloud home ({outside_wither:.3f} vs {outside_prime:.3f})")
while plant.age < plant.lifetime - 2:               # wither all the way to the end
    assert plant.step()
assert plant.home_mass(1.5) > 0.7, \
    f"the plant should end its life as a concentrated seed-dot ({plant.home_mass(1.5):.3f})"
print(f"wither OK (outside-home mass {outside_prime:.2f} -> {outside_wither:.2f}, "
      f"ends as a dot at {plant.home_mass(1.5):.2f})")

# --- death at lifetime -------------------------------------------------------------
born = plant.age
plant.prime = 0                                   # force straight into wither
plant.lifetime = plant.age + 3
for _ in range(4):
    plant.step()
assert plant.age >= plant.lifetime, "age keeps counting"
dead = not plant.step()
assert dead, "a plant must die after its lifetime"
print("death OK (plant removed at lifetime)")

# --- the garden steps its whole population ----------------------------------------
game.plants = []
game.plant(3, 3)
game.plant(8, 8)
before = [p.age for p in game.plants]
game._step()
assert all(p.age == b + 1 for p, b in zip(game.plants, before)), "garden ages all plants"
assert len(game.plants) == 2
print("garden step OK (whole population ages together)")

# --- entangled twins: one wavefunction, two sites in superposition -----------------
game.plants = []
game.plant(2, 6, twin=(9, 6))
assert len(game.plants) == 1, "twins are ONE plant"
tw = game.plants[0]
p = probs_of(tw)
assert abs(p[6][2] - 0.5) < 1e-9 and abs(p[6][9] - 0.5) < 1e-9, \
    f"twins carry half probability each ({p[6][2]:.3f}, {p[6][9]:.3f})"
for _ in range(10):
    tw.step()
assert abs(tw.total_probability() - 1.0) < 1e-9, "twins stay unitary"
print("entangled twins OK (single wavefunction, half/half superposition)")

# --- max population ------------------------------------------------------------------
game.plants = []
game.cfg["max_plants"] = 3
for _ in range(5):
    game.plant(1, 1)
assert len(game.plants) == 3, f"garden respects max_plants ({len(game.plants)})"
print("population cap OK")

# --- gust, clear, wind --------------------------------------------------------------
game.plants = []
game.gust()
assert len(game.plants) == 3, "gust scatters three seeds"
loop.press(0, 11)
assert game.plants == [], "clear pad empties the garden"
game.cfg["wind_seconds"] = 0.0
game.running = True
game.update(0.2)                                  # empty garden -> wind blows a seed in
assert len(game.plants) == 1, f"wind should reseed an empty garden ({len(game.plants)})"
print("gust / clear / wind OK")

# --- pads -----------------------------------------------------------------------------
loop.press(11, 0)
assert game.cfg["speed_index"] == 3, "speed pad cycles"
loop.press(0, 0)
assert game.running is False
game.running = True
loop.press(5, 5)
assert len(game.plants) >= 2 and abs(probs_of(game.plants[-1])[5][5] - 1.0) < 1e-9, \
    "plain pads plant seeds"
print("pads OK (speed, pause, plant)")

# --- rendering: hue variety across species, overlap washes to white ------------------
game.plants = []
game.running = False
a = game._plant(2, 2)
b = game._plant(9, 9)
a.hue, b.hue = 0.0, 0.5                           # force distinct species hues
for _ in range(8):
    a.step()
    b.step()
frame = loop.tick()
lit = {px(frame, x, y) for y in range(H) for x in range(W) if sum(px(frame, x, y)) > 100}
assert len(lit) >= 3, f"distinct species hues should show ({len(lit)} colors)"
print(f"rendering OK ({len(lit)} distinct colors across two species)")
print("garden frame:\n" + ascii_frame(frame))
print("all quantum garden tests OK")