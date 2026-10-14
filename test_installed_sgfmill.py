"""Run the sgfmill testsuite against an installed sgfmill package.

Unlike run_sgfmill_testsuite, this deliberately does not import the sgfmill
package from its sibling directory: the distribution directory is dropped from
sys.path first, so the tests run against whichever sgfmill is installed. The
sgfmill_tests package is then loaded from an explicit path, so that it remains
importable without its sibling sgfmill.
"""

import importlib.util
import os
import sys

from pathlib import Path

project_dir = Path(Path.cwd(), __file__).parent

# Remove the distribution directory from sys.path, wherever it appears. When
# the script is invoked by an absolute path, sys.path[0] is the directory
# containing the script rather than the directory it was started from, but an
# entry for the latter may still be present.
project_dir_str = str(project_dir)
sys.path[:] = [p for p in sys.path
               if os.path.abspath(p) != project_dir_str]

try:
    import sgfmill
except ImportError:
    sys.exit("test_installed_sgfmill: can't find the sgfmill package")

PACKAGE_NAME = "sgfmill_tests"

# Make sgfmill_tests importable without the sibling sgfmill.
packagepath = Path(project_dir, PACKAGE_NAME)
spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME, packagepath / "__init__.py",
    submodule_search_locations=[str(packagepath)])
mdl = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE_NAME] = mdl
spec.loader.exec_module(mdl)

found = Path(Path.cwd(), sgfmill.__file__).parent
print("testing sgfmill package in %s" % found, file=sys.stderr)
from sgfmill_tests import run_sgfmill_testsuite
run_sgfmill_testsuite.run(sys.argv[1:])
