"""Notification service for ArcadeOS: see alerts on the board, hear them on
the EP-133.

Sources:
  1. macOS Notification Center database (best effort — grant the app bundle
     Full Disk Access in System Settings if the status shows no access)
  2. webhook: POST http://127.0.0.1:7760/notify {"app": "...", "title": "..."}

Rules live in notify.json and are edited in the webapp at
http://127.0.0.1:7760 — match by app/title substring; each rule has a colour,
an overlay style (border / flash / corner), and an EP-133 note to play.
"""

from __future__ import annotations

import json
import math
import plistlib
import queue
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deck_web import _origin_ok

PORT = 7760
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "notify.json"
EDITOR = ROOT / "notify_editor.html"
NC_DB = Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db"
PORT_CONTAINS = ["EP-133", "EP133", "K.O", "KO II"]

DEFAULT = {
    # show EVERY notification on the board (scroll its text), not only matches
    "show_all": True,
    "default": {"color": [0, 150, 255], "style": "border", "note": 40,
                "velocity": 100, "channel": 0, "duration": 2.5, "cooldown": 3,
                "marquee": True},
    "rules": [
        {"name": "slack", "app_contains": "slack", "title_contains": "",
         "color": [240, 120, 0], "style": "border", "note": 39,
         "velocity": 110, "channel": 0, "duration": 2.5, "cooldown": 4,
         "marquee": True, "enabled": True},
        {"name": "mail", "app_contains": "mail", "title_contains": "",
         "color": [0, 90, 240], "style": "corner", "note": 37,
         "velocity": 100, "channel": 0, "duration": 2.0, "cooldown": 8,
         "marquee": True, "enabled": True},
    ]
}

# friendly names for common macOS notification source bundle ids
APP_NAMES = {
    "slack": "SLACK", "mail": "MAIL", "messages": "MESSAGES", "imessage": "MESSAGES",
    "calendar": "CALENDAR", "ical": "CALENDAR", "reminders": "REMINDERS", "whatsapp": "WHATSAPP",
    "telegram": "TELEGRAM", "discord": "DISCORD", "zoom": "ZOOM", "teams": "TEAMS",
    "outlook": "OUTLOOK", "spotify": "SPOTIFY", "music": "MUSIC", "facetime": "FACETIME",
    "safari": "SAFARI", "chrome": "CHROME", "notes": "NOTES", "photos": "PHOTOS",
}


def friendly_app(app: str) -> str:
    low = (app or "").lower()
    for key, name in APP_NAMES.items():
        if key in low:
            return name
    tail = low.replace("com.", "").split(".")[-1] or low
    return tail.upper()[:12] if tail else "ALERT"


# recognisable brand-ish colours for common apps; everything else gets a
# stable colour derived from its name so each source looks distinct.
APP_COLORS = {
    "SLACK": [240, 120, 0], "MAIL": [0, 90, 240], "MESSAGES": [0, 200, 60],
    "CALENDAR": [220, 0, 40], "REMINDERS": [255, 140, 0], "WHATSAPP": [0, 200, 90],
    "TELEGRAM": [0, 160, 230], "DISCORD": [110, 100, 240], "ZOOM": [0, 120, 255],
    "TEAMS": [90, 80, 220], "OUTLOOK": [0, 100, 210], "SPOTIFY": [0, 210, 90],
    "MUSIC": [250, 60, 90], "FACETIME": [0, 200, 70], "NOTES": [230, 200, 0],
}


def app_color(app: str) -> list[int]:
    import colorsys

    name = friendly_app(app)
    if name in APP_COLORS:
        return list(APP_COLORS[name])
    h = (sum(ord(c) * (i + 1) for i, c in enumerate(name)) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return [int(r * 255), int(g * 255), int(b * 255)]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class NotifyService:
    def __init__(self) -> None:
        self.cfg = dict(DEFAULT)
        if CONFIG.exists():
            try:
                self.cfg.update(json.loads(CONFIG.read_text()))
            except Exception:
                pass
        else:
            CONFIG.write_text(json.dumps(DEFAULT, indent=2) + "\n")
        self.overlays: list[tuple[dict, float]] = []      # (rule, t0)
        self.last_fired: dict[str, float] = {}
        self.recent: list[dict] = []                      # last notifications seen
        self.nc_status = "starting"
        self.port = None
        self.next_port_try = 0.0
        self.pending_off: list[tuple[float, int, int]] = []
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.on_marquee = None            # legacy: callback(text)
        self.on_notification = None       # callback(app, title, body, color)
        self.lock = threading.Lock()
        threading.Thread(target=self._nc_poller, daemon=True).start()

    # -- rule engine ---------------------------------------------------------
    def _notify_ui(self, app: str, title: str, body: str, color) -> None:
        """Prefer the on-board notification center; fall back to a scroll."""
        if self.on_notification is not None:
            try:
                self.on_notification(friendly_app(app), title, body, color)
                return
            except Exception:
                pass
        if self.on_marquee is not None:
            parts = [p.strip() for p in (title, body) if p and p.strip()]
            try:
                self.on_marquee(friendly_app(app) + ("  " + " ".join(parts) if parts else ""))
            except Exception:
                pass

    def handle(self, app: str, title: str, body: str = "") -> str | None:
        now = time.monotonic()
        with self.lock:
            self.recent = ([{"app": app, "title": title[:60], "t": time.time()}]
                           + self.recent)[:8]
        hay_app, hay_title = app.lower(), (title + " " + body).lower()
        for rule in self.cfg["rules"]:
            if not rule.get("enabled", True):
                continue
            if rule.get("app_contains") and rule["app_contains"].lower() not in hay_app:
                continue
            if rule.get("title_contains") and rule["title_contains"].lower() not in hay_title:
                continue
            if now - self.last_fired.get(rule["name"], -999) < rule.get("cooldown", 4):
                return rule["name"]
            self.last_fired[rule["name"]] = now
            self.fire(rule)
            if rule.get("marquee") or self.cfg.get("show_all", True):
                self._notify_ui(app, title, body, rule.get("color", [0, 150, 255]))
            log(f"notification: {app!r} -> rule '{rule['name']}'")
            return rule["name"]
        # no rule matched: show it anyway (any and all notifications)
        if self.cfg.get("show_all", True):
            d = dict(self.cfg.get("default", DEFAULT["default"]))
            if now - self.last_fired.get("__all__", -999) < d.get("cooldown", 3):
                return "all(cooldown)"
            self.last_fired["__all__"] = now
            d["name"] = "all"
            color = app_color(app)                 # a distinct colour per source
            d["color"] = color
            self.fire(d)
            self._notify_ui(app, title, body, color)
            log(f"notification: {app!r} -> show-all")
            return "all"
        return None

    def fire(self, rule: dict) -> None:
        with self.lock:
            self.overlays.append((rule, time.monotonic()))
        self._play(rule)

    # -- MIDI ----------------------------------------------------------------
    def _open_port(self, now: float) -> None:
        if self.port is not None or now < self.next_port_try:
            return
        self.next_port_try = now + 5.0
        try:
            import mido

            names = mido.get_output_names()
        except Exception:
            return
        wanted = [n for n in names if any(k.lower() in n.lower() for k in PORT_CONTAINS)]
        name = wanted[0] if wanted else (names[0] if names else None)
        if name:
            try:
                self.port = mido.open_output(name)
                log(f"notify MIDI out: {name}")
            except Exception:
                pass

    def _play(self, rule: dict) -> None:
        now = time.monotonic()
        self._open_port(now)
        if self.port is None:
            return
        import mido

        try:
            self.port.send(mido.Message("note_on", note=int(rule.get("note", 39)),
                                        velocity=int(rule.get("velocity", 110)),
                                        channel=int(rule.get("channel", 0))))
            self.pending_off.append((now + 0.15, int(rule.get("note", 39)),
                                     int(rule.get("channel", 0))))
        except Exception:
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.next_port_try = 0.0

    # -- overlay rendering (called from ArcadeOS.draw) -----------------------
    def draw_overlay(self, screen, now: float) -> None:
        for off_t, note, ch in list(self.pending_off):
            if now >= off_t:
                try:
                    import mido

                    if self.port:
                        self.port.send(mido.Message("note_off", note=note, channel=ch))
                except Exception:
                    pass
                self.pending_off.remove((off_t, note, ch))
        with self.lock:
            self.overlays = [(r, t0) for r, t0 in self.overlays
                             if now - t0 < r.get("duration", 2.5)]
            active = list(self.overlays)
        for rule, t0 in active:
            age = now - t0
            dur = rule.get("duration", 2.5)
            a = max(0.0, (1.0 - age / dur)) * (0.55 + 0.45 * math.sin(age * 12))
            if a <= 0.02:
                continue
            color = rule.get("color", [240, 120, 0])
            style = rule.get("style", "border")
            if style == "flash":
                cells = range(144)
            elif style == "corner":
                cells = [y * 12 + x for y in (0, 1, 2) for x in (9, 10, 11)]
            else:  # border
                cells = ([i for i in range(12)] + [132 + i for i in range(12)]
                         + [y * 12 for y in range(1, 11)] + [y * 12 + 11 for y in range(1, 11)])
            for i in cells:
                px = screen.px[i]
                screen.px[i] = tuple(int(px[c] * (1 - a) + color[c] * a) for c in range(3))

    # -- Notification Center reader (via the FDA-granted ncread_helper) -------
    def _nc_poller(self) -> None:
        helper = ROOT / "ncread_helper"
        if not helper.exists():
            self.nc_status = "ncread_helper missing (swiftc -O ncread.swift -o ncread_helper -lsqlite3)"
            return
        import subprocess

        while True:
            try:
                proc = subprocess.Popen([str(helper)], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            except OSError as exc:
                self.nc_status = f"helper failed to launch: {exc}"
                time.sleep(5.0)
                continue
            # watch stderr for the access status
            def watch_err(p=proc):
                for line in iter(p.stderr.readline, b""):
                    txt = line.decode(errors="replace").strip()
                    if "watching" in txt:
                        self.nc_status = "ok"
                    elif "Full Disk Access" in txt or "denied" in txt:
                        self.nc_status = ("no access — grant Full Disk Access to "
                                          "ncread_helper in System Settings")
            threading.Thread(target=watch_err, daemon=True).start()
            for line in iter(proc.stdout.readline, b""):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    self.nc_status = "ok"
                    self.handle(obj.get("app", ""), obj.get("title", ""), obj.get("body", ""))
                except Exception:
                    pass
            proc.wait()
            time.sleep(3.0)     # helper exited (e.g. no FDA yet) — retry


SERVICE: NotifyService | None = None
_started = False


def get_service() -> NotifyService:
    global SERVICE
    if SERVICE is None:
        SERVICE = NotifyService()
    return SERVICE


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin", "")
        if origin and _origin_ok(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        self.send_response(204 if _origin_ok(origin) else 403)
        if origin and _origin_ok(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        svc = get_service()
        if self.path == "/":
            self._send(200, EDITOR.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/rules":
            self._send(200, json.dumps(svc.cfg).encode(), "application/json")
        elif self.path == "/status":
            with svc.lock:
                body = {"nc_status": svc.nc_status, "recent": svc.recent}
            self._send(200, json.dumps(body).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not _origin_ok(self.headers.get("Origin", "")):
            self._send(403, b"origin not allowed", "text/plain")
            return
        svc = get_service()
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, b"invalid JSON", "text/plain")
            return
        if self.path == "/notify":
            rule = svc.handle(str(body.get("app", "")), str(body.get("title", "")),
                              str(body.get("body", "")))
            self._send(200, json.dumps({"matched": rule}).encode(), "application/json")
        elif self.path == "/test":
            idx = body.get("rule")
            rules = svc.cfg["rules"]
            if isinstance(idx, int) and 0 <= idx < len(rules):
                svc.fire(rules[idx])
                self._send(200, b"fired", "text/plain")
            else:
                self._send(400, b"bad rule index", "text/plain")
        elif self.path == "/rules":
            rules = body.get("rules")
            if not isinstance(rules, list):
                self._send(400, b"rules must be a list", "text/plain")
                return
            for r in rules:
                if not isinstance(r.get("name"), str) or not r["name"]:
                    self._send(400, b"every rule needs a name", "text/plain")
                    return
                if "note" in r and not (isinstance(r["note"], int) and 0 <= r["note"] <= 127):
                    self._send(400, f"rule '{r['name']}': bad note".encode(), "text/plain")
                    return
            svc.cfg["rules"] = rules
            CONFIG.write_text(json.dumps(svc.cfg, indent=2) + "\n")
            self._send(200, b"saved", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")


def ensure_server(port: int = PORT) -> NotifyService:
    global _started
    svc = get_service()
    if not _started:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _started = True
        log(f"notifications: http://127.0.0.1:{port} (rules editor + webhook)")
    return svc
