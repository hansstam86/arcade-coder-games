"""Local web editor for deck.json — served by the running deck at
http://127.0.0.1:7788. Saving writes deck.json; the deck hot-reloads it.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 7788
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "deck.json"
EDITOR = ROOT / "deck_editor.html"

_started = False

# Origins allowed to use the API cross-origin (the hosted editor). Anything
# else with an Origin header is rejected — a malicious page must not be able
# to write commands into deck.json.
ALLOWED_ORIGINS = {"https://hansstam86.github.io"}


def _origin_ok(origin: str) -> bool:
    return (
        not origin
        or origin in ALLOWED_ORIGINS
        or origin.startswith("http://127.0.0.1")
        or origin.startswith("http://localhost")
    )


def _validate(cfg: dict) -> str | None:
    if not isinstance(cfg.get("pages"), dict) or not cfg["pages"]:
        return "config needs a non-empty 'pages' object"
    for name, page in cfg["pages"].items():
        for b in page.get("buttons", []):
            for key in ("x", "y"):
                if not isinstance(b.get(key), int) or not 0 <= b[key] < 12:
                    return f"button in '{name}': bad {key}"
            act = b.get("action", {})
            if act.get("type") == "page" and act.get("target") not in cfg["pages"]:
                return f"button '{b.get('label', '?')}' targets unknown page '{act.get('target')}'"
    if cfg.get("start_page") not in cfg["pages"]:
        return "start_page must name an existing page"
    return None


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
            self._send(200, EDITOR.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/config":
            self._send(200, CONFIG.read_bytes(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not _origin_ok(self.headers.get("Origin", "")):
            self._send(403, b"origin not allowed", "text/plain")
            return
        if self.path != "/config":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send(400, f"invalid JSON: {exc}".encode(), "text/plain")
            return
        problem = _validate(cfg)
        if problem:
            self._send(400, problem.encode(), "text/plain")
            return
        if CONFIG.exists():
            CONFIG.with_suffix(".json.bak").write_bytes(CONFIG.read_bytes())
        CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
        self._send(200, b"saved", "text/plain")


def ensure_server(port: int = PORT) -> None:
    global _started
    if _started:
        return
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _started = True
    print(f"[{time.strftime('%H:%M:%S')}] deck editor: http://127.0.0.1:{port}", flush=True)
