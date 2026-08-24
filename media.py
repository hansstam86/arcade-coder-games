"""macOS media-key control (play/pause, next, previous) for ArcadeOS.

Posts NSSystemDefined media keys with Quartz CGEvent from THIS process, so the
event is attributed to the host app bundle (ArcadeMinesweeper.app) — which
holds the Accessibility grant — rather than to a helper. Any app that owns the
system "now playing" role (YouTube Music in a browser, Music, Spotify, ...)
responds, even in the background.
"""

from __future__ import annotations

import Quartz
from AppKit import NSEvent

NX_PLAY = 16
NX_NEXT = 17
NX_PREV = 18
NX_FAST = 19      # seek forward (some players)
NX_REWIND = 20    # seek backward


def _post(key: int) -> None:
    for down in (True, False):
        flags = 0xA00 if down else 0xB00
        data1 = (key << 16) | ((0xA if down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            14,             # NSSystemDefined
            (0.0, 0.0),
            flags,
            0.0, 0, None,
            8,              # subtype for media keys
            data1,
            -1,
        )
        cg = ev.CGEvent()
        if cg is not None:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, cg)


def play_pause() -> None:
    _post(NX_PLAY)


def next_track() -> None:
    _post(NX_NEXT)


def prev_track() -> None:
    _post(NX_PREV)


def seek_forward() -> None:
    _post(NX_FAST)


def seek_back() -> None:
    _post(NX_REWIND)
