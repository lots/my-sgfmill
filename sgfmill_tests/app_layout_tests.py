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

from sgfmill import ascii_boards
from sgfmill import sgf


_ROOT = str(Path(__file__).resolve().parent.parent)


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
    # (2, 3) is off the main diagonal on purpose: a stone on the diagonal looks
    # the same under a clockwise turn as under a vertical flip, so the four
    # transformations would not be distinguishable.
    game.extend_main_sequence().set_move("b", (2, 3))
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

def test_transform_actions_preview_the_result(tc):
    """Selecting a flip or turn should show the board it would produce.

    The point of these four actions is what the board becomes, so the result is
    shown as soon as the action is selected; Run then only saves it.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                original = _text_of(app, "#board-view")

                # Turn the board a quarter-turn clockwise. The sample's black
                # stone is at (2, 3), D3; clockwise that is column 5 of row 2,
                # which is C6.
                _choose(app, [o[0] for o in app.OPERATIONS].index("rotate_cw"))
                await pilot.pause()
                preview = _text_of(app, "#board-view")
                tc.assertNotEqual(preview, original)
                tc.assertIn("PREVIEW", preview)
                tc.assertIn("clockwise", preview)
                # Row index 5 shows as row 6 (the 9x9 diagram is numbered down
                # from 9), at column C.
                tc.assertIn("6  .  .  #  .  .  .  .  .  .", preview)
                # Nothing has been written yet, and the game is unchanged.
                tc.assertFalse(list(Path(tmp).glob("*-rotate_cw.sgf")))
                _, plays = _plays(app.game)
                tc.assertEqual(plays[0], ("b", (2, 3)))

                # An action that is not a transformation shows the plain board.
                app._set_action([o[0] for o in app.OPERATIONS].index("info"))
                await pilot.pause()
                tc.assertNotIn("PREVIEW", _text_of(app, "#board-view"))
        _run(scenario())

def test_every_transform_has_a_preview(tc):
    """All four flip/turn actions preview, and each gives a different board."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                boards = {}
                for identifier in ("rotate_cw", "rotate_acw", "flip_v",
                                   "flip_h"):
                    index = [o[0] for o in app.OPERATIONS].index(identifier)
                    _choose(app, index)
                    await pilot.pause()
                    shown = _text_of(app, "#board-view")
                    tc.assertIn("PREVIEW", shown,
                                "%s did not preview" % identifier)
                    boards[identifier] = shown
                # Four different transformations of one position. (The stone is
                # on the main diagonal, which is why clockwise and anticlockwise
                # still differ from each other and from the flips.)
                tc.assertEqual(len(set(boards.values())), 4)
        _run(scenario())

def test_run_saves_the_transformed_board(tc):
    """Run should write the previewed board, and never over the target."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)
        original_bytes = path.read_bytes()

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                _choose(app, [o[0] for o in app.OPERATIONS].index("rotate_cw"))
                await pilot.pause()
                target = Path(app.query_one("#param-input").value)
                app.run_current_operation()
                await pilot.pause()
                tc.assertTrue(target.exists())
                # The saved file holds the transformed position: the stone
                # starts at (2, 3), and a quarter turn clockwise takes it to
                # (5, 2).
                saved = sgf.Sgf_game.from_bytes(target.read_bytes())
                _, plays = _plays(saved)
                tc.assertEqual(plays[0], ("b", (5, 2)))
                # ...and the target is untouched.
                tc.assertEqual(path.read_bytes(), original_bytes)

                # Asking to write over the target is refused, in place of
                # silently turning the file the user opened.
                app.query_one("#param-input").value = "-"
                app.run_current_operation()
                await pilot.pause()
                tc.assertEqual(path.read_bytes(), original_bytes)
        _run(scenario())


def _plays(game):
    from sgfmill import sgf_moves
    return sgf_moves.get_setup_and_moves(game)


def test_explorer_can_go_up_a_folder(tc):
    """The explorer should offer '..' and follow it to the parent folder.

    The tree is rooted at one directory, so without this there is no way to
    reach anything above the directory the app was started on.
    """
    with scratch_dir() as tmp:
        inner = Path(tmp) / "inner"
        inner.mkdir()
        _write_sample(str(inner), name="deep.sgf")
        _write_sample(tmp, name="shallow.sgf")

        async def scenario():
            app = SgfToolkitApp(str(inner))
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                tree = app.query_one("#explorer-tree")
                start = Path(tree.path)
                tc.assertEqual(start, inner.resolve())
                # The parent link is offered, with the parent's path.
                entry = _node_named(tree, "..")
                tc.assertIsNotNone(entry, "no '..' entry in the explorer")
                tc.assertEqual(entry.data.path, start.parent)

                # Selecting it re-roots the tree one level up.
                app.action_focus_explorer()
                await pilot.pause()
                for _ in range(len(tree.root.children) + 1):
                    await pilot.press("down")
                await pilot.pause()
                tc.assertEqual(str(tree.cursor_node.label), "..")
                await pilot.press("enter")
                await pilot.pause()
                tc.assertEqual(Path(tree.path), start.parent)
                # The listing is now the parent's, and it can go up again.
                tc.assertIsNotNone(_node_named(tree, ".."))
        _run(scenario())

def test_explorer_backspace_goes_up(tc):
    """Backspace should do the same as following '..'."""
    with scratch_dir() as tmp:
        inner = Path(tmp) / "inner"
        inner.mkdir()

        async def scenario():
            app = SgfToolkitApp(str(inner))
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                tree = app.query_one("#explorer-tree")
                start = Path(tree.path)
                app.action_focus_explorer()
                await pilot.pause()
                await pilot.press("backspace")
                await pilot.pause()
                tc.assertEqual(Path(tree.path), start.parent)
                # ...and the label above the tree keeps up.
                label = _text_of(app, "#explorer-dir")
                tc.assertIn(str(start.parent), label)
        _run(scenario())

def test_explorer_has_no_parent_at_the_top(tc):
    """At the top of a filesystem there is no parent to offer."""
    anchor = Path(_ROOT).anchor          # 'C:\\' on Windows, '/' elsewhere
    async def scenario():
        app = SgfToolkitApp(anchor)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            tree = app.query_one("#explorer-tree")
            tc.assertEqual(Path(tree.path), Path(anchor))
            tc.assertIsNone(_node_named(tree, ".."),
                            "'..' should not be offered at the top")
    _run(scenario())


def _node_named(tree, label):
    """Find a node by its label, anywhere in the tree."""
    pending = [tree.root]
    while pending:
        node = pending.pop()
        if str(node.label) == label:
            return node
        pending.extend(node.children)
    return None


def _highlighted_index(list_view):
    """Which entry of a ListView is highlighted, or None."""
    child = list_view.highlighted_child
    if child is None:
        return None
    return list_view.children.index(child)


def test_selecting_a_flip_applies_it_once(tc):
    """A flip must be applied once per choice, however it is chosen.

    Choosing an entry fires two events -- the entry is highlighted, then
    selected -- so applying the transformation on both flipped the board twice
    and a "flip" was a no-op. Applying on the choice alone makes each choice
    exactly one flip, and choosing again flips back.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("flip_v")
                original = _position_of(app)
                list_view = app.query_one("#operations")
                list_view.focus()
                await pilot.pause()

                # (a) arrow onto the entry: that only looks, it applies nothing.
                while _highlighted_index(list_view) != index:
                    await pilot.press("down")
                    await pilot.pause()
                await pilot.pause()
                tc.assertEqual(app.pending_transforms, [],
                               "moving the highlight applied a flip")

                # (b) choose it by mouse: exactly one application.
                await pilot.click(list_view.children[index])
                await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 1,
                               "a mouse click applied it %d times"
                               % len(app.pending_transforms))
                mirrored = _position_of(app)
                tc.assertNotEqual(mirrored, original)
                tc.assertIn("vertical flip",
                            _text_of(app, "#board-view").splitlines()[0])

                # (c) choose it again: a second application, back to the
                #     original board. This is what makes a flip a flip.
                await pilot.click(list_view.children[index])
                await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 2,
                               "the second click did not apply it again")
                tc.assertEqual(_position_of(app), original,
                               "two flips did not return to the original")

                # (d) running it saves what is on screen -- which is now the
                #     original board, and the log says so.
                app.run_current_operation()
                await pilot.pause()
                tc.assertEqual(app.pending_transforms, [])
        _run(scenario())

def test_choosing_a_flip_twice_returns_to_the_original(tc):
    """Two choices of a flip cancel out, and that is what gets saved."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                _, before = _plays(app.game)
                original = _position_of(app)
                index = [o[0] for o in app.OPERATIONS].index("flip_v")
                tc.assertEqual(len(app.pending_transforms), 0)
                _choose(app, index)
                await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 1)
                tc.assertNotEqual(_position_of(app), original)
                _choose(app, index)
                await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 2)
                tc.assertEqual(_position_of(app), original,
                               "two flips did not return to the original")
                # Saving that writes the file's own position, and says so.
                target = Path(app.query_one("#param-input").value)
                app.run_current_operation()
                await pilot.pause()
                tc.assertTrue(target.exists())
                _, saved = _plays(sgf.Sgf_game.from_bytes(target.read_bytes()))
                tc.assertEqual(saved, before,
                               "two flips should save the original position")
                tc.assertIn("unchanged", _text_of(app, "#notes-view"))
        _run(scenario())

def test_a_saved_flip_is_mirrored_once(tc):
    """The saved file must hold a single mirror image, not the original."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                # The sample's black stone is at (2, 3) on a 9x9 board;
                # mirrored vertically it becomes (6, 3).
                _, plays = _plays(app.game)
                tc.assertEqual(plays[0], ("b", (2, 3)))

                index = [o[0] for o in app.OPERATIONS].index("flip_v")
                list_view = app.query_one("#operations")
                list_view.focus()
                await pilot.pause()
                while _highlighted_index(list_view) != index:
                    await pilot.press("down")
                    await pilot.pause()
                await pilot.pause()
                # Choosing it by mouse applies one flip.
                await pilot.click(list_view.children[index])
                await pilot.pause()
                target = Path(app.query_one("#param-input").value)
                app.run_current_operation()
                await pilot.pause()
                tc.assertTrue(target.exists())
                _, saved = _plays(sgf.Sgf_game.from_bytes(target.read_bytes()))
                tc.assertEqual(saved[0], ("b", (6, 3)),
                               "the saved board is not a single mirror image")
        _run(scenario())


def test_transform_output_names_say_what_they_do(tc):
    """Each transformation should suggest a name matching its own action.

    All four suggested '-rotate_cw', so turning a board anticlockwise and
    flipping it both offered a file called '-rotate_cw'.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                templates = [(o[0], o[3]) for o in app.OPERATIONS
                             if o[0] in ("rotate_cw", "rotate_acw", "flip_v",
                                         "flip_h")]
                suffixes = [suffix for _identifier, suffix in templates]
                tc.assertEqual(len(set(suffixes)), len(suffixes),
                               "two transformations share a name: %s"
                               % (templates,))
                # The suggested name follows the action that is selected.
                for identifier, suffix in templates:
                    app._set_action([o[0] for o in app.OPERATIONS]
                                    .index(identifier))
                    await pilot.pause()
                    suggested = Path(app.query_one("#param-input").value).name
                    tc.assertEqual(suggested, path.stem + suffix + ".sgf",
                                   "%s suggested %s" % (identifier, suggested))
        _run(scenario())


def _choose(app, index):
    """Choose an action the way a user does: this is what applies a flip."""
    app._set_action(index)
    app._preview_transform(app.current[0])

def _position_of(app):
    """The board diagram currently shown, without the caption line."""
    text = _text_of(app, "#board-view")
    return text.split("\n", 1)[1] if "\n" in text else ""


_PANES = ("#explorer", "#operations-pane", "#game-tree-pane")
_PANE_FOCUS = {"#explorer": "#explorer-tree",
               "#operations-pane": "#operations",
               "#game-tree-pane": "#game-tree"}


def _width(app, selector):
    return app.query_one(selector).region.width


def _row_total(app):
    return sum(_width(app, s) for s in _PANES + ("#results",))


def test_panes_can_be_resized(tc):
    """Each panel across the top row should be width-adjustable.

    The panels share the window, so widening one takes the space from the
    results panel, which is whatever is left over.
    """
    with scratch_dir() as tmp:
        _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 40)) as pilot:
                await pilot.pause()
                for pane in _PANES:
                    app.query_one(_PANE_FOCUS[pane]).focus()
                    await pilot.pause()
                    before = _width(app, pane)
                    await pilot.press("ctrl+right")
                    await pilot.pause()
                    tc.assertEqual(_width(app, pane), before + app.PANE_STEP,
                                   "%s did not widen" % pane)
                    await pilot.press("ctrl+left")
                    await pilot.pause()
                    tc.assertEqual(_width(app, pane), before,
                                   "%s did not go back" % pane)
                    tc.assertEqual(_row_total(app), 150)   # still fills it
                # Widening a panel takes the space from the results panel.
                app.query_one("#explorer-tree").focus()
                await pilot.pause()
                results_before = _width(app, "#results")
                await pilot.press("ctrl+right")
                await pilot.pause()
                tc.assertEqual(_width(app, "#results"),
                               results_before - app.PANE_STEP)
        _run(scenario())

def test_pane_resize_is_bounded(tc):
    """A panel can't be squeezed away, or pushed past the window."""
    with scratch_dir() as tmp:
        _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 40)) as pilot:
                await pilot.pause()
                for pane in _PANES:
                    app.query_one(_PANE_FOCUS[pane]).focus()
                    await pilot.pause()
                    for _ in range(20):
                        app.action_resize_left()
                    await pilot.pause()
                    tc.assertEqual(_width(app, pane), app.PANE_MIN_WIDTH,
                                   "%s went below its minimum" % pane)
                    for _ in range(40):
                        app.action_resize_right()
                    await pilot.pause()
                    # The results panel keeps its own minimum...
                    tc.assertEqual(_width(app, "#results"),
                                   app.RESULTS_MIN_WIDTH)
                    # ...and the row still fits the window exactly.
                    tc.assertEqual(_row_total(app), 150)
                    for _ in range(40):        # put it back
                        app.action_resize_left()
                    await pilot.pause()
        _run(scenario())

def test_resize_without_a_panel_says_so(tc):
    """Resizing with the focus outside the panels must not guess."""
    with scratch_dir() as tmp:
        _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 40)) as pilot:
                await pilot.pause()
                app.query_one("#message-bar").focus()
                await pilot.pause()
                before = _width(app, "#explorer")
                app.action_resize_right()
                await pilot.pause()
                tc.assertEqual(_width(app, "#explorer"), before)
                # ...and the parameter box counts as part of the actions
                # panel, since it sits inside it.
                app.query_one("#param-input").focus()
                await pilot.pause()
                before = _width(app, "#operations-pane")
                app.action_resize_right()
                await pilot.pause()
                tc.assertEqual(_width(app, "#operations-pane"),
                               before + app.PANE_STEP)
        _run(scenario())


def test_show_tree_lists_the_whole_game(tc):
    """'Show tree' should list every node, including variations."""
    with scratch_dir() as tmp:
        path = Path(tmp) / "branches.sgf"
        # Root, two main-line moves, then two variations off the second.
        path.write_bytes(
            b"(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]PW[White]"
            b";B[cg];W[gc](;B[gg])(;B[cc];W[gg]))")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 46)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("tree")
                app._set_action(index)
                app.run_current_operation()
                await pilot.pause()
                tree = app.query_one("#game-tree")
                labels = _tree_labels(tree.root)
                # One entry per SGF node: the root (showing its properties)
                # plus five moves -- three on the main line and the two that
                # begin the variations.
                tc.assertEqual(len(labels), 6, labels)
                # The root shows the properties a reader cares about, not
                # the bookkeeping ones (FF, GM, SZ, CA).
                tc.assertEqual(labels[0], "PB PW")
                for expected in ("B C3", "W G7", "B G3", "B C7", "W G3"):
                    tc.assertIn(expected, labels)
        _run(scenario())

def test_tree_click_shows_that_position(tc):
    """Selecting a node should draw the board that node leads to.

    Each entry is checked against the position computed independently from the
    path through the tree, which is what makes the feature trustworthy.
    """
    with scratch_dir() as tmp:
        path = Path(tmp) / "positions.sgf"
        # A pass and setup stones as well, to exercise both.
        path.write_bytes(
            b"(;FF[4]GM[1]CA[UTF-8]SZ[9]AB[aa]AW[ii]PB[Black]"
            b";B[cg];W[];B[gc](;W[gg])(;W[cc];B[gg]))")

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 46)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("tree")
                app._set_action(index)
                app.run_current_operation()
                await pilot.pause()
                tree = app.query_one("#game-tree")
                checked = 0
                for node in _tree_nodes(tree.root):
                    if node.data is None:
                        continue
                    # Selecting posts NodeSelected, which the app handles.
                    tree.select_node(node)
                    await pilot.pause()
                    shown = _text_of(app, "#board-view")
                    want = _diagram_for_path(node.data)
                    tc.assertIn(want, shown,
                                "wrong position at %s" % node.label)
                    # The caption says where the position is.
                    tc.assertIn(str(node.label), shown.splitlines()[0])
                    checked += 1
                tc.assertEqual(checked, 6)
                # ...and the Board tab is the one showing it.
                tc.assertEqual(app.query_one("TabbedContent").active,
                               "tab-board")
        _run(scenario())

def test_tree_entry_for_the_root_is_safe(tc):
    """The tree's own root entry has no SGF node; selecting it must not fail."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(150, 46)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = [o[0] for o in app.OPERATIONS].index("tree")
                app._set_action(index)
                app.run_current_operation()
                await pilot.pause()
                tree = app.query_one("#game-tree")
                before = _text_of(app, "#board-view")
                tree.select_node(tree.root)
                await pilot.pause()
                # Nothing breaks, and the board is left alone.
                tc.assertEqual(_text_of(app, "#board-view"), before)
        _run(scenario())


def _tree_nodes(node):
    """Every node of a Textual Tree, depth first."""
    found = [node]
    for child in node.children:
        found.extend(_tree_nodes(child))
    return found


def _tree_labels(node):
    return [str(n.label) for n in _tree_nodes(node)]


def _diagram_for_path(sgf_node):
    """The board diagram for a node, computed from its ancestors.

    Deliberately a separate implementation from the app's: it walks the
    ancestors, applies setup stones and replays the moves, so a mistake in the
    app's version shows up as a difference rather than agreeing with it.
    """
    from sgfmill import ascii_boards, boards, sgf_properties
    chain = []
    walker = sgf_node
    while walker is not None:
        chain.append(walker)
        walker = walker.parent
    chain.reverse()
    side = chain[0].owner.get_size()
    board = boards.Board(side)
    board.apply_setup(*chain[0].get_setup_stones())
    for node in chain[1:]:
        board.apply_setup(*node.get_setup_stones())
        colour, raw = node.get_raw_move()
        if colour and raw:
            move = sgf_properties.interpret_go_point(raw, side)
            board.play(move[0], move[1], colour)
    return ascii_boards.render_board(board)


def test_transformations_compose_into_a_cycle(tc):
    """Applying a flip twice, or a turn four times, returns to the original.

    Transformations accumulate in the preview, so the cycle can be seen closing
    on screen: two flips cancel, and four quarter-turns come full circle.
    """
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = {o[0]: i for i, o in enumerate(app.OPERATIONS)}
                original = _position_of(app)

                for identifier, times in (("flip_v", 2), ("flip_h", 2),
                                          ("rotate_cw", 4), ("rotate_acw", 4)):
                    # Selecting the action applies it once...
                    _choose(app, index[identifier])
                    await pilot.pause()
                    tc.assertEqual(len(app.pending_transforms), 1)
                    tc.assertNotEqual(_position_of(app), original,
                                      "%s: first application changed nothing"
                                      % identifier)
                    # ...and each further application composes with it.
                    for count in range(2, times + 1):
                        app.apply_transform_again()
                        await pilot.pause()
                        tc.assertEqual(len(app.pending_transforms), count)
                    # A full cycle is back where we started.
                    tc.assertEqual(_position_of(app), original,
                                   "%s applied %d times is not the identity"
                                   % (identifier, times))
                    caption = _text_of(app, "#board-view").splitlines()[0]
                    tc.assertIn("%d x " % times, caption)
        _run(scenario())

def test_partial_transformations_are_not_the_identity(tc):
    """One flip, or three turns, must not look like the original board."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = {o[0]: i for i, o in enumerate(app.OPERATIONS)}
                original = _position_of(app)
                for identifier, times in (("flip_v", 1), ("flip_h", 1),
                                          ("rotate_acw", 1)):
                    _choose(app, index[identifier])
                    await pilot.pause()
                    for _ in range(times - 1):
                        app.apply_transform_again()
                        await pilot.pause()
                    tc.assertNotEqual(_position_of(app), original,
                                      "%s x %d should not be the identity"
                                      % (identifier, times))
                # Three quarter-turns are also not the identity.
                _choose(app, index["rotate_cw"])
                await pilot.pause()
                app.apply_transform_again()
                app.apply_transform_again()
                await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 3)
                tc.assertNotEqual(_position_of(app), original,
                                  "rotate_cw x 3 should not be the identity")
        _run(scenario())

def test_run_saves_the_composed_result(tc):
    """Run saves the accumulated transformation, not just the last one."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                index = {o[0]: i for i, o in enumerate(app.OPERATIONS)}

                # Two clockwise turns = a half turn: (2, 3) becomes (6, 5).
                _choose(app, index["rotate_cw"])
                await pilot.pause()
                app.apply_transform_again()
                await pilot.pause()
                target = Path(app.query_one("#param-input").value)
                app.run_current_operation()
                await pilot.pause()
                _, plays = _plays(sgf.Sgf_game.from_bytes(target.read_bytes()))
                tc.assertEqual(plays[0], ("b", (6, 5)))
                # Saving clears the preview, so the next action starts fresh.
                tc.assertEqual(app.pending_transforms, [])

                # A full cycle saves the original position, and says so. The
                # first output is removed first, so this save lands on the
                # suggested name rather than a collision-avoiding one.
                target.unlink()
                _choose(app, index["rotate_cw"])
                await pilot.pause()
                for _ in range(3):
                    app.apply_transform_again()
                    await pilot.pause()
                tc.assertEqual(len(app.pending_transforms), 4)
                target2 = Path(app.query_one("#param-input").value)
                tc.assertEqual(target2, target)
                app.run_current_operation()
                await pilot.pause()
                _, plays2 = _plays(
                    sgf.Sgf_game.from_bytes(target2.read_bytes()))
                tc.assertEqual(plays2[0], ("b", (2, 3)))
                tc.assertIn("full cycle", _text_of(app, "#notes-view"))
        _run(scenario())

def test_apply_again_needs_a_transform_action(tc):
    """Pressing 'apply again' on anything else should change nothing."""
    with scratch_dir() as tmp:
        path = _write_sample(tmp)

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                app.load_file(path)
                await pilot.pause()
                app._set_action([o[0] for o in app.OPERATIONS].index("info"))
                await pilot.pause()
                app.apply_transform_again()
                await pilot.pause()
                tc.assertEqual(app.pending_transforms, [])
        _run(scenario())


def _reference_board(data):
    """The board the library produces for some SGF data."""
    from sgfmill import sgf_moves
    game = sgf.Sgf_game.from_bytes(data)
    board, plays = sgf_moves.get_setup_and_moves(game)
    for colour, move in plays:
        if move is not None:
            board.play(move[0], move[1], colour)
    return board


def test_board_matches_the_library(tc):
    """The board view must equal the position the library computes.

    A correctness check rather than a layout one: the stones drawn must be
    exactly what applying the file's moves gives, including for positions where
    the number of moves and the number of stones differ.
    """
    cases = {
        "plain.sgf": b"(;FF[4]GM[1]SZ[9];B[cg];W[gc];B[gg];W[cc])",
        # A pass places no stone, so four moves leave three stones.
        "pass.sgf": b"(;FF[4]GM[1]SZ[9];B[cg];W[];B[gg];W[cc])",
        # A capture removes a stone.
        "capture.sgf": b"(;FF[4]GM[1]SZ[9];W[ee];B[de];B[fe];B[ed];B[ef])",
        # Setup stones are on the board before any move.
        "setup.sgf": b"(;FF[4]GM[1]SZ[9]AB[aa][bb];B[cg];W[gc])",
        # A pass and a capture together.
        "both.sgf": (b"(;FF[4]GM[1]SZ[9]AB[dd];W[ee];B[de];B[fe];B[ed];"
                     b"B[ef];W[];B[cc])"),
    }
    with scratch_dir() as tmp:
        paths = {}
        for name, data in cases.items():
            path = Path(tmp) / name
            path.write_bytes(data)
            paths[name] = path

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                for name, path in sorted(paths.items()):
                    app.load_file(path)
                    await pilot.pause()
                    shown = _text_of(app, "#board-view")
                    diagram = ascii_boards.render_board(
                        _reference_board(path.read_bytes()))
                    tc.assertIn(diagram, shown,
                                "%s: board view does not match the library"
                                % name)
        _run(scenario())

def test_position_summary_explains_the_counts(tc):
    """The caption must not claim more stones than there are.

    "4 moves" beside three stones looks like a bug, so the caption says how
    many stones the moves produced, and mentions passes and setup stones.
    """
    with scratch_dir() as tmp:
        cases = {
            "plain.sgf": (b"(;FF[4]GM[1]SZ[9];B[cg];W[gc];B[gg];W[cc])",
                          ["4 moves", "4 stones"]),
            "pass.sgf": (b"(;FF[4]GM[1]SZ[9];B[cg];W[];B[gg];W[cc])",
                         ["4 moves", "1 pass", "3 stones"]),
            "setup.sgf": (b"(;FF[4]GM[1]SZ[9]AB[aa][bb];B[cg];W[gc])",
                          ["2 moves", "2 stones", "2 setup stones"]),
        }
        paths = {}
        for name, (data, _expected) in cases.items():
            path = Path(tmp) / name
            path.write_bytes(data)
            paths[name] = path

        async def scenario():
            app = SgfToolkitApp(tmp)
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                for name, path in sorted(paths.items()):
                    app.load_file(path)
                    await pilot.pause()
                    caption = _text_of(app, "#board-view").splitlines()[0]
                    for fragment in cases[name][1]:
                        tc.assertIn(fragment, caption,
                                    "%s: caption was %r" % (name, caption))
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
