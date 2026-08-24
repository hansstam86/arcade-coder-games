"""Switch Firefox tabs for ArcadeOS pads.

Brings Firefox to the front and sends Cmd-Option-Left/Right (its default
next/previous-tab shortcut). Needs Accessibility permission for the
controlling app — macOS prompts on first use.
"""

from __future__ import annotations

import subprocess

# key code 124 = right arrow (next tab), 123 = left arrow (previous tab)
_SCRIPT = """
tell application "Firefox" to activate
delay 0.04
tell application "System Events"
    key code %d using {command down, option down}
end tell
"""


def switch_tab(delta: int) -> None:
    """delta +1 = next tab, -1 = previous tab. Runs off-thread (non-blocking)."""
    code = 124 if delta > 0 else 123
    try:
        subprocess.Popen(["osascript", "-e", _SCRIPT % code],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
