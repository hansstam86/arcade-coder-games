"""Local web editor for kopads.json at http://127.0.0.1:7799.

Same pattern as deck_web: GET /config, validated POST /config (the running
KO-pads hot-reloads), plus POST /test to fire a test note at the EP-133.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deck_web import _origin_ok

PORT = 7799
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "kopads.json"
EDITOR = ROOT / "kopads_editor.html"

test_notes: "queue.Queue[int]" = queue.Queue()
_started = False


def _validate(cfg: dict) -> str | None:
    bands = cfg.get("bands")
    if not isinstance(bands, list) or len(bands) != 4:
        return "config needs exactly 4 bands"
    for b in bands:
        if not isinstance(b.get("base_note"), int) or not 0 <= b["base_note"] <= 115:
            return f"band {b.get('group', '?')}: base_note must be 0..115"
    if not isinstance(cfg.get("channel"), int) or not 0 <= cfg["channel"] <= 15:
        return "channel must be 0..15"
    if not isinstance(cfg.get("velocity"), int) or not 1 <= cfg["velocity"] <= 127:
        return "velocity must be 1..127"
    if cfg.get("layout") == "custom":
        for b in cfg.get("buttons", []):
            for key in ("x", "y"):
                if not isinstance(b.get(key), int) or not 0 <= b[key] < 12:
                    return f"button '{b.get('label', '?')}': bad {key}"
            m = b.get("midi", {})
            if m.get("type") not in ("note", "cc"):
                return f"button '{b.get('label', '?')}': midi.type must be note or cc"
            for k in ("note", "cc", "value", "on_value", "off_value", "velocity"):
                if k in m and not (isinstance(m[k], int) and 0 <= m[k] <= 127):
                    return f"button '{b.get('label', '?')}': bad {k}"
            if "channel" in m and not (isinstance(m["channel"], int) and 0 <= m["channel"] <= 15):
                return f"button '{b.get('label', '?')}': bad channel"
    for o in cfg.get("overrides", []):
        if not (isinstance(o.get("band"), int) and 0 <= o["band"] < 4):
            return "override: bad band"
        if not (isinstance(o.get("col"), int) and 0 <= o["col"] < 12):
            return "override: bad col"
        if "note" in o and not (isinstance(o["note"], int) and 0 <= o["note"] <= 127):
            return "override: bad note"
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
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send(400, f"invalid JSON: {exc}".encode(), "text/plain")
            return
        if self.path == "/test":
            note = body.get("note")
            midi = body.get("midi")
            if isinstance(midi, dict) and midi.get("type") in ("note", "cc"):
                test_notes.put(midi)
                self._send(200, b"queued", "text/plain")
            elif isinstance(note, int) and 0 <= note <= 127:
                test_notes.put(note)
                self._send(200, b"queued", "text/plain")
            else:
                self._send(400, b"bad note", "text/plain")
        elif self.path == "/config":
            problem = _validate(body)
            if problem:
                self._send(400, problem.encode(), "text/plain")
                return
            if CONFIG.exists():
                CONFIG.with_suffix(".json.bak").write_bytes(CONFIG.read_bytes())
            CONFIG.write_text(json.dumps(body, indent=2) + "\n")
            self._send(200, b"saved", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")


def ensure_server(port: int = PORT) -> None:
    global _started
    if _started:
        return
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _started = True
    print(f"[{time.strftime('%H:%M:%S')}] ko-pads editor: http://127.0.0.1:{port}", flush=True)
