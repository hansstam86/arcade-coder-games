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
    "rules": [
        {"name": "slack", "app_contains": "slack", "title_contains": "",
         "color": [240, 120, 0], "style": "border", "note": 39,
         "velocity": 110, "channel": 0, "duration": 2.5, "cooldown": 4,
         "enabled": True},
        {"name": "mail", "app_contains": "mail", "title_contains": "",
         "color": [0, 90, 240], "style": "corner", "note": 37,
         "velocity": 100, "channel": 0, "duration": 2.0, "cooldown": 8,
         "enabled": True},
    ]
}


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
        self.lock = threading.Lock()
        threading.Thread(target=self._nc_poller, daemon=True).start()

    # -- rule engine ---------------------------------------------------------
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
            log(f"notification: {app!r} -> rule '{rule['name']}'")
            return rule["name"]
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

    # -- Notification Center poller ------------------------------------------
    def _nc_poller(self) -> None:
        last_seen = time.time() - 978307200.0     # Cocoa epoch offset: start now
        while True:
            try:
                con = sqlite3.connect(f"file:{NC_DB}?mode=ro", uri=True, timeout=1.0)
                rows = con.execute(
                    "SELECT a.identifier, r.delivered_date, r.data "
                    "FROM record r JOIN app a ON r.app_id = a.app_id "
                    "WHERE r.delivered_date > ? ORDER BY r.delivered_date LIMIT 20",
                    (last_seen,)).fetchall()
                con.close()
                self.nc_status = "ok"
                for identifier, delivered, blob in rows:
                    last_seen = max(last_seen, delivered)
                    title = body = ""
                    try:
                        d = plistlib.loads(blob)
                        req = d.get("req", {})
                        title = req.get("titl", "") or ""
                        body = req.get("body", "") or ""
                    except Exception:
                        pass
                    self.handle(identifier or "", title, body)
            except Exception as exc:  # noqa: BLE001
                self.nc_status = f"no access ({type(exc).__name__}) — use the webhook, or grant Full Disk Access to ArcadeMinesweeper"
            time.sleep(2.0)


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
