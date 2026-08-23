#!/usr/bin/env python3
"""Run KO-pads on the real board (used by the app bundle launcher)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from kopads import KOPads

run(KOPads, backend="hw")
