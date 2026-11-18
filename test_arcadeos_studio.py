"""Offline tests: studio sign registered as an ArcadeOS app (runs on Linux)."""
import arcadeos
from arcadecoder import H, W
from arcadecoder.runner import GameLoop
from arcadeos import ArcadeOS

# --- registry ---------------------------------------------------------------
names = [n for n, _c, _i, _p in arcadeos.APPS]
assert "studio" in names, "studio must be registered in ArcadeOS APPS"
assert arcadeos.APP_BY_NAME["studio"].__name__ == "Studio"
assert arcadeos.macapps is None and arcadeos.firefox is None  # linux: guarded imports

# --- home grid: navigate to the studio icon ----------------------------------
loop = GameLoop(ArcadeOS)
os_game = loop.game
placed = os_game._placed()
idx = [p[0] for p in placed].index("studio")
if len(placed) <= len(arcadeos.HOME_SLOTS):
    slot = arcadeos.HOME_SLOTS[idx]
else:
    per = len(arcadeos.HOME_SLOTS) - 1
    os_game.home_page = idx // per
    slot = {n: (bx, by) for (bx, by), n, _c, _i in os_game._active()}["studio"]
print(f"studio icon on page {os_game.home_page} at {slot} (app #{idx} of {len(placed)})")

frame = loop.tick()
assert sum(1 for h in frame if h != "#000000") > 10, "home grid should render"
loop.press(*slot)

# --- entered: app runs, is busy (never auto-ambient), shows ON AIR ------------
assert os_game.app_name == "studio", f"should be in studio, got {os_game.app_name}"
assert getattr(os_game.app, "busy", False) is True, "the sign must be busy (no auto-ambient)"
for _ in range(60):
    frame = loop.tick()
lit = sum(1 for h in frame if h != "#000000")
assert lit > 100, f"ON AIR cue should light the board (lit={lit})"
reds = sum(
    1 for h in frame
    if (s := h.lstrip("#")) and int(s[0:2], 16) > 120 and int(s[2:4], 16) < 40 and int(s[4:6], 16) < 40
)
assert reds > 80, f"ON AIR cue should flood the board red (red px={reds})"

# --- inside the OS: a right-half press still cycles the cue -------------------
loop.press(10, 6)
loop.tick()
assert os_game.app.cue()["text"] == "STAND BY", "right-half press should advance the cue"

# --- home pad returns to the home grid ----------------------------------------
loop.press(6, 0)
loop.tick()
assert os_game.app_name == "home", "home pad should leave the app"

print("all ArcadeOS studio wiring tests OK")