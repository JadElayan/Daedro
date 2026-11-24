"""Daedro: catch robot behaviour regressions before they ship (simulation)."""
import os
import sys

# Off-screen rendering (videos, camera observations) on a headless Linux box needs EGL, and
# MuJoCo picks its GL backend when it is first imported, so set it here. Leave other
# platforms (macOS, Linux desktops with a display) on MuJoCo's own default.
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("MUJOCO_GL", "egl")

__version__ = "0.2.0"
