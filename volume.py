"""Mac output-volume control for ArcadeOS's dedicated volume pads."""

from __future__ import annotations

import subprocess
import threading


class Volume:
    def __init__(self) -> None:
        self.level = self._read()

    def _read(self) -> int:
        try:
            out = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=2)
            return max(0, min(100, int(out.stdout.strip() or 50)))
        except Exception:
            return 50

    def _apply(self, v: int) -> None:
        try:
            subprocess.run(["osascript", "-e", f"set volume output volume {v}"],
                           timeout=2, capture_output=True)
        except Exception:
            pass

    def change(self, delta: int) -> int:
        self.level = max(0, min(100, self.level + delta))
        threading.Thread(target=self._apply, args=(self.level,), daemon=True).start()
        return self.level
