"""pytest integration for sgfmill's custom test framework.

sgfmill does not use unittest test discovery. Each ``*_tests.py`` module
exposes a ``make_tests(suite)`` factory which builds its cases at run time,
wrapping bare ``def test_xxx(tc)`` functions in ``Sgfmill_SimpleTestCase``
objects. ``sgfmill_tests/run_sgfmill_testsuite.py`` calls those factories and
stays the authoritative runner.

pytest's default collection cannot see any of that: the modules define no
``Test*`` classes, and the ``test_xxx`` functions take a TestCase argument
rather than fixtures. This conftest bridges the gap by calling the *same*
factories and exposing the resulting TestCase objects as individual pytest
items, so ``pytest`` runs the real suite with normal per-test reporting.

There is no duplicated test logic here -- only collection and reporting glue.
If this file is deleted, ``python -m sgfmill_tests.run_sgfmill_testsuite``
still works unchanged.
"""

import unittest

try:
    from _pytest.nodes import Item
except ImportError:      # pragma: no cover - pytest not installed
    Item = None


class UnittestResult(unittest.TestResult):
    """unittest TestResult that replays outcomes through a pytest callback.

    Executing a TestCase through unittest's own TestResult -- rather than
    hand-rolling assertion handling -- is what keeps failure messages and
    tracebacks identical to the authoritative runner.
    """

    def __init__(self, on_success, on_skip, on_failure):
        super().__init__()
        self._on_success = on_success
        self._on_skip = on_skip
        self._on_failure = on_failure

    def addSuccess(self, test):
        super().addSuccess(test)
        self._on_success()

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._on_skip(reason)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._on_failure(self._exc_info_text(err))

    def addError(self, test, err):
        super().addError(test, err)
        self._on_failure(self._exc_info_text(err))

    @staticmethod
    def _exc_info_text(err):
        import traceback
        return "".join(traceback.format_exception(*err))


if Item is not None:

    class SgfmillTestCaseItem(Item):
        """One sgfmill TestCase, reported as a single pytest item."""

        def __init__(self, *, testcase, **kw):
            super().__init__(**kw)
            self.testcase = testcase

        @classmethod
        def from_testcase(cls, parent, testcase):
            return cls.from_parent(
                parent, name=testcase.id(), testcase=testcase)

        def runtest(self):
            from _pytest.outcomes import fail, skip

            result = UnittestResult(
                on_success=lambda: None,
                on_skip=lambda reason: skip(reason),
                on_failure=lambda text: fail(text, pytrace=False),
            )
            self.testcase.run(result)

        def reportinfo(self):
            return self.path, 0, self.name


def _flatten(suite):
    """Yield every leaf TestCase from a (possibly nested) TestSuite."""
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _flatten(test)
        else:
            yield test


def _is_parameterised_base_class(obj):
    """True for TestCase classes that must be constructed with parameters.

    board_tests.py defines Play_test_TestCase and friends as subclasses of
    ParameterisedTestCase. They carry no test methods of their own -- the
    factory in make_tests instantiates them with actual parameters -- so
    pytest must not collect them directly.
    """
    if not isinstance(obj, type):
        return False
    from . import test_framework
    for cls in obj.__mro__:
        is_parameterised = issubclass(
            cls, test_framework.ParameterisedTestCase)
        runs_real_test = (
            cls.__dict__.get("runTest") is not
            test_framework.ParameterisedTestCase.runTest)
        if is_parameterised and runs_real_test:
            return True
    return False


def pytest_pycollect_makeitem(collector, name, obj):
    """Turn a module's ``make_tests`` factory into one item per TestCase."""
    if _is_parameterised_base_class(obj):
        return []
    if name != "make_tests" or Item is None:
        return None
    try:
        suite = unittest.TestSuite()
        obj(suite)
        cases = list(_flatten(suite))
    except Exception:
        # Never break collection; fall back to pytest's default handling.
        return None
    if not cases:
        return None
    return [
        SgfmillTestCaseItem.from_testcase(collector, case)
        for case in cases
    ]
