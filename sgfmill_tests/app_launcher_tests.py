"""Test the App/run_sgf_toolkit.cmd launcher.

The launcher is a small batch file, so these run it for real, in a subprocess.
SGF_TOOLKIT_EXIT_AFTER_STARTUP makes the app quit once its layout is ready, so
each case finishes on its own without a terminal.
"""

import os
import subprocess
import sys
import unittest

from . import sgfmill_test_support


def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LAUNCHER = os.path.join(_ROOT, "App", "run_sgf_toolkit.cmd")


def _run(cwd, *args):
    """Run the launcher in 'start and quit' mode, returning the result."""
    env = dict(os.environ)
    env["SGF_TOOLKIT_EXIT_AFTER_STARTUP"] = "1"
    env.pop("PYTHONPATH", None)
    return subprocess.run([_LAUNCHER, *args], cwd=cwd, env=env,
                          capture_output=True, timeout=180)


def _output(result):
    return (result.stdout + result.stderr).decode("utf-8", "replace")


@unittest.skipUnless(sys.platform == "win32",
                     "the launcher is a Windows batch file")
def test_launcher_runs_from_the_repository_root(tc):
    """With no argument it should open the directory it was started from."""
    result = _run(_ROOT)
    output = _output(result)
    tc.assertEqual(result.returncode, 0, output[-2000:])
    tc.assertNotIn("could not find a Python interpreter", output)

@unittest.skipUnless(sys.platform == "win32",
                     "the launcher is a Windows batch file")
def test_launcher_accepts_a_relative_directory(tc):
    """A directory is resolved against the caller's working directory."""
    result = _run(_ROOT, "examples")
    output = _output(result)
    tc.assertEqual(result.returncode, 0, output[-2000:])

    # From inside a subdirectory, '.' should mean that subdirectory, not App\.
    examples = os.path.join(_ROOT, "examples")
    result = _run(examples, ".")
    output = _output(result)
    tc.assertEqual(result.returncode, 0, output[-2000:])

@unittest.skipUnless(sys.platform == "win32",
                     "the launcher is a Windows batch file")
def test_launcher_prints_help_without_starting(tc):
    """--help should print the usage and exit, not open the interface."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("SGF_TOOLKIT_EXIT_AFTER_STARTUP", None)
    for option in ("--help", "-h"):
        result = subprocess.run([_LAUNCHER, option], cwd=_ROOT, env=env,
                                capture_output=True, timeout=180)
        output = _output(result)
        tc.assertEqual(result.returncode, 0, output[-2000:])
        tc.assertIn("Usage:", output)
        tc.assertIn("Ctrl+J", output)

@unittest.skipUnless(sys.platform == "win32",
                     "the launcher is a Windows batch file")
def test_launcher_reports_a_bad_directory(tc):
    """A directory that doesn't exist should be reported, not ignored."""
    result = _run(_ROOT, "no-such-directory-here")
    output = _output(result)
    tc.assertNotEqual(result.returncode, 0)
    tc.assertIn("not a directory", output)
