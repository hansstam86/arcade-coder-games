#!/usr/bin/env python3
"""Run ArcadeOS on the real board (used by the app bundle launcher)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from arcadeos import ArcadeOS

run(ArcadeOS, backend="hw")
