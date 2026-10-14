"""Tests for the SGF Toolkit layout and its three-step flow.

The window is two rows: three panels side by side on the top row (target,
actions, result) and a single message pane across the bottom. These tests cover
that arrangement, the message text, and that writing to an existing name does
not overwrite it.
"""

import asyncio
import contextlib
import io
import shutil
import uuid
from pathlib import Path

from rich.console import Console

from . import sgfmill_test_support

from App.sgf_toolkit import MessageBar, SgfToolkitApp

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
    """The text of a Static-like widget, as a string."""
    content = app.query_one(selector).content
    if isinstance(content, str):
        return content
    console = Console(file=io.StringIO(), width=200, no_color=True,
                      legacy_windows=False)
    console.print(content)
    return console.file.getvalue()


def _visible_text(app, selector):
    """What the widget shows on screen, with line wrapping applied."""
    console = Console(file=io.StringIO(), width=400, no_color=True,
                      legacy_windows=False)
    console.print(app.query_one(selector).render())
    return console.file.getvalue().replace("\n", " ")


def test_two_rows_only(tc):
    """Three panels across the top row, and one message pane below them."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                explorer = app.query_one("#explorer").region
                actions = app.query_one("#operations-pane").region
                results = app.query_one("#results").region
                message = app.query_one("#message-bar").region

                # The three panels are side by side: same row, increasing x.
                tc.assertEqual(explorer.y, actions.y)
                tc.assertEqual(actions.y, results.y)
                tc.assertLess(explorer.x, actions.x)
                tc.assertLess(actions.x, results.x)
                # ...and they have the same height, filling the row.
                tc.assertEqual(explorer.height, actions.height)
                tc.assertEqual(actions.height, results.height)
                # ...they start at the left edge and are not stacked.
                tc.assertEqual(explorer.x, 0)
                tc.assertEqual(actions.x, explorer.width)
                # The message pane is its own row, below all three.
                tc.assertEqual(message.x, 0)
                tc.assertGreater(message.y, explorer.y)
                tc.assertGreater(message.y, actions.y)
                tc.assertGreater(message.y, results.y)
                tc.assertGreater(message.width, results.width - 1)
        _run(scenario())

def test_message_bar_describes_each_action(tc):
    """The message pane should describe the highlighted action."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                # Every action has a message.
                for identifier, _label, _prompt, _default in app.OPERATIONS:
                    tc.assertIn(identifier, MessageBar.HELP,
                                "no message for %s" % identifier)
                app._set_action(0)
                await pilot.pause()
                first = _visible_text(app, "#message-bar")
                tc.assertIn("ASCII board", first)
                # ...and it changes when another action is selected.
                index = [o[0] for o in app.OPERATIONS].index("check")
                app._set_action(index)
                await pilot.pause()
                second = _visible_text(app, "#message-bar")
                tc.assertNotEqual(first, second)
                tc.assertIn("FF[4]", second)
        _run(scenario())

def test_message_bar_mentions_the_parameter_and_target(tc):
    """The message should say which file the action applies to, and what the
    parameter box is for."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                for identifier, _label, prompt, _default in app.OPERATIONS:
                    index = [o[0] for o in app.OPERATIONS].index(identifier)
                    app._set_action(index)
                    await pilot.pause()
                    shown = _visible_text(app, "#message-bar")
                    tc.assertIn("sample.sgf", shown,
                                "message for %s omits the target" % identifier)
                    if prompt is not None:
                        # 'Move number (blank = final)' -> 'Move number'
                        keyword = prompt.split("(")[0].strip()
                        tc.assertIn(keyword, shown,
                                    "message for %s omits its parameter"
                                    % identifier)
        _run(scenario())

def test_message_bar_can_be_toggled(tc):
    """'h' should hide and show the message pane."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                bar = app.query_one(MessageBar)
                tc.assertTrue(bar.display)
                await pilot.press("h")
                await pilot.pause()
                tc.assertFalse(bar.display)
                await pilot.press("h")
                await pilot.pause()
                tc.assertTrue(bar.display)
        _run(scenario())

def test_output_name_is_not_overwritten(tc):
    """Writing to a name that exists should pick a free name instead."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp, with_junk=True)
        existing = Path(tmp) / "sample-clean.sgf"
        existing.write_text("do not clobber me")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
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
    """'-' means the open file, as the message pane says for Save."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("clean")
                app._set_action(index)
                app.query_one("#param-input").value = "-"
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        tc.assertTrue(sgf.Sgf_game.from_bytes(path.read_bytes()).get_size() == 9)

def test_target_details_bar(tc):
    """The results panel should describe the target it is showing."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                tc.assertIn("no target selected", _text_of(app, "#target-bar"))
                app.load_file(path)
                await pilot.pause()
                bar = _text_of(app, "#target-bar")
                tc.assertIn("9x9", bar)
                tc.assertIn("1 game", bar)
        _run(scenario())
