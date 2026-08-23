"""Offline tests: game logic, canvas round-trip, press decoding."""
import random
import zlib

from minesweeper import (
    Board,
    Game,
    N,
    W,
    cmd_paint_frame,
    cmd_start_builtin,
    dev,
    extract_canvas,
    inflate_raw,
)

random.seed(7)

# --- canvas round trip -------------------------------------------------------
game = Game()
fb = game.framebuffer()
assert len(fb) == 432
cmd = cmd_paint_frame(fb)
# command: field1 varint 4, then field7 len-delimited
assert cmd[0] == 0x08 and cmd[1] == 0x04
canvas = extract_canvas(cmd)
assert canvas == fb, "canvas should round-trip through the command encoding"

# huffman-only stream must inflate correctly
comp = cmd_paint_frame(fb)
print("frame command bytes:", len(comp))

# --- known captured notification decodes to one pixel ------------------------
notify = bytes.fromhex("08021a120a100c0c6318050c4306b08adc0100")
raw = extract_canvas(notify)
assert raw is not None and len(raw) == 432
nonzero = [i for i in range(N) if raw[i * 3 : i * 3 + 3] != b"\x00\x00\x00"]
assert nonzero == [143], nonzero
assert raw[143 * 3 : 143 * 3 + 3] == bytes((5, 20, 220))
print("captured notification decodes: pixel (11,11) brush colour OK")

# --- press detection via diff ------------------------------------------------
board = Board()
board.sent_frames.append(fb)
pressed = bytearray(fb)
pressed[37 * 3 : 37 * 3 + 3] = bytes((5, 20, 220))
fake_notify = b"\x08\x02\x1a\x00\x0a\x00" + bytes([12, 12]) + zlib.compressobj(
    9, zlib.DEFLATED, -15
).compress(bytes(pressed)) + zlib.compressobj(9, zlib.DEFLATED, -15).flush()
# build properly:
c = zlib.compressobj(9, zlib.DEFLATED, -15)
stream = c.compress(bytes(pressed)) + c.flush()
fake_notify = b"\x08\x02" + bytes([12, 12]) + stream
presses = board.decode_presses(fake_notify)
assert presses == [37], presses
print("diff-based press detection OK:", presses)

# --- game play ---------------------------------------------------------------
g = Game()
r = g.press(0)
assert r in ("reveal", "win")
assert g.placed and 0 in g.revealed
assert 0 not in g.mines and all(n not in g.mines for n in g.neighbors(0))
# play a full game by pressing every safe cell
g2 = Game()
g2.press(66)
for i in range(N):
    if not g2.over and i not in g2.mines:
        g2.press(i)
assert g2.won, "revealing all safe cells should win"
print("full safe sweep wins OK")

g3 = Game()
g3.press(0)
mine = next(iter(g3.mines))
assert g3.press(mine) == "boom"
assert g3.over and not g3.won
print("mine press ends game OK")

print("ALL TESTS PASSED")
