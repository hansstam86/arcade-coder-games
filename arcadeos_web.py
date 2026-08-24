"""ArcadeOS dashboard at http://127.0.0.1:7770 — see and switch the running app."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deck_web import _origin_ok

PORT = 7770
ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "arcadeos_dashboard.html"

_os = None
_started = False
_boot = time.time()


def set_os(os_app) -> None:
    global _os
    _os = os_app


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
        if self.path == "/":
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/status":
            from arcadeos import APPS

            body = {
                "app": _os.app_name if _os else "unknown",
                "apps": ["home"] + [n for n, *_ in APPS],
                "auto_ambient_from": getattr(_os, "auto_ambient_from", None),
                "busy": bool(getattr(getattr(_os, "app", None), "busy", False)),
                "uptime_s": int(time.time() - _boot),
            }
            self._send(200, json.dumps(body).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not _origin_ok(self.headers.get("Origin", "")):
            self._send(403, b"origin not allowed", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send(400, b"invalid JSON", "text/plain")
            return
        if self.path == "/marquee":
            from pathlib import Path

            cfg_path = Path(__file__).resolve().parent / "marquee.json"
            try:
                cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
            except Exception:
                cfg = {}
            for k in ("text", "speed", "rainbow", "color", "background"):
                if k in body:
                    cfg[k] = body[k]
            cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
            if _os is not None and body.get("show", True):
                _os.pending_switch = "marquee"    # jump to it so you see the change
            self._send(200, b"ok", "text/plain")
            return
        if self.path != "/switch":
            self._send(404, b"not found", "text/plain")
            return
        from arcadeos import APP_BY_NAME

        name = body.get("app")
        if name != "home" and name not in APP_BY_NAME:
            self._send(400, b"unknown app", "text/plain")
            return
        if _os is None:
            self._send(503, b"OS not attached", "text/plain")
            return
        _os.pending_switch = name
        self._send(200, b"switching", "text/plain")


def ensure_server(port: int = PORT) -> None:
    global _started
    if _started:
        return
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _started = True
    print(f"[{time.strftime('%H:%M:%S')}] ArcadeOS dashboard: http://127.0.0.1:{port}", flush=True)
