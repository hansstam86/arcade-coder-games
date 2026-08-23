#!/usr/bin/env python3
"""Run ambient mode on the real board (used by the app bundle)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from ambient import Ambient

run(Ambient, backend="hw")
