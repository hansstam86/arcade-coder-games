"""Browser emulator: run an SDK Game with no hardware.

Serves a clickable 12x12 pad grid at http://127.0.0.1:7777 — clicks are
presses, frames stream over Server-Sent Events. Stdlib only.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import Game
from .runner import GameLoop

PORT = 7777
HTML = (Path(__file__).parent / "emulator.html").read_text()

_presses: "queue.Queue[tuple[int, int]]" = queue.Queue()
_frame_lock = threading.Lock()
_frame: list[str] = ["#000000"] * 144
_frame_seq = 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/press":
            q = parse_qs(url.query)
            try:
                _presses.put((int(q["x"][0]), int(q["y"][0])))
            except (KeyError, ValueError):
                pass
            self.send_response(204)
            self.end_headers()
        elif url.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            last_seq = -1
            try:
                while True:
                    with _frame_lock:
                        seq, px = _frame_seq, _frame
                    if seq != last_seq:
                        last_seq = seq
                        self.wfile.write(f"data: {json.dumps(px)}\n\n".encode())
                        self.wfile.flush()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                return
        else:
            self.send_response(404)
            self.end_headers()


def run_emulator(game_cls: type[Game], port: int = PORT, open_browser: bool = True) -> None:
    global _frame, _frame_seq
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    print(f"arcadecoder emulator: {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()

    loop = GameLoop(game_cls)
    interval = 1.0 / max(1, game_cls.fps)
    try:
        while True:
            t0 = time.monotonic()
            while not _presses.empty():
                x, y = _presses.get_nowait()
                loop.press(x, y)
            px = loop.tick()
            with _frame_lock:
                if px != _frame:
                    _frame = list(px)
                    _frame_seq += 1
            time.sleep(max(0.0, interval - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        print("bye", flush=True)
    finally:
        server.shutdown()
