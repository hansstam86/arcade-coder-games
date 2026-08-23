#!/usr/bin/env python3
"""Run the MIDI visualizer on the real board (used by the app bundle)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from arcadecoder import run
from midiviz import MidiViz

run(MidiViz, backend="hw")
