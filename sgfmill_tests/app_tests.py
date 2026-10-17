"""Tests for the SGF Toolkit Textual app.

These drive the app headlessly with Textual's own test harness, so the
behaviour of each operation is checked rather than just its code being
imported.
"""

import asyncio
import contextlib
import os
import shutil
import uuid
from pathlib import Path

from . import sgfmill_test_support

from App.sgf_toolkit import SgfToolkitApp

from sgfmill import sgf


def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


def _run(coro):
    """Run an app test to completion."""
    return asyncio.run(coro)


def _text_of(app, selector):
    """The plain text currently shown by a Static widget.

    The content may be a string or any Rich renderable, so it is rendered
    through a Rich Console to get the text a user would see.
    """
    import io
    from rich.console import Console
    content = app.query_one(selector).content
    if isinstance(content, str):
        return content
    console = Console(file=io.StringIO(), width=200, no_color=True,
                      legacy_windows=False)
    console.print(content)
    return console.file.getvalue()


@contextlib.contextmanager
def scratch_dir():
    """A temporary directory, created inside the source tree.

    tempfile is not used: both the directories it creates and their cleanup
    involve changing permissions, which some sandboxes deny.
    """
    base = Path(__file__).resolve().parent.parent / ".tmp" / "app_tests"
    path = base / ("case_" + uuid.uuid4().hex[:12])
    path.mkdir(parents=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_sample(directory, name="sample.sgf", with_junk=False):
    """Write a small SGF file and return its path."""
    game = sgf.Sgf_game(size=9)
    root = game.get_root()
    root.set("PB", "Black")
    root.set("PW", "White")
    game.extend_main_sequence().set_move("b", (2, 2))
    game.extend_main_sequence().set_move("w", (6, 6))
    if with_junk:
        root.set_raw("MULTIGOGM", b"1")
    path = Path(directory) / name
    path.write_bytes(game.serialise())
    return path


def test_app_starts(tc):
    """The app should build its layout and offer its operations."""
    with scratch_dir() as tmp:
        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                listing = app.query_one("#operations")
                tc.assertEqual(len(listing.children), len(app.OPERATIONS))
                tc.assertIs(app.game, None)
                tc.assertIsNotNone(app.query_one("#explorer-tree"))
        _run(scenario())

def test_load_file_shows_board(tc):
    """Selecting a file should parse it and draw the board."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                tc.assertEqual(app.game.get_size(), 9)
                tc.assertEqual(app.game_count, 1)
                tc.assertEqual(app.path, path)
                # The board diagram should show both stones.
                rendered = _text_of(app, "#board-view")
                tc.assertIn("#", rendered)
                tc.assertIn("o", rendered)
                tc.assertEqual(app.encoding_result.encoding, "UTF-8")
        _run(scenario())

def test_operations_run(tc):
    """Every read-only operation should run without raising."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp, with_junk=True)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                for identifier in ("info", "properties", "moves", "check",
                                   "encoding", "board"):
                    app.current = (identifier, identifier, None, "")
                    app.run_current_operation()
                    await pilot.pause()
        _run(scenario())

def test_check_reports_non_standard(tc):
    """The check operation should find a private property."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp, with_junk=True)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                app.current = ("check", "check", None, "")
                app.run_current_operation()
                await pilot.pause()
                shown = _text_of(app, "#info-view")
                tc.assertIn("MULTIGOGM", shown)
        _run(scenario())

def test_clean_writes_file(tc):
    """Cleaning should write a file with the private property removed."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp, with_junk=True)
        target = Path(tmp) / "cleaned.sgf"

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                app.current = ("clean", "clean", "Output file", "")
                app.query_one("#param-input").value = str(target)
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        tc.assertTrue(target.exists())
        data = target.read_bytes()
        tc.assertNotIn(b"MULTIGOGM", data)
        # The result must still be a valid, loadable game.
        reloaded = sgf.Sgf_game.from_bytes(data)
        tc.assertEqual(reloaded.get_size(), 9)

def test_transform_writes_file(tc):
    """A board transform should write a new file with the move moved."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)
        target = Path(tmp) / "turned.sgf"

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                # Choose the action (which is what applies it), then set the
                # output name and run. (Running with nothing applied refuses,
                # since there would be no transformation to save.)
                app._set_action(
                    [o[0] for o in app.OPERATIONS].index("rotate_cw"))
                app._preview_transform("rotate_cw")
                await pilot.pause()
                app.query_one("#param-input").value = str(target)
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        tc.assertTrue(target.exists())
        before = sgf.Sgf_game.from_bytes(path.read_bytes())
        after = sgf.Sgf_game.from_bytes(target.read_bytes())
        _, before_plays = _plays(before)
        _, after_plays = _plays(after)
        tc.assertEqual(before_plays[0], ("b", (2, 2)))
        # A quarter turn clockwise on a 9x9 board: (row, col) -> (8-col, row),
        # so (2, 2) becomes (6, 2) and (6, 6) becomes (2, 6).
        tc.assertEqual(after_plays[0], ("b", (6, 2)))
        tc.assertEqual(after_plays[1], ("w", (2, 6)))

def _plays(game):
    from sgfmill import sgf_moves
    return sgf_moves.get_setup_and_moves(game)

def test_convert_encoding(tc):
    """Converting a Latin-1 file to UTF-8 should preserve the text."""
    with scratch_dir() as tmp:
        source = Path(tmp) / "latin1.sgf"
        source.write_bytes(
            "(;FF[4]CA[ISO-8859-1]GM[1]SZ[9]PB[José];B[cc])".encode("iso-8859-1"))
        target = Path(tmp) / "utf8.sgf"

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(source)
                await pilot.pause()
                tc.assertEqual(app.game.get_root().get("PB"), "José")
                tc.assertEqual(app.encoding_result.encoding, "ISO-8859-1")
                app.current = ("to_utf8", "to_utf8", "Output file", "")
                app.query_one("#param-input").value = str(target)
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        tc.assertTrue(target.exists())
        data = target.read_bytes()
        tc.assertIn(b"CA[UTF-8]", data)
        tc.assertEqual(sgf.Sgf_game.from_bytes(data).get_root().get("PB"),
                       "José")

def test_split_collection(tc):
    """Splitting a two-game collection should write two files."""
    with scratch_dir() as tmp:
        source = Path(tmp) / "collection.sgf"
        parts = []
        for name in ("First", "Second"):
            game = sgf.Sgf_game(size=9)
            game.get_root().set("PB", name)
            game.extend_main_sequence().set_move("b", (2, 2))
            parts.append(game.serialise())
        source.write_bytes(b"".join(parts))
        target_dir = Path(tmp) / "out_files"

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(source)
                await pilot.pause()
                tc.assertEqual(app.game_count, 2)
                app.current = ("split", "split", "Output directory", "")
                app.query_one("#param-input").value = str(target_dir)
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

        tc.assertTrue(target_dir.is_dir())
        names = sorted(p.name for p in target_dir.iterdir())
        tc.assertEqual(names, ["collection_1.sgf", "collection_2.sgf"])

def test_bad_file_is_handled(tc):
    """An unparseable file should be reported, not raise."""
    with scratch_dir() as tmp:
        bad = Path(tmp) / "bad.sgf"
        bad.write_bytes(b"this is not an SGF file")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(bad)
                await pilot.pause()
                tc.assertIs(app.game, None)
                # Operations should refuse politely rather than fail.
                app.current = ("info", "info", None, "")
                app.run_current_operation()
                await pilot.pause()
        _run(scenario())

def test_save_writes_back(tc):
    """The save operation should write the game back to its own file."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                app.game.get_root().set("EV", "Edited in the app")
                app.action_save()
                await pilot.pause()
        _run(scenario())

        reloaded = sgf.Sgf_game.from_bytes(path.read_bytes())
        tc.assertEqual(reloaded.get_root().get("EV"), "Edited in the app")

def test_operation_failure_is_visible(tc):
    """An operation that raises must report it, not fail silently.

    This is a regression test: a bug in an operation used to be swallowed, so
    the app appeared to do nothing at all.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()

                def broken():
                    raise RuntimeError("deliberate failure")

                app.op_info = broken
                app.current = ("info", "info", None, "")
                app.run_current_operation()
                await pilot.pause()
                shown = _text_of(app, "#info-view")
                tc.assertIn("deliberate failure", shown)
                # The app must still be alive and usable.
                tc.assertTrue(app.is_running)
        _run(scenario())

def test_explorer_filters_to_sgf(tc):
    """The explorer should list .sgf files but ignore other files."""
    with scratch_dir() as tmp:
        _write_sample(tmp)
        (Path(tmp) / "notes.txt").write_text("not an sgf file")
        (Path(tmp) / "sub").mkdir()
        _write_sample(tmp, name="sub/other.sgf")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test() as pilot:
                await pilot.pause()
                await asyncio.sleep(0.2)
                await pilot.pause()
                tree = app.query_one("#explorer-tree")
                names = _tree_names(tree.root)
                tc.assertIn("sample.sgf", names)
                tc.assertIn("sub", names)
                tc.assertNotIn("notes.txt", names)
        _run(scenario())

def _tree_names(node):
    names = []
    for child in node.children:
        names.append(str(child.label))
        names.extend(_tree_names(child))
    return names
