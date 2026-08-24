#!/usr/bin/env python3
"""Bridge for the atech ESP32-S3 sensor kit → the rest of the platform.

Reads newline-delimited JSON from the atech board's USB serial port and
publishes the latest sensor state. Tolerant of key naming so it works with
whatever atech's generated firmware emits — it looks for, in order:

  accel x: ax | accel_x | accelX | x
  accel y: ay | accel_y | accelY | y
  accel z: az | accel_z | accelZ | z
  distance: dist | distance | range | tof
  button:  btn | button | b
  knob:    knob | pot | dial | k

Values are exposed raw plus a convenient tilt() helper (dx, dy in -1..1).

  python -m atech            # print live sensor readings (plug the board in)
  python -m atech --sim      # emit fake data (no hardware) for development
"""

from __future__ import annotations

import json
import glob
import threading
import time


ACCEL_KEYS = {"x": ("ax", "accel_x", "accelX", "x"),
              "y": ("ay", "accel_y", "accelY", "y"),
              "z": ("az", "accel_z", "accelZ", "z")}
DIST_KEYS = ("dist", "distance", "range", "tof")
BTN_KEYS = ("btn", "button", "b")
KNOB_KEYS = ("knob", "pot", "dial", "k")


def _pick(d: dict, keys, default=0.0):
    for k in keys:
        if k in d:
            return d[k]
    return default


def find_port() -> str | None:
    ports = [p for p in glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
             if "K-50" not in p and "YX81" not in p]
    return ports[0] if ports else None


class Atech:
    """Background serial reader publishing the latest sensor sample."""

    def __init__(self, port: str | None = None, baud: int = 115200) -> None:
        self.port = port
        self.baud = baud
        self.ax = self.ay = 0.0
        self.az = 1.0
        self.dist = 0.0
        self.btn = 0
        self.knob = 0.0
        self.connected = False
        self.last_t = 0.0
        self.raw = None
        self._stop = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _ingest(self, obj: dict) -> None:
        with self._lock:
            self.ax = float(_pick(obj, ACCEL_KEYS["x"], self.ax))
            self.ay = float(_pick(obj, ACCEL_KEYS["y"], self.ay))
            self.az = float(_pick(obj, ACCEL_KEYS["z"], self.az))
            self.dist = float(_pick(obj, DIST_KEYS, self.dist))
            self.btn = int(_pick(obj, BTN_KEYS, self.btn))
            self.knob = float(_pick(obj, KNOB_KEYS, self.knob))
            self.raw = obj
            self.last_t = time.monotonic()

    def _run(self) -> None:
        import serial

        while not self._stop:
            port = self.port or find_port()
            if port is None:
                self.connected = False
                time.sleep(1.0)
                continue
            try:
                ser = serial.Serial(port, self.baud, timeout=1.0)
            except Exception:
                self.connected = False
                time.sleep(2.0)
                continue
            self.connected = True
            leftover = b""
            while not self._stop:
                try:
                    chunk = ser.read(256)
                except Exception:
                    break
                if not chunk:
                    if time.monotonic() - self.last_t > 3:
                        pass  # still connected, just quiet
                    continue
                leftover += chunk
                while b"\n" in leftover:
                    line, leftover = leftover.split(b"\n", 1)
                    line = line.strip()
                    if not line or not line.startswith(b"{"):
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8", "replace"))
                        if isinstance(obj, dict):
                            self._ingest(obj)
                    except Exception:
                        continue
            try:
                ser.close()
            except Exception:
                pass
            self.connected = False

    # -- convenience --------------------------------------------------------
    def fresh(self, within: float = 1.0) -> bool:
        return self.connected and (time.monotonic() - self.last_t) < within

    def tilt(self) -> tuple[float, float]:
        """Board tilt as (dx, dy) each in ~-1..1, from the accelerometer.

        Assumes az is 'up' at rest. Works whether accel is in g or m/s^2
        because it normalizes by the vector magnitude.
        """
        with self._lock:
            ax, ay, az = self.ax, self.ay, self.az
        mag = (ax * ax + ay * ay + az * az) ** 0.5 or 1.0
        return max(-1.0, min(1.0, ax / mag)), max(-1.0, min(1.0, ay / mag))

    def snapshot(self) -> dict:
        with self._lock:
            return {"ax": self.ax, "ay": self.ay, "az": self.az,
                    "dist": self.dist, "btn": self.btn, "knob": self.knob,
                    "connected": self.connected, "fresh": self.fresh()}

    def stop(self) -> None:
        self._stop = True


class SimAtech(Atech):
    """Fake sensor source for development without hardware."""

    def __init__(self) -> None:
        self._stop = False
        self.ax = self.ay = 0.0
        self.az = 1.0
        self.dist = 200.0
        self.btn = 0
        self.knob = 0.5
        self.connected = True
        self.last_t = time.monotonic()
        self.raw = {}
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._sim, daemon=True)
        self._thread.start()

    def _sim(self) -> None:
        import math

        t0 = time.monotonic()
        while not self._stop:
            t = time.monotonic() - t0
            self._ingest({
                "ax": 0.6 * math.sin(t * 0.7),
                "ay": 0.6 * math.cos(t * 0.5),
                "az": 0.8,
                "dist": 150 + 120 * (0.5 + 0.5 * math.sin(t)),
                "btn": 1 if int(t) % 4 == 0 else 0,
                "knob": 0.5 + 0.5 * math.sin(t * 0.3),
            })
            time.sleep(0.02)


if __name__ == "__main__":
    import sys

    dev = SimAtech() if "--sim" in sys.argv else Atech()
    print("port:", dev.port or find_port() or "(none — plug in the atech board)")
    try:
        while True:
            s = dev.snapshot()
            dx, dy = dev.tilt()
            print(f"conn={s['connected']} fresh={s['fresh']} "
                  f"ax={s['ax']:+.2f} ay={s['ay']:+.2f} az={s['az']:+.2f} "
                  f"tilt=({dx:+.2f},{dy:+.2f}) dist={s['dist']:.0f} "
                  f"btn={s['btn']} knob={s['knob']:.2f}", flush=True)
            time.sleep(0.25)
    except KeyboardInterrupt:
        dev.stop()
