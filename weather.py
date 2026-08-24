#!/usr/bin/env python3
"""Weather — an animated, glanceable forecast for the Arcade Coder.

The board shows an animated scene for the current conditions (clear sun/stars,
drifting clouds, falling rain or snow, lightning, fog), the temperature in the
middle, and a 12-hour forecast ribbon along the bottom row (each column an
upcoming hour, coloured cold-blue -> hot-red, tinted blue when rain is likely).

Data comes from Open-Meteo (no API key). Location is auto-detected once by IP
and cached; override it in weather.json (latitude, longitude, label). Tap the
board to toggle temperature / feels-like; it refreshes on entry and every
~15 minutes.

  python weather.py           # emulator
"""

from __future__ import annotations

import json
import math
import random
import ssl
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "weather.json"
W = H = 12

DEFAULT = {
    "latitude": None,
    "longitude": None,
    "label": "",
    "units": "c",            # "c" or "f"
    "refresh_minutes": 15,
}

FONT = {  # 3x5
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "-": ["000", "000", "111", "000", "000"],
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _wmo_category(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (71, 72, 73, 74, 75, 76, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    if 51 <= code <= 82:
        return "rain"
    return "cloudy"


def _http_json(url: str, timeout: float = 7.0):
    req = urllib.request.Request(url, headers={"User-Agent": "arcade-coder-weather"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except ssl.SSLError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode())


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_TEMP_STOPS = [
    (-15, (60, 60, 200)), (-5, (0, 120, 255)), (5, (0, 200, 220)),
    (12, (0, 200, 90)), (20, (230, 220, 0)), (28, (255, 120, 0)),
    (38, (255, 0, 0)),
]


def temp_color(t: float):
    if t <= _TEMP_STOPS[0][0]:
        return _TEMP_STOPS[0][1]
    for (t0, c0), (t1, c1) in zip(_TEMP_STOPS, _TEMP_STOPS[1:]):
        if t <= t1:
            return _lerp(c0, c1, (t - t0) / (t1 - t0))
    return _TEMP_STOPS[-1][1]


class Weather(Game):
    fps = 12

    def start(self):
        self.cfg = dict(DEFAULT)
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.data = self.cfg.get("cache")     # last good reading, if any
        self.status = "loading" if not self.data else "ok"
        self.show_feels = False
        self.busy = False
        # animation state
        self.rain = [[random.uniform(0, W), random.uniform(-H, 0),
                      random.uniform(9, 16)] for _ in range(14)]
        self.snow = [[random.uniform(0, W), random.uniform(-H, 0),
                      random.uniform(0.6, 1.4), random.uniform(2.5, 5)] for _ in range(16)]
        self.stars = [(random.randrange(W), random.randrange(6),
                       random.uniform(0, 6.3)) for _ in range(10)]
        self.lightning = 0.0
        self.last_anim = time.monotonic()
        self._fetch_async()
        self._next_refresh = time.monotonic() + self.cfg["refresh_minutes"] * 60

    # -- data ----------------------------------------------------------------
    def _fetch_async(self) -> None:
        threading.Thread(target=self._fetch, daemon=True).start()

    def _locate(self):
        lat, lon = self.cfg.get("latitude"), self.cfg.get("longitude")
        label = self.cfg.get("label", "")
        if lat is None or lon is None:
            try:
                geo = _http_json("http://ip-api.com/json/?fields=lat,lon,city")
                lat, lon = geo["lat"], geo["lon"]
                label = label or geo.get("city", "")
            except Exception:
                return None, None, label
        return lat, lon, label

    def _fetch(self) -> None:
        try:
            lat, lon, label = self._locate()
            if lat is None:
                self.status = "offline"
                return
            url = ("https://api.open-meteo.com/v1/forecast"
                   f"?latitude={lat}&longitude={lon}"
                   "&current=temperature_2m,apparent_temperature,weather_code,is_day"
                   "&hourly=temperature_2m,weather_code,precipitation_probability"
                   "&forecast_days=2&timezone=auto")
            js = _http_json(url)
            cur = js["current"]
            hourly = js["hourly"]
            times = hourly["time"]
            now_t = cur["time"]
            start = next((i for i, t in enumerate(times) if t >= now_t), 0)
            nxt = list(range(start, min(start + 12, len(times))))
            data = {
                "temp": cur["temperature_2m"],
                "feels": cur["apparent_temperature"],
                "code": int(cur["weather_code"]),
                "is_day": int(cur.get("is_day", 1)),
                "label": label,
                "hours": [{"t": hourly["temperature_2m"][i],
                           "p": hourly["precipitation_probability"][i] or 0}
                          for i in nxt],
                "at": time.time(),
            }
            self.data = data
            self.status = "ok"
            self.cfg["cache"] = data
            try:
                CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2) + "\n")
            except Exception:
                pass
            log(f"weather: {label or 'here'} {round(data['temp'])}° "
                f"{_wmo_category(data['code'])}")
        except Exception as e:
            if not self.data:
                self.status = "offline"
            log(f"weather fetch failed: {e}")

    # -- input ---------------------------------------------------------------
    def on_press(self, x, y):
        self.show_feels = not self.show_feels
        self._fetch_async()

    def update(self, dt):
        now = time.monotonic()
        if now >= self._next_refresh:
            self._next_refresh = now + self.cfg["refresh_minutes"] * 60
            self._fetch_async()

    # -- scene ---------------------------------------------------------------
    def _to_f(self, c):
        return c * 9 / 5 + 32 if self.cfg.get("units") == "f" else c

    def _scene(self, buf, cat, is_day, now, dt):
        if cat in ("clear", "partly") and is_day:
            for i in range(144):
                y = i // W
                buf[i] = _lerp((60, 150, 255), (170, 210, 255), y / H)
            self._sun(buf, now, partly=(cat == "partly"))
        elif cat in ("clear", "partly"):
            for i in range(144):
                buf[i] = (4, 6, 26)
            for sx, sy, ph in self.stars:
                v = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(now * 1.6 + ph))
                buf[sy * W + sx] = (int(200 * v), int(200 * v), int(150 * v))
            self._moon(buf)
            if cat == "partly":
                self._clouds(buf, now, (70, 70, 90))
        elif cat == "cloudy":
            base = (120, 130, 145) if is_day else (30, 34, 46)
            for i in range(144):
                buf[i] = base
            self._clouds(buf, now, (185, 195, 210) if is_day else (60, 66, 84))
        elif cat == "fog":
            for i in range(144):
                y = i // W
                band = 0.5 + 0.5 * math.sin(y * 0.9 + now * 0.8)
                g = int(80 + 90 * band)
                buf[i] = (g, g, int(g * 1.05))
        elif cat == "rain":
            base = (60, 70, 90) if is_day else (20, 26, 40)
            for i in range(144):
                buf[i] = base
            self._clouds(buf, now, (90, 100, 120))
            self._rain(buf, dt)
        elif cat == "snow":
            base = (110, 120, 140) if is_day else (26, 32, 48)
            for i in range(144):
                buf[i] = base
            self._snow(buf, dt)
        elif cat == "thunder":
            flash = now < self.lightning
            base = (200, 200, 220) if flash else (26, 28, 44)
            for i in range(144):
                buf[i] = base
            self._clouds(buf, now, (70, 74, 96))
            self._rain(buf, dt)
            if random.random() < 0.02 and not flash:
                self.lightning = now + 0.12
        else:
            for i in range(144):
                buf[i] = (40, 44, 60)

    def _sun(self, buf, now, partly=False):
        cx, cy, r = 6.0, 4.5, 2.2
        for y in range(H):
            for x in range(W):
                d = math.hypot(x - cx, y - cy)
                if d <= r:
                    buf[y * W + x] = (255, 235, 60)
                elif d <= r + 1.2:
                    v = 0.5 + 0.5 * math.sin(now * 3 + math.atan2(y - cy, x - cx) * 3)
                    buf[y * W + x] = _lerp(buf[y * W + x], (255, 210, 40), 0.5 * v)
        if partly:
            self._clouds(buf, now, (235, 240, 250))

    def _moon(self, buf):
        cx, cy, r = 7.5, 3.5, 1.8
        for y in range(H):
            for x in range(W):
                if math.hypot(x - cx, y - cy) <= r:
                    buf[y * W + x] = (225, 225, 210)
                if math.hypot(x - (cx + 1.1), y - cy) <= r:
                    buf[y * W + x] = (4, 6, 26)     # crescent bite

    def _clouds(self, buf, now, color):
        for k, speed in ((0, 0.5), (1, 0.32)):
            cxf = (now * speed + k * 6) % (W + 6) - 3
            cy = 3 + k * 3
            for dx, dy in [(0, 0), (1, 0), (2, 0), (-1, 0), (0, -1), (1, -1),
                           (-1, 1), (0, 1), (1, 1), (2, 1)]:
                x, y = int(cxf) + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    buf[y * W + x] = color

    def _rain(self, buf, dt):
        for d in self.rain:
            d[1] += d[2] * dt
            if d[1] >= H:
                d[0], d[1] = random.uniform(0, W), random.uniform(-3, -0.2)
            x, y = int(d[0]) % W, int(d[1])
            if 0 <= y < H:
                buf[y * W + x] = (120, 170, 255)
                if y + 1 < H:
                    buf[(y + 1) * W + x] = (70, 110, 210)

    def _snow(self, buf, dt):
        for f in self.snow:
            f[1] += f[3] * dt
            f[0] += math.sin(f[1] * 0.6) * f[2] * dt
            if f[1] >= H:
                f[0], f[1] = random.uniform(0, W), random.uniform(-3, -0.2)
            x, y = int(f[0]) % W, int(f[1])
            if 0 <= y < H:
                buf[y * W + x] = (240, 245, 255)

    # -- text + ribbon -------------------------------------------------------
    def _draw_text(self, buf, text, color, y0, dim_plate=True):
        widths = len(text) * 3 + (len(text) - 1)
        x0 = (W - widths) // 2
        if dim_plate:
            for yy in range(y0 - 1, y0 + 6):
                for xx in range(W):
                    if 0 <= yy < H:
                        buf[yy * W + xx] = tuple(c // 4 for c in buf[yy * W + xx])
        cx = x0
        for ch in text:
            for dy, row in enumerate(FONT.get(ch, FONT["0"])):
                for dx, bit in enumerate(row):
                    if bit == "1" and 0 <= cx + dx < W:
                        buf[(y0 + dy) * W + cx + dx] = color
            cx += 4

    def _ribbon(self, buf, hours):
        for i in range(min(12, len(hours))):
            h = hours[i]
            c = temp_color(h["t"])                 # colour scale is in Celsius
            if h["p"] >= 50:
                c = _lerp(c, (60, 120, 255), 0.5)
            if i == 0:
                c = tuple(min(255, int(v * 1.3) + 20) for v in c)
            buf[11 * W + i] = c

    def draw(self, screen):
        now = time.monotonic()
        dt = min(0.2, now - self.last_anim)
        self.last_anim = now
        buf = [(0, 0, 0)] * 144

        if not self.data:
            # loading = pulsing teal sweep; offline = dim red
            if self.status == "offline":
                v = int(30 + 20 * math.sin(now * 2))
                for i in range(144):
                    buf[i] = (60 + v, 0, 0)
            else:
                for y in range(H):
                    for x in range(W):
                        v = 0.5 + 0.5 * math.sin(now * 3 - (x + y) * 0.4)
                        buf[y * W + x] = (0, int(90 * v), int(150 * v))
            screen.px = buf
            return

        d = self.data
        cat = _wmo_category(d["code"])
        self._scene(buf, cat, d["is_day"], now, dt)
        val = d["feels"] if self.show_feels else d["temp"]
        val = round(self._to_f(val))
        color = (255, 200, 120) if self.show_feels else (255, 255, 255)
        self._draw_text(buf, f"{val}", color, 3)
        self._ribbon(buf, d.get("hours", []))
        screen.px = buf


if __name__ == "__main__":
    run(Weather)
