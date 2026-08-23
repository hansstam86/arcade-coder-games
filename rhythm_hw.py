#!/usr/bin/env python3
"""Run the rhythm game on the real board (used by the app bundle)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from rhythm import Rhythm

run(Rhythm, backend="hw")
