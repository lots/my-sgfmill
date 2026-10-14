"""Tests for the SGF Toolkit layout and its three-step flow.

These cover things app_tests.py does not: where the panes are, that the help
pane describes the highlighted action, and that writing to an existing name
does not overwrite it.
"""

import asyncio
import contextlib
import shutil
import uuid
from pathlib import Path

from . import sgfmill_test_support

from App.sgf_toolkit import OperationHelp, SgfToolkitApp

from sgfmill import sgf


def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


def _run(coro):
    return asyncio.run(coro)


@contextlib.contextmanager
def scratch_dir():
    """A scratch directory inside the source tree (see app_tests.py)."""
    base = Path(__file__).resolve().parent.parent / ".tmp" / "app_layout_tests"
    path = base / ("case_" + uuid.uuid4().hex[:12])
    path.mkdir(parents=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_sample(directory, name="sample.sgf", with_junk=False):
    game = sgf.Sgf_game(size=9)
    root = game.get_root()
    root.set("PB", "Black")
    if with_junk:
        root.set_raw("MULTIGOGM", b"1")
    game.extend_main_sequence().set_move("b", (2, 2))
    path = Path(directory) / name
    path.write_bytes(game.serialise())
    return path


def _text_of(app, selector):
    """The visible text of a Static-like widget, as a string."""
    import io
    from rich.console import Console
    content = app.query_one(selector).content
    if isinstance(content, str):
        return content
    console = Console(file=io.StringIO(), width=110, no_color=True,
                      legacy_windows=False)
    console.print(content)
    return console.file.getvalue()


def test_layout_order(tc):
    """The three steps read left to right and top to bottom, with help below.

    Step 1 (the explorer) is on the left, step 2 (the actions) is beside it and
    above its results, and the help pane spans the bottom of the window.
    """
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                explorer = app.query_one("#explorer").region
                actions = app.query_one("#operations-pane").region
                results = app.query_one("#results").region
                help_pane = app.query_one("#help").region

                # Step 1 is on the left, and nothing else is to its left.
                tc.assertEqual(explorer.x, 0)
                # Step 2 is to the right of step 1, sharing the result column.
                tc.assertEqual(actions.x, explorer.width)
                # Step 3 is below step 2, in the same column.
                tc.assertEqual(results.x, actions.x)
                tc.assertLess(actions.y, results.y)
                # Help spans the bottom, below everything else.
                tc.assertEqual(help_pane.x, 0)
                tc.assertGreater(help_pane.y, explorer.y)
                tc.assertGreater(help_pane.y, results.y)
                tc.assertGreater(help_pane.width, explorer.width)
        _run(scenario())

def test_help_describes_each_action(tc):
    """Highlighting an action should describe it in the help pane."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                help_pane = app.query_one(OperationHelp)
                # Every action has help text.
                for identifier, _label, _prompt, _default in app.OPERATIONS:
                    tc.assertIn(identifier, OperationHelp.HELP,
                                "no help for %s" % identifier)
                # The pane shows the help for the selected action.
                app._set_action(0)
                await pilot.pause()
                first = _text_of(app, "#help")
                tc.assertIn("ASCII board", first)
                # ...and changes when another action is selected.
                index = [o[0] for o in app.OPERATIONS].index("check")
                app._set_action(index)
                await pilot.pause()
                second = _text_of(app, "#help")
                tc.assertNotEqual(first, second)
                tc.assertIn("FF[4]", second)
                # An action with a parameter says so, and what it gets.
                index = [o[0] for o in app.OPERATIONS].index("clean")
                app._set_action(index)
                await pilot.pause()
                third = _text_of(app, "#help")
                tc.assertIn("Output file", third)
        _run(scenario())

def test_help_mentions_the_parameter(tc):
    """Help for an action with a parameter should say what the box is for.

    The help is prose rather than the label verbatim, so this checks that the
    kind of thing being asked for appears in it.
    """
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                for identifier, _label, prompt, _default in app.OPERATIONS:
                    if prompt is None:
                        continue
                    # 'Move number (blank = final)' -> 'Move number'
                    keyword = prompt.split("(")[0].strip()
                    index = [o[0] for o in app.OPERATIONS].index(identifier)
                    app._set_action(index)
                    await pilot.pause()
                    shown = _text_of(app, "#help")
                    tc.assertIn(keyword, shown,
                                "help for %s omits its parameter" % identifier)
        _run(scenario())

def test_help_can_be_toggled(tc):
    """'h' should hide and show the help pane."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                help_pane = app.query_one(OperationHelp)
                tc.assertTrue(help_pane.display)
                await pilot.press("h")
                await pilot.pause()
                tc.assertFalse(help_pane.display)
                await pilot.press("h")
                await pilot.pause()
                tc.assertTrue(help_pane.display)
        _run(scenario())

def test_output_name_is_not_overwritten(tc):
    """Writing to a name that exists should pick a free name instead."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp, with_junk=True)
        existing = Path(tmp) / "sample-clean.sgf"
        existing.write_text("do not clobber me")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("clean")
                app._set_action(index)
                # The suggested default is the existing name.
                tc.assertEqual(app.query_one("#param-input").value,
                               str(existing))
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        # The existing file is untouched, and a numbered file was written.
        tc.assertEqual(existing.read_text(), "do not clobber me")
        written = sorted(p.name for p in Path(tmp).glob("sample-clean-*.sgf"))
        tc.assertEqual(written, ["sample-clean-1.sgf"])
        cleaned = sgf.Sgf_game.from_bytes(
            (Path(tmp) / "sample-clean-1.sgf").read_bytes())
        tc.assertFalse(cleaned.get_root().has_property("MULTIGOGM"))

def test_dash_writes_back_to_the_target(tc):
    """'-' means the open file, as the help pane says for Save."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("clean")
                app._set_action(index)
                app.query_one("#param-input").value = "-"
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        # The target itself was rewritten (here it was already clean).
        tc.assertTrue(sgf.Sgf_game.from_bytes(path.read_bytes()).get_size() == 9)

def test_target_is_shown_before_the_action(tc):
    """The parameter row should name the target, so step 2 is unambiguous.

    The target's own details (size, board, games, encoding) are in the bar
    above it.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                tc.assertIn("none selected", _text_of(app, "#target-bar"))
                app.load_file(path)
                await pilot.pause()
                # The details bar describes the file...
                bar = _text_of(app, "#target-bar")
                tc.assertIn("9x9", bar)
                tc.assertIn("1 game", bar)
                # ...and the parameter row says which file the action applies to.
                row = _text_of(app, "#param-label")
                tc.assertIn("sample.sgf", row)
        _run(scenario())
