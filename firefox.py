"""Switch Firefox tabs for ArcadeOS pads.

Brings Firefox to the front and posts Cmd-Option-Left/Right (its default
next/previous-tab shortcut). The key event is posted directly with Quartz
CGEvent from this process — NOT via osascript/System Events — because TCC
attributes System-Events keystrokes to `osascript` (which is not granted),
whereas a CGEvent posted here is attributed to the host app bundle
(ArcadeMinesweeper.app), which holds the Accessibility grant.
"""

from __future__ import annotations

import subprocess
import threading
import time

import Quartz

# virtual key codes
_KEY_RIGHT = 0x7C   # next tab
_KEY_LEFT = 0x7B    # previous tab
_FLAGS = Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskAlternate


def _post_key(keycode: int) -> None:
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(src, keycode, down)
        Quartz.CGEventSetFlags(ev, _FLAGS)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def _run(delta: int) -> None:
    try:
        subprocess.run(["open", "-a", "Firefox"], timeout=3)   # bring it forward
        time.sleep(0.12)                                       # let focus settle
        _post_key(_KEY_RIGHT if delta > 0 else _KEY_LEFT)
        print(f"[{time.strftime('%H:%M:%S')}] firefox tab {'next' if delta > 0 else 'prev'}",
              flush=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] firefox tab switch error: {e}", flush=True)


def switch_tab(delta: int) -> None:
    """delta +1 = next tab, -1 = previous tab. Runs off-thread (non-blocking)."""
    threading.Thread(target=_run, args=(delta,), daemon=True).start()
