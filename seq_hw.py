#!/usr/bin/env python3
"""Run the step sequencer on the real board (used by the app bundle)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from seq import Sequencer

run(Sequencer, backend="hw")
