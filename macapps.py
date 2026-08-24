"""Switch between the Mac's running apps (like Cmd-Tab) for ArcadeOS pads.

Uses System Events to bring the next/previous visible app to the front, so it
cycles the whole app list (not just the last two). Needs Accessibility
permission for the controlling app — macOS prompts on first use.
"""

from __future__ import annotations

import subprocess

_SCRIPT = """
tell application "System Events"
    set visApps to (name of every process whose background only is false and visible is true)
    set n to count of visApps
    if n < 2 then return
    set frontApp to name of first process whose frontmost is true
    set idx to 1
    repeat with i from 1 to n
        if item i of visApps is frontApp then set idx to i
    end repeat
    set nextIdx to (((idx - 1) + (%d) + n) mod n) + 1
    set frontmost of process (item nextIdx of visApps) to true
end tell
"""


def switch(delta: int) -> None:
    """delta +1 = next app, -1 = previous app. Runs off-thread (non-blocking)."""
    try:
        subprocess.Popen(["osascript", "-e", _SCRIPT % delta],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
