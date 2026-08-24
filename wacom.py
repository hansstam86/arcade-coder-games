#!/usr/bin/env python3
"""Read a Wacom tablet's pen (position + pressure + eraser) on macOS.

Uses a passive Quartz event tap on the HID event stream, so it needs no
focused window — but the app must have Input Monitoring permission (System
Settings > Privacy & Security > Input Monitoring > ArcadeMinesweeper).

The tap runs in a background thread with its own CFRunLoop; the latest pen
state is published on a shared PenState. Position is the global cursor
(the Intuos maps its surface to the whole screen), normalized 0..1 over the
main display, which callers map onto the 12x12 grid.

Run directly to probe:  (inside the app bundle) prints pen events for 20s.
"""

from __future__ import annotations

import threading
import time

_TAP = None


class PenState:
    def __init__(self) -> None:
        self.x = 0.5              # 0..1 across the main display
        self.y = 0.5
        self.pressure = 0.0       # 0..1
        self.contact = False      # pressure > 0
        self.eraser = False       # eraser end in use
        self.last_t = 0.0
        self.available = False    # tap installed successfully
        self.error = None
        self.lock = threading.Lock()

    def update(self, x, y, pressure, eraser):
        with self.lock:
            self.x, self.y = x, y
            self.pressure = pressure
            self.contact = pressure > 0.001
            self.eraser = eraser
            self.last_t = time.monotonic()

    def snapshot(self):
        with self.lock:
            return (self.x, self.y, self.pressure, self.contact, self.eraser)


def start(state: PenState | None = None) -> PenState:
    """Start the event tap in a background thread. Returns the PenState."""
    global _TAP
    state = state or PenState()
    if _TAP is not None:
        return state

    def run():
        import Quartz
        from CoreFoundation import (CFRunLoopAddSource, CFRunLoopGetCurrent,
                                    CFRunLoopRun, kCFRunLoopCommonModes)

        w = h = 1.0
        main = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        w = max(1.0, main.size.width)
        h = max(1.0, main.size.height)

        SUBTYPE = Quartz.kCGMouseEventSubtype
        TABLET_POINT = Quartz.kCGEventMouseSubtypeTabletPoint
        TABLET_PROX = Quartz.kCGEventMouseSubtypeTabletProximity

        mask = 0
        for et in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDragged,
                   Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp,
                   Quartz.kCGEventRightMouseDragged, Quartz.kCGEventTabletPointer,
                   Quartz.kCGEventTabletProximity):
            mask |= Quartz.CGEventMaskBit(et)

        eraser_flag = {"on": False}

        def callback(proxy, etype, event, refcon):
            try:
                if etype in (Quartz.kCGEventTabletProximity,) or \
                   Quartz.CGEventGetIntegerValueField(event, SUBTYPE) == TABLET_PROX:
                    ptype = Quartz.CGEventGetIntegerValueField(
                        event, Quartz.kCGTabletProximityEventPointerType)
                    eraser_flag["on"] = (ptype == 3)  # 3 = eraser
                    return event
                subtype = Quartz.CGEventGetIntegerValueField(event, SUBTYPE)
                if subtype != TABLET_POINT and etype != Quartz.kCGEventTabletPointer:
                    return event  # not a tablet event (e.g. trackpad) — ignore
                loc = Quartz.CGEventGetLocation(event)
                pressure = Quartz.CGEventGetDoubleValueField(
                    event, Quartz.kCGTabletEventPointPressure)
                state.update(min(1.0, max(0.0, loc.x / w)),
                             min(1.0, max(0.0, loc.y / h)),
                             float(pressure), eraser_flag["on"])
            except Exception:
                pass
            return event

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGHIDEventTap, Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly, mask, callback, None)
        if not tap:
            state.error = ("event tap denied — grant Input Monitoring to "
                           "ArcadeMinesweeper in System Settings")
            return
        src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), src, kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        state.available = True
        CFRunLoopRun()

    _TAP = threading.Thread(target=run, daemon=True)
    _TAP.start()
    return state


if __name__ == "__main__":
    st = start()
    print("probing Wacom pen for 20s — hover and press the pen on the tablet")
    t0 = time.monotonic()
    last = None
    while time.monotonic() - t0 < 20:
        if st.error:
            print("ERROR:", st.error)
            break
        snap = st.snapshot()
        if snap != last and (snap[3] or snap[2] > 0):
            x, y, p, contact, eraser = snap
            print(f"pen x={x:.2f} y={y:.2f} pressure={p:.2f} "
                  f"{'ERASE' if eraser else 'draw '} {'DOWN' if contact else '    '}")
            last = snap
        time.sleep(0.05)
    print("available:", st.available, "error:", st.error)
