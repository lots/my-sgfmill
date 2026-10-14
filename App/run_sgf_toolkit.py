#!/usr/bin/env python3
"""Run the SGF Toolkit Textual app.

    python App/run_sgf_toolkit.py [directory]

This script adds the directory containing the App package to sys.path, so it
works when run directly from anywhere. (Running a script puts *its own*
directory on sys.path, not the directory you started it from, so without this
the 'App' package couldn't be found.)
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from App.sgf_toolkit import main


if __name__ == "__main__":
    main()
