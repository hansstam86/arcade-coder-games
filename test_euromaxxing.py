"""Offline tests: euromaxxing modes, palette discipline, glyphs, facts ticker."""
import json
import time
from pathlib import Path

from arcadecoder import H, Screen, W
from arcadecoder.runner import GameLoop
from euromaxxing import DEFAULT, GLYPHS, Euromaxxing

GOLD = tuple(DEFAULT["gold"])
FLAG_BLUE = tuple(DEFAULT["flag_blue"])
GROUND_BLUE = tuple(DEFAULT["ground_blue"])


def px(hexes, x, y):
    s = hexes[y * W + x].lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def ascii_frame(hexes: list[str]) -> str:
    chars = " .:-=+*#%@"
    rows = []
    for y in range(H):
        rows.append("".join(chars[min(9, int(sum(px(hexes, x, y)) / 765 * 10))] for x in range(W)))
    return "\n".join(rows)


def glyph_cells(rows):
    return {(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "#"}


# --- the glyphs are well-formed 12x12 grids with real ink -----------------------
for name, rows in GLYPHS:
    assert len(rows) == 12, f"{name} must be 12 rows"
    assert all(len(r) == 12 for r in rows), f"{name} rows must be 12 wide"
    assert len(glyph_cells(rows)) > 25, f"{name} should have some ink"
print(f"glyphs OK ({[n for n, _ in GLYPHS]})")

loop = GameLoop(Euromaxxing)
game = loop.game
assert game.cfg["modes"][game.mode_i] == "mark"

# --- mark mode: gold ink lands exactly on the glyph, field stays flag blue -------
frame = loop.tick()
eu_cells = glyph_cells(GLYPHS[0][1])
for x, y in eu_cells:
    r, g, b = px(frame, x, y)
    assert r > 200 and g > 150 and b < 20, f"glyph pixel {(x, y)} should be gold, got {px(frame, x, y)}"
for y in range(H):
    for x in range(W):
        if (x, y) not in eu_cells:
            assert px(frame, x, y) == FLAG_BLUE, f"field pixel {(x, y)} should be flag blue"
print("mark mode OK (EU glyph in gold on the cranked flag blue)")

# --- glyph alternation with the blue blink ---------------------------------------
game.glyph_t = 999.0
game.update(1.0)                                  # trips the alternation timer
assert game.glyph_i == 1, "glyph should alternate"
frame = loop.tick()                               # flash window: blue-only frame
assert all(px(frame, x, y) == FLAG_BLUE for y in range(H) for x in range(W)), \
    "the blink frame should hide the glyph"
game.flash_until = time.monotonic() - 0.01
frame = loop.tick()                               # EUR glyph appears
eur_cells = glyph_cells(GLYPHS[1][1])
ink = sum(1 for x, y in eur_cells if px(frame, x, y)[0] > 200)
assert ink == len(eur_cells), f"EUR glyph should render fully (ink {ink}/{len(eur_cells)})"
print("glyph alternation OK (EU -> EUR with blue blink between)")

# --- facts mode: gold text on the system ground, scrolls, hot-reloads -----------
tmp = Path("/tmp/opencode/euro-facts-test.json")
tmp.write_text(json.dumps([{"headline": "THE WEB WAS BORN AT CERN"},
                           {"headline": "MP3 IS A GERMAN INVENTION"}]))
game.cfg["facts_path"] = str(tmp)
game._load_facts()
game._build_columns()
game.on_press(1, 1)                              # -> facts mode
game.offset = 10.0                               # mid-scroll, text in the band
frame = loop.tick()
assert game.cfg["modes"][game.mode_i] == "facts"
text_px = sum(1 for y in range(3, 8) for x in range(W) if px(frame, x, y) == GOLD)
assert text_px > 4, f"facts should render gold text in the band (got {text_px})"
ground = sum(1 for y in range(H) for x in range(W) if px(frame, x, y) == GROUND_BLUE)
assert ground > 90, f"the rest should stay on the system ground ({ground})"
a = loop.tick()
game.update(0.5)                                 # advance the scroll
b = loop.tick()
assert a != b, "the ticker should scroll"
tmp.write_text(json.dumps([{"headline": "BLUE TOOTH IS A DANISH KING"}]))
game.facts_mtime = 0.0                           # force the reload path
game.next_check = 0.0                            # and the 1s check gate
game.update(1.0)
assert "BLUE TOOTH IS A DANISH KING" in game.facts_text, "facts hot-reload"
print("facts mode OK (gold on system ground, scrolls, hot-reloads)")

# --- spin mode: gold comet orbiting the ground ----------------------------------
game.on_press(1, 1)                              # -> spin mode
frame = loop.tick()
gold_px = [(x, y) for y in range(H) for x in range(W) if px(frame, x, y)[0] > 200]
assert len(gold_px) == 1, f"exactly one bright leader star (got {len(gold_px)}) at {gold_px}"
scr = Screen()
game.draw_spin(scr, 3.0)
bright = [(x, y) for y in range(H) for x in range(W) if px(scr.to_hex(), x, y)[0] > 200]
assert gold_px[0] not in bright, "the leader star should orbit"
trail = sum(1 for y in range(H) for x in range(W)
            if 30 < px(scr.to_hex(), x, y)[0] < 200 and px(scr.to_hex(), x, y)[2] < 80)
assert trail >= 10, f"the 11 trailing stars should follow dimmer ({trail})"
print("spin mode OK (leader + comet trail)")

# --- mode cycling wraps -----------------------------------------------------------
game.on_press(1, 1)                              # -> back to mark
assert game.cfg["modes"][game.mode_i] == "mark"
frame = loop.tick()
print(f"mark frame ({GLYPHS[game.glyph_i][0]}):\n" + ascii_frame(frame))
print("all euromaxxing tests OK")