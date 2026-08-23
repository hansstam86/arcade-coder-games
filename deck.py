#!/usr/bin/env python3
"""ArcadeDeck — turn the Arcade Coder into a fully customizable macro deck.

Buttons, pages, colours, and actions live in deck.json. Actions run on the
computer this script runs on; the board is the control surface.

  python deck.py            # test your layout in the browser emulator
  python deck_hw.py         # run on the real board (via the app bundle)

Config format (deck.json):
  {
    "start_page": "main",
    "pages": {
      "main": { "buttons": [
        { "x": 0, "y": 0, "w": 3, "h": 3, "label": "mute",
          "color": [0, 180, 0],
          "action": { "type": "shell", "command": "..." },
          "status": { "command": "...", "interval": 3,
                      "on_color": [220, 0, 0], "off_color": [0, 180, 0] } },
        { "x": 8, "y": 8, "w": 3, "h": 3, "label": "apps",
          "color": [0, 60, 220], "action": { "type": "page", "target": "apps" } }
      ] }
    }
  }

Action types:
  shell        {command}            run a shell command
  open         {target}             `open <target>` (app path, URL, file)
  applescript  {script}             `osascript -e <script>`
  page         {target}             switch to another page

A button flashes white on press, then green/red when its command exits 0/non-0.
With "status", the check command runs every `interval` seconds and the button
shows on_color when it exits 0, off_color otherwise.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run

CONFIG_PATH = Path(__file__).resolve().parent / "deck.json"

FLASH_PRESS = (255, 255, 255)
FLASH_OK = (0, 255, 0)
FLASH_FAIL = (255, 0, 0)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Button:
    def __init__(self, spec: dict) -> None:
        self.x, self.y = int(spec["x"]), int(spec["y"])
        self.w, self.h = int(spec.get("w", 3)), int(spec.get("h", 3))
        self.label = spec.get("label", "?")
        self.color = tuple(spec.get("color", [120, 120, 120]))
        self.action = spec.get("action", {})
        self.status = spec.get("status")
        self.status_state: bool | None = None
        self.status_proc: subprocess.Popen | None = None
        self.next_poll = 0.0
        self.action_proc: subprocess.Popen | None = None

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def current_color(self):
        if self.status and self.status_state is not None:
            key = "on_color" if self.status_state else "off_color"
            return tuple(self.status.get(key, self.color))
        return self.color


def action_command(action: dict) -> list[str] | None:
    kind = action.get("type")
    if kind == "shell":
        return ["/bin/sh", "-c", action["command"]]
    if kind == "open":
        target = action["target"]
        # "www.youtube.com" is a URL, not a file — give bare domains a scheme
        if "://" not in target and not target.startswith(("/", "~")) and "." in target.split("/")[0] and not Path(target).exists():
            target = "https://" + target
        return ["open", target]
    if kind == "applescript":
        return ["osascript", "-e", action["script"]]
    return None


class Deck(Game):
    fps = 8
    config_path = CONFIG_PATH

    def start(self):
        self._load(initial=True)
        self.flashes: dict[int, tuple[tuple, float]] = {}  # id(btn) -> (color, until)
        self._next_mtime_check = 0.0
        try:  # local web editor for the config (see deck_web.py)
            from deck_web import ensure_server

            ensure_server()
        except Exception as exc:  # noqa: BLE001
            log(f"config editor not started: {exc!r}")
        log(f"deck up — page '{self.page}', {sum(len(b) for b in self.pages.values())} buttons")

    def _load(self, initial: bool = False) -> None:
        path = Path(self.config_path)
        cfg = json.loads(path.read_text())
        self.pages = {
            name: [Button(b) for b in page.get("buttons", [])]
            for name, page in cfg["pages"].items()
        }
        keep = None if initial else getattr(self, "page", None)
        self.page = keep if keep in self.pages else cfg.get("start_page", next(iter(self.pages)))
        self._cfg_mtime = path.stat().st_mtime

    def _maybe_reload(self, now: float) -> None:
        if now < self._next_mtime_check:
            return
        self._next_mtime_check = now + 1.0
        try:
            if Path(self.config_path).stat().st_mtime != self._cfg_mtime:
                self._load()
                self.flashes.clear()
                log(f"deck.json changed — reloaded (page '{self.page}')")
        except (OSError, json.JSONDecodeError, KeyError, StopIteration) as exc:
            log(f"config reload failed, keeping old config: {exc!r}")
            self._cfg_mtime = Path(self.config_path).stat().st_mtime

    def buttons(self):
        return self.pages[self.page]

    def on_press(self, x, y):
        now = time.monotonic()
        for btn in self.buttons():
            if not btn.contains(x, y):
                continue
            kind = btn.action.get("type")
            if kind == "page":
                target = btn.action.get("target")
                if target in self.pages:
                    self.page = target
                    log(f"page -> {target}")
                return
            cmd = action_command(btn.action)
            if cmd is None:
                log(f"button '{btn.label}': no runnable action")
                return
            log(f"button '{btn.label}': {' '.join(shlex.quote(c) for c in cmd[:3])}")
            self.flashes[id(btn)] = (FLASH_PRESS, now + 0.25)
            try:
                btn.action_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except OSError as exc:
                log(f"button '{btn.label}' failed to launch: {exc}")
                self.flashes[id(btn)] = (FLASH_FAIL, now + 0.8)
            return

    def update(self, dt):
        now = time.monotonic()
        self._maybe_reload(now)
        for btn in self.buttons():
            # harvest finished actions -> success/failure flash
            if btn.action_proc is not None and btn.action_proc.poll() is not None:
                ok = btn.action_proc.returncode == 0
                self.flashes[id(btn)] = (FLASH_OK if ok else FLASH_FAIL, now + 0.6)
                if not ok:
                    log(f"button '{btn.label}' exited {btn.action_proc.returncode}")
                btn.action_proc = None
                btn.next_poll = 0.0  # refresh status right away
            # status polling
            if btn.status:
                if btn.status_proc is not None:
                    rc = btn.status_proc.poll()
                    if rc is not None:
                        btn.status_state = rc == 0
                        btn.status_proc = None
                elif now >= btn.next_poll:
                    btn.next_poll = now + float(btn.status.get("interval", 5))
                    try:
                        btn.status_proc = subprocess.Popen(
                            ["/bin/sh", "-c", btn.status["command"]],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    except OSError:
                        pass
        self.flashes = {k: v for k, v in self.flashes.items() if v[1] > now}

    def draw(self, screen):
        screen.clear((3, 3, 5))
        for btn in self.buttons():
            flash = self.flashes.get(id(btn))
            color = flash[0] if flash else btn.current_color()
            for yy in range(btn.y, min(btn.y + btn.h, 12)):
                for xx in range(btn.x, min(btn.x + btn.w, 12)):
                    screen.set(xx, yy, color)


if __name__ == "__main__":
    run(Deck)
