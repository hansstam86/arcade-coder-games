"""Offline tests: studio sign cue cycling, rendering, auto-return."""
import time

from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from studio import DEFAULT, Studio


def ascii_frame(hexes: list[str]) -> str:
    """Colour-letter ASCII preview: R/G/B/Y/C/M for hues, # for white."""
    out = []
    for y in range(H):
        row = ""
        for x in range(W):
            h = hexes[y * W + x].lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            if r + g + b < 45:
                row += "."
            elif min(r, g, b) > 150:
                row += "#"
            elif r > 100 and g > 100:
                row += "Y"
            elif g > 100 and b > 100:
                row += "C"
            elif r > 100 and b > 100:
                row += "M"
            elif r > 60:
                row += "R"
            elif g > 60:
                row += "G"
            elif b > 60:
                row += "B"
            else:
                row += "o"
        out.append(row)
    return "\n".join(out)


loop = GameLoop(Studio)
g = loop.game
n = len(DEFAULT["cues"])
frames = {}

# --- every cue renders, and pressing right walks the whole deck ---------------
for i in range(n):
    for _ in range(60):                     # ~3s of frames per cue
        frame = loop.tick()
    lit = sum(1 for h in frame if h != "#000000")
    assert lit > 10, f"cue {i} ({g.cue()['text']!r}) looks blank (lit={lit})"
    frames[g.cue()["text"]] = frame
    print(f"cue {i}: {g.cue()['text']:<22} style={g.cue()['style']:<6} lit={lit}")
    loop.press(11, 5)                        # right half -> next cue

assert g.i == 0, "deck should wrap around to cue 0"

# --- ON AIR tally: red field, stacked ON/AIR in white ------------------------
frame = frames["ON AIR"]
reds = sum(
    1 for h in frame
    if (s := h.lstrip("#")) and int(s[0:2], 16) > 120 and int(s[2:4], 16) < 40 and int(s[4:6], 16) < 40
)
whites = sum(1 for h in frame if min(int(h.lstrip('#')[j:j+2], 16) for j in (0, 2, 4)) > 150)
assert reds > 80, f"ON AIR should flood the board red (red px={reds})"
assert whites > 20, f"ON AIR letters should be white (white px={whites})"
print("\nON AIR frame:\n" + ascii_frame(frame))

# --- pressing the left half goes back ----------------------------------------
loop.press(0, 5)
assert g.i == n - 1, f"left half should go back a cue, got {g.i}"

# --- APPLAUSE auto-returns to the previous cue -------------------------------
prev = g.i
g.goto(2)                                    # APPLAUSE
assert g.i == 2 and g.return_to == prev, "entering APPLAUSE should remember the previous cue"
g.return_at = time.monotonic() - 0.01         # force the timer
loop.tick()
assert g.i == prev, f"APPLAUSE should auto-return to cue {prev}, got {g.i}"

# --- scroll cues eventually put pixels in the text band -----------------------
frame = frames["COMMERCIAL BREAK"]
band = sum(1 for y in range(3, 8) for x in range(W) if frame[y * W + x].lstrip("#") != "000000")
assert band > 10, f"scrolling cue should light the text band (band px={band})"

print("\nall studio sign tests OK")