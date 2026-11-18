"""Offline tests: aurora field, palettes, ripples, freeze, rendering."""
import math

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from aurora import FREEZE_PAD, PALETTES, PALETTE_PAD, PULSE_PAD, SPEED_PAD, STILL_PAD, Aurora, _palette_color, _torus_dist


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


# --- torus distance wraps ----------------------------------------------------------
assert _torus_dist(0, 0, 1, 0) == 1.0
assert _torus_dist(0, 0, 11, 0) == 1.0, "distance wraps the short way round the torus"
assert abs(_torus_dist(0, 0, 6, 6) - math.sqrt(72)) < 1e-9
print("torus distance OK")

# --- palette: exact at stops, smooth in between, cyclic ---------------------------
stops = PALETTES[0][1]
assert _palette_color(stops, 0.0) == stops[0], "t=0 hits the first stop exactly"
assert _palette_color(stops, 0.999) != _palette_color(stops, 0.99), "nearing the wrap moves"
mid = _palette_color(stops, 0.5 / len(stops))
a, b = stops[0], stops[1]
assert all(min(a[c], b[c]) <= mid[c] <= max(a[c], b[c]) for c in range(3)), \
    "between stops interpolates through, not around"
print("palette OK (exact stops, smooth cyclic interpolation)")

loop = GameLoop(Aurora)
game = loop.game
HUD = {FREEZE_PAD, SPEED_PAD, PALETTE_PAD, STILL_PAD, PULSE_PAD}

# --- the base field is smooth: neighbours differ only gently -----------------------
game.ripples = []
game.t = 7.3
frame = loop.tick()
worst = 0
for y in range(H):
    for x in range(W):
        if (x, y) in HUD:
            continue
        for nx, ny in ((x + 1, y), (x, y + 1)):
            if nx < W and ny < H and (nx, ny) not in HUD:
                d = max(abs(px(frame, x, y)[c] - px(frame, nx, ny)[c]) for c in range(3))
                worst = max(worst, d)
assert worst <= 150, f"plasma should flow without harsh jumps (worst neighbour delta {worst}, HUD pads excluded)"
print(f"field smoothness OK (worst neighbour channel delta {worst})")

# --- it flows: frozen field is constant, flowing field moves ------------------------
game.ripples = []
game.running = False
f1 = loop.tick()
f2 = loop.tick()
assert f1 == f2, "frozen field holds still"
game.running = True
game.t += 0.4
f3 = loop.tick()
assert f3 != f1, "flowing field moves"
print("flow OK (freeze holds, time moves the field)")

# --- ripples: a young one changes the field, then its contribution decays ----------
game.ripples = []
game.t = 10.0
base_frame = loop.tick()
game.add_ripple(5.0, 5.0, amp=1.2)
game.t += 0.05                                   # ripple born a moment ago
young = loop.tick()
assert young != base_frame, "a fresh ripple disturbs the field"

def ripple_contribution(t):
    """The ripple's effect at time t: field with ripple minus field without."""
    game.t = t
    game.ripples = [(5.0, 5.0, 10.0, 1.2)]
    with_r = game.field(6.0, 5.0)                # one pixel from the epicentre
    game.ripples = []
    without = game.field(6.0, 5.0)
    return with_r - without

c_young = ripple_contribution(10.05)
c_old = ripple_contribution(13.0)
c_gone = ripple_contribution(22.0)
assert abs(c_young) > 0.4, f"a fresh ripple should push the field hard ({c_young:.3f})"
assert abs(c_gone) < 0.05, f"an old ripple should have faded away ({c_gone:.4f})"
assert abs(c_gone) < abs(c_old) < abs(c_young), "the influence decays over time"
print(f"ripples OK (contribution {abs(c_young):.2f} -> {abs(c_gone):.4f})")
print("ripples OK (born loud, fading into the field)")

# --- pads ---------------------------------------------------------------------------
loop.press(11, 0)
assert game.cfg["speed_index"] == 2, "speed pad cycles"
loop.press(6, 0)
assert game.palette_i == 1, "palette pad cycles"
loop.press(0, 11)
assert game.ripples == [], "still pad clears ripples"
loop.press(5, 5)
assert len(game.ripples) == 1, "plain pads drop ripples"
loop.press(11, 11)
assert len(game.ripples) == 2 and game.ripples[-1][3] == 2.5, "pulse pad fires the big one"
loop.press(0, 0)
assert game.running is False
game.running = True
print("pads OK (speed, palette, still, ripple, pulse, freeze)")

# --- rendering: rich, alive, never dead pixels ----------------------------------------
game.ripples = []
game.t = 3.1
frame = loop.tick()
colors = {px(frame, x, y) for y in range(H) for x in range(W)}
assert len(colors) >= 20, f"a palette gradient should render richly ({len(colors)} colours)"
assert all(sum(c) > 30 for c in colors), "no dead pixels on the aurora"
print(f"rendering OK ({len(colors)} distinct colours, all alive)")
print("aurora frame:\n" + ascii_frame(frame))
print("all aurora tests OK")