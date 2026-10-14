"""Regression test: the app's entry script must be runnable directly.

Running 'python App/run_sgf_toolkit.py' puts App/ on sys.path rather than the
directory it was started from, so the script has to add its parent directory
itself. Without that, it fails with "No module named 'App'". This test runs the
script for real, in a subprocess, exactly as a user would.
"""

import hashlib
import os
import subprocess
import sys
import unittest

from . import sgfmill_test_support


def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_ROOT, "App", "run_sgf_toolkit.py")


def _hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_entry_script_runs_from_repo_root(tc):
    """'python App/run_sgf_toolkit.py' must start the app, not fail to import.

    SGF_TOOLKIT_EXIT_AFTER_STARTUP makes the app quit once its layout is ready,
    so this can run without a terminal.
    """
    # A stale __pycache__ inside App/ can hide this bug, because the installed
    # sgfmill package and the App package both live under the same directory.
    before = _hash(os.path.join(_ROOT, "sgfmill", "__init__.py"))
    env = dict(os.environ)
    env["SGF_TOOLKIT_EXIT_AFTER_STARTUP"] = "1"
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, os.path.join("App", "run_sgf_toolkit.py")],
        cwd=_ROOT, env=env, capture_output=True, timeout=120)
    after = _hash(os.path.join(_ROOT, "sgfmill", "__init__.py"))

    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    tc.assertEqual(result.returncode, 0, output[-2000:])
    tc.assertNotIn("ModuleNotFoundError", output)
    # The app must not have been satisfied by a cached .pyc of the library.
    tc.assertEqual(after, before, "sgfmill/__init__.py was modified!")

def test_entry_script_works_from_another_directory(tc):
    """The script must work when started from somewhere else entirely."""
    env = dict(os.environ)
    env["SGF_TOOLKIT_EXIT_AFTER_STARTUP"] = "1"
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, _SCRIPT],
        cwd=os.path.dirname(_ROOT), env=env, capture_output=True, timeout=120)
    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    tc.assertEqual(result.returncode, 0, output[-2000:])
    tc.assertNotIn("ModuleNotFoundError", output)
