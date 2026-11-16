#!/usr/bin/env python3
"""Rebuild every diagram SVG in this folder (controllers_gamepad.svg is the hand-made style reference)."""
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
for name in ("system_loop", "training_loop", "curriculum", "data_flow"):
    subprocess.run([sys.executable, os.path.join(here, f"make_{name}.py")], check=True)
