import os, sys, time, threading
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
import Quartz
from CoreFoundation import CFRunLoopAddSource, CFRunLoopGetCurrent, CFRunLoopRun, kCFRunLoopCommonModes

counts = {"moved":0, "tablet_point":0, "tablet_prox":0, "dragged":0, "max_pressure":0.0, "samples":[]}
SUB = Quartz.kCGMouseEventSubtype

def cb(proxy, etype, event, refcon):
    try:
        sub = Quartz.CGEventGetIntegerValueField(event, SUB)
        if etype == Quartz.kCGEventMouseMoved: counts["moved"] += 1
        if etype == Quartz.kCGEventLeftMouseDragged: counts["dragged"] += 1
        if sub == Quartz.kCGEventMouseSubtypeTabletProximity: counts["tablet_prox"] += 1
        if sub == Quartz.kCGEventMouseSubtypeTabletPoint:
            counts["tablet_point"] += 1
            p = Quartz.CGEventGetDoubleValueField(event, Quartz.kCGTabletEventPointPressure)
            counts["max_pressure"] = max(counts["max_pressure"], p)
        # also try generic mouse pressure
        mp = Quartz.CGEventGetDoubleValueField(event, Quartz.kCGMouseEventPressure)
        if mp > 0 and len(counts["samples"]) < 5:
            counts["samples"].append(round(mp,3))
    except Exception as e:
        pass
    return event

mask = 0
for et in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDragged,
           Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
    mask |= Quartz.CGEventMaskBit(et)
tap = Quartz.CGEventTapCreate(Quartz.kCGHIDEventTap, Quartz.kCGHeadInsertEventTap,
                              Quartz.kCGEventTapOptionListenOnly, mask, cb, None)
print("tap:", bool(tap), flush=True)
if tap:
    src = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), src, kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(tap, True)
    def stopper():
        time.sleep(25)
        print("RESULT:", counts, flush=True)
        os._exit(0)
    threading.Thread(target=stopper, daemon=True).start()
    CFRunLoopRun()
