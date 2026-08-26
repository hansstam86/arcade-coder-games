#!/usr/bin/env python3
"""Oracle — ask the board a question, it consults and answers.

Tap the glowing crystal ball; it swirls while it "thinks", then a short
cryptic answer scrolls across the board in gold.

Two brains:
  * local (default): a bank of mystical fortunes / yes-no verdicts.
  * AI: if `oracle.json` has a working setup it calls the real `claude` CLI
    for a fresh answer each time — set {"ai": true} and, if needed,
    {"oauth_token": "<from `claude setup-token`>"}. Falls back to local if the
    call fails, so it never hangs.

  python oracle.py            # emulator
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arcadecoder import Game, run
from marquee import render_columns

CONFIG_PATH = Path(__file__).resolve().parent / "oracle.json"
W = H = 12

FORTUNES = [
    "IT IS CERTAIN", "WITHOUT A DOUBT", "YES DEFINITELY", "THE STARS SAY YES",
    "SIGNS POINT TO YES", "ASK AGAIN LATER", "CANNOT SEE NOW", "DO NOT COUNT ON IT",
    "MY REPLY IS NO", "VERY DOUBTFUL", "FORTUNE FAVORS THE BOLD",
    "A JOURNEY BEGINS SOON", "PATIENCE BRINGS REWARD", "TRUST THE QUIET VOICE",
    "CHANGE IS ALREADY HERE", "THE ANSWER IS WITHIN", "SEEK AND YOU WILL FIND",
    "GOOD FORTUNE NEARS", "A FRIEND HOLDS THE KEY", "REST THEN TRY AGAIN",
    "BOLD MOVES WIN TODAY", "LET IT GO AND SEE", "THE TIDE IS TURNING",
    "GREAT THINGS TAKE TIME", "FOLLOW THE SMALL SPARK",
]

AI_PROMPT = ("You are a cryptic fortune oracle. Reply with ONE short fortune, "
             "max 8 words, UPPERCASE letters and spaces only, no punctuation, "
             "no quotes, nothing else.")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def hsv(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, max(0.0, min(1.0, v)))
    return int(r * 255), int(g * 255), int(b * 255)


class Oracle(Game):
    fps = 14

    def start(self):
        self.cfg = {"ai": False, "claude_cmd": "claude"}
        if CONFIG_PATH.exists():
            try:
                self.cfg.update(json.loads(CONFIG_PATH.read_text()))
            except Exception:
                pass
        self.state = "idle"           # idle | think | reveal
        self.answer = ""
        self.cols = []
        self.scroll = 0.0
        self.think_min = 0.0
        self._pending = None
        self.busy = False
        log("oracle ready — tap to consult")

    # -- consulting ----------------------------------------------------------
    def _clean(self, t: str) -> str:
        t = " ".join(t.strip().upper().split())
        t = "".join(c for c in t if c.isalnum() or c == " ")
        return t[:60] or random.choice(FORTUNES)

    def _ask_ai(self):
        try:
            env = dict(os.environ)
            tok = self.cfg.get("oauth_token")
            if tok:
                env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
                env.pop("ANTHROPIC_API_KEY", None)
            out = subprocess.run(
                [self.cfg.get("claude_cmd", "claude"), "-p", AI_PROMPT,
                 "--output-format", "text"],
                capture_output=True, text=True, timeout=45, env=env)
            if out.returncode == 0 and out.stdout.strip():
                self._pending = self._clean(out.stdout)
                return
        except Exception:
            pass
        self._pending = "__fail__"      # fall back to local

    def _consult(self):
        self.state = "think"
        now = time.monotonic()
        self.think_min = now + 2.4      # minimum suspense
        self.deadline = now + 45        # hard cap when waiting on the AI
        if self.cfg.get("ai"):
            self._pending = "__wait__"
            threading.Thread(target=self._ask_ai, daemon=True).start()
        else:
            self._pending = random.choice(FORTUNES)

    def _reveal(self, text):
        self.answer = text
        self.cols = render_columns("   " + text + "   ")
        self.scroll = -float(W)
        self.state = "reveal"
        log(f"oracle: {text}")

    def on_press(self, x, y):
        if self.state == "idle":
            self._consult()
        elif self.state == "reveal":
            self.state = "idle"          # tap to clear early

    def update(self, dt):
        now = time.monotonic()
        if self.state != "think" or now < self.think_min:
            return
        if self._pending == "__wait__" and now < self.deadline:
            return                                   # AI still thinking
        p = self._pending
        ans = p if (p and p not in ("__wait__", "__fail__")) else random.choice(FORTUNES)
        self._reveal(ans)

    # -- render --------------------------------------------------------------
    def _orb(self, screen, now, energy):
        cx, cy, r = 5.5, 5.5, 5.2
        spd = 0.4 + energy * 2.2
        for y in range(H):
            for x in range(W):
                d = math.hypot(x - cx, y - cy)
                if d <= r:
                    v = (math.sin(x * 0.7 + now * spd)
                         + math.sin(y * 0.6 - now * spd * 1.1)
                         + math.sin((x + y) * 0.5 + now * spd * 0.7)) / 3
                    hue = 0.72 + 0.12 * v + now * 0.03
                    bright = (0.25 + 0.35 * abs(v)) * (1 - d / r * 0.5) + energy * 0.3
                    screen.set(x, y, hsv(hue, 0.8, bright))
                elif d <= r + 0.8:
                    screen.set(x, y, hsv(0.75, 0.6, 0.15 + 0.2 * energy))
        if energy > 0.5:                              # sparkles while thinking
            for _ in range(2):
                sx, sy = random.randrange(W), random.randrange(H)
                if math.hypot(sx - cx, sy - cy) <= r:
                    screen.set(sx, sy, (255, 255, 255))

    def draw(self, screen):
        now = time.monotonic()
        screen.clear((2, 1, 8))
        if self.state == "reveal":
            self.scroll += 7.0 * (1 / self.fps)
            total = max(1, len(self.cols))
            base = int(self.scroll)
            for sx in range(W):
                ci = base + sx
                if 0 <= ci < total:
                    for r in range(5):
                        if self.cols[ci][r]:
                            screen.set(sx, 3 + r, (255, 210, 60))
            if self.scroll >= total:                  # done -> back to idle
                self.state = "idle"
            return
        energy = 0.15 if self.state == "idle" else min(1.0, 0.6 + 0.4 * math.sin(now * 6))
        self._orb(screen, now, energy)


if __name__ == "__main__":
    run(Oracle)
