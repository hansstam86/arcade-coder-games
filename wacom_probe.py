import os, sys, time
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
sys.path.insert(0, ".")
import wacom
st = wacom.start()
print("wacom probe: move/press the pen now (25s)", flush=True)
t0 = time.monotonic(); last = None; seen = 0
while time.monotonic() - t0 < 25:
    if st.error:
        print("ERROR:", st.error, flush=True); break
    snap = st.snapshot()
    if snap != last and (snap[3] or snap[2] > 0):
        x, y, p, contact, eraser = snap
        print(f"pen x={x:.2f} y={y:.2f} p={p:.2f} {'ERASE' if eraser else 'draw'} {'DOWN' if contact else ''}", flush=True)
        last = snap; seen += 1
    time.sleep(0.05)
print(f"done — available={st.available} events={seen} error={st.error}", flush=True)
