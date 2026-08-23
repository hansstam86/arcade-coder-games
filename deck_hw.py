#!/usr/bin/env python3
"""Run the ArcadeDeck on the real board (used by the app bundle launcher)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)  # keep device_config.json in the repo
from arcadecoder import run
from deck import Deck

run(Deck, backend="hw")
