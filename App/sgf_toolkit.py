"""A small Textual front end for the sgfmill library.

Run it with::

    python App/run_sgf_toolkit.py [directory]

The window is organised around the order you work in:

    1. Select a target   -- the EXPLORER, on the left
    2. Choose an action  -- the OPERATIONS list, on the left
    3. See the result    -- the tabs, in the middle

and a HELP pane along the bottom describes whichever action is highlighted, so
the list can stay short and you don't have to guess.

Each action is a thin wrapper around one of the library's public functions; see
OPERATIONS for the mapping.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from rich.console import Group
from rich.table import Table
from rich.text import Text

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from sgfmill import ascii_boards
from sgfmill import sgf
from sgfmill import sgf_encoding
from sgfmill import sgf_grammar
from sgfmill import sgf_moves
from sgfmill import sgf_normalise
from sgfmill import sgf_transform
from sgfmill.common import format_vertex


APP_TITLE = "SGF Toolkit"


class SgfFileExplorer(DirectoryTree):
    """A directory tree showing folders and .sgf files, and little else.

    Directories are kept so you can navigate. Files are restricted to .sgf,
    because nothing else can be used by this app, and hidden entries are left
    out so that .git and __pycache__ stay out of the way.
    """

    def filter_paths(self, paths):
        def wanted(path):
            if path.name.startswith("."):
                return False
            return path.is_dir() or path.suffix.lower() == ".sgf"
        return [path for path in paths if wanted(path)]


class MessageBar(Static):
    """The bottom message pane: one line about the highlighted action.

    It says what the action does and, when the action takes a parameter, what
    the parameter means and where the result will go -- so the action list can
    stay short and you don't have to guess. The text lives here, next to
    nothing else, so it is easy to keep up to date; a test checks that every
    action has an entry.
    """

    #: identifier -> (what it does, what the parameter means, what you get)
    #: Kept short: the pane is two lines, and the target's name is prepended.
    HELP = {
        "board": (
            "Draw the position on an ASCII board.",
            "Move number: position BEFORE that move.",
            "Board tab.",
        ),
        "info": (
            "Summarise the game: size, komi, handicap, players, result.",
            None,
            "Info tab.",
        ),
        "properties": (
            "List every node of the tree, with its properties.",
            None,
            "Info tab.",
        ),
        "moves": (
            "List the moves of the leftmost variation.",
            None,
            "Moves tab.",
        ),
        "check": (
            "Report properties FF[4] does not define for Go.",
            None,
            "Info tab; nothing changes.",
        ),
        "clean": (
            "Remove those non-standard properties.",
            "Output file: where to write.",
            "New .sgf file.",
        ),
        "encoding": (
            "Report the encoding the file is really in.",
            None,
            "Info tab.",
        ),
        "to_utf8": (
            "Rewrite the file as UTF-8.",
            "Output file: where to write.",
            "New .sgf file.",
        ),
        "rotate_cw": (
            "Preview the board turned 90 degrees clockwise.",
            "Output file: where Run saves it.",
            None,
        ),
        "rotate_acw": (
            "Preview the board turned 90 degrees anticlockwise.",
            "Output file: where Run saves it.",
            None,
        ),
        "flip_v": (
            "Preview the board flipped vertically (left/right swap).",
            "Output file: where Run saves it.",
            None,
        ),
        "flip_h": (
            "Preview the board flipped horizontally (top/bottom swap).",
            "Output file: where Run saves it.",
            None,
        ),
        "split": (
            "Split a multi-game file into one file per game.",
            "Output directory: written into.",
            "One file per game.",
        ),
        "save": (
            "Write the game back to the file it came from.",
            None,
            "The only action that changes it.",
        ),
    }

    def update_message(self, identifier, target=None):
        """Describe an action, as a single line.

        'target' is the name of the selected file, if there is one; it is
        included so that the message says what the action will be applied to.
        """
        entry = self.HELP.get(identifier)
        text = Text()
        if target:
            text.append(target, style="bold")
            text.append("  ")
        if entry is None:
            text.append("No help available for this action.",
                        style="dim italic")
            self.update(text)
            return
        summary, parameter, result = entry
        text.append(summary)
        if parameter:
            text.append("  ")
            text.append(parameter, style="dim")
        if result:
            text.append("  ")
            text.append(result, style="dim")
        self.update(text)


class SgfToolkitApp(App):
    """Browse .sgf files and invoke sgfmill's functions on them."""

    CSS = """
    /* One row of three panels, side by side, filling the window. */
    #body { height: 1fr; }

    #explorer {
        width: 34;
        min-width: 24;
        border-right: solid $panel-lighten-2;
    }
    #explorer-heading, #operations-heading {
        background: $panel;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    #explorer-tree { height: 1fr; }
    #explorer-dir {
        padding: 0 1;
        height: 1;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }

    #operations-pane {
        width: 38;
        min-width: 26;
        border-right: solid $panel-lighten-2;
    }
    #operations { height: 1fr; }
    #params { height: auto; padding: 0 1; }
    #param-label {
        height: 3;
        content-align: left middle;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    #param-input { margin-bottom: 1; }
    #run { width: 100%; margin-bottom: 1; }

    #results { width: 1fr; }
    #target-bar {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    TabbedContent { height: 1fr; }
    #board-view, #info-view, #moves-view, #notes-view { padding: 0 1; }

    /* The bottom row: one message pane, full width. The text wraps onto the
       two lines it is given rather than being cut off. */
    #message-bar {
        height: 2;
        border-top: solid $panel-lighten-2;
        padding: 0 1;
        text-wrap: wrap;
        overflow: hidden;
    }
    """

    BINDINGS = [
        Binding("ctrl+j", "run", "Run action"),
        Binding("e", "focus_explorer", "Explorer"),
        Binding("a", "focus_operations", "Actions"),
        Binding("h", "toggle_help", "Help"),
        Binding("r", "reload", "Reload"),
        Binding("s", "save", "Save"),
        Binding("d", "go_to_directory", "Open dir"),
        Binding("ctrl+n", "refresh_explorer", "Refresh files"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = APP_TITLE

    # (identifier, label, prompt for the parameter, default value)
    # A prompt of None means the action has no parameter.
    OPERATIONS = [
        ("board",      "Show board position",         "Move number (blank = final)", ""),
        ("info",       "Show game information",        None, ""),
        ("properties", "List properties in the tree",  None, ""),
        ("moves",      "List moves",                   None, ""),
        ("check",      "Check for non-standard props", None, ""),
        ("clean",      "Clean non-standard -> file",   "Output file", "-clean"),
        ("to_utf8",    "Convert to UTF-8 -> file",     "Output file", ""),
        ("rotate_cw",  "Turn board 90 clockwise",      "Output file", "-rotate_cw"),
        ("rotate_acw", "Turn board 90 anticlockwise",  "Output file", "-rotate_cw"),
        ("flip_v",     "Flip board vertically",        "Output file", "-rotate_cw"),
        ("flip_h",     "Flip board horizontally",      "Output file", "-rotate_cw"),
        ("split",      "Split collection -> directory", "Output directory", "_files"),
        ("save",       "Save back to the file",        None, ""),
    ]

    #: The board transformations, and the words used for them in the caption.
    #: Selecting one of these actions previews the result; Run saves it.
    BOARD_TRANSFORMS = {
        "rotate_cw": (sgf_transform.ROTATE_CW, "clockwise turn"),
        "rotate_acw": (sgf_transform.ROTATE_ACW, "anticlockwise turn"),
        "flip_v": (sgf_transform.FLIP_VERTICAL, "vertical flip"),
        "flip_h": (sgf_transform.FLIP_HORIZONTAL, "horizontal flip"),
    }

    #: transformation -> the words used for it, for looking up a caption.
    BOARD_TRANSFORMS_BY_VALUE = {
        transformation: words
        for transformation, words in BOARD_TRANSFORMS.values()
    }

    def __init__(self, start_dir):
        super().__init__()
        self.start_dir = Path(start_dir).resolve()
        self.path = None
        self.raw = None
        self.encoding_result = None
        self.game = None
        self.game_count = 0
        self.current = self.OPERATIONS[0]

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # One row of three panels, side by side: target, actions, results.
        with Horizontal(id="body"):
            with Vertical(id="explorer"):
                yield Static("1  SELECT TARGET", id="explorer-heading")
                yield Static(str(self.start_dir), id="explorer-dir")
                yield SgfFileExplorer(str(self.start_dir), id="explorer-tree")
            with Vertical(id="operations-pane"):
                yield Static("2  SELECT ACTION", id="operations-heading")
                yield ListView(id="operations")
                with Vertical(id="params"):
                    yield Static("", id="param-label")
                    yield Input(placeholder="", id="param-input")
                    yield Button("Run", variant="primary", id="run")
            with Vertical(id="results"):
                yield Static("", id="target-bar")
                with TabbedContent(initial="tab-board"):
                    with TabPane("Board", id="tab-board"):
                        yield Static("", id="board-view")
                    with TabPane("Info", id="tab-info"):
                        yield Static("", id="info-view")
                    with TabPane("Moves", id="tab-moves"):
                        yield Static("", id="moves-view")
                    with TabPane("Notes", id="tab-notes"):
                        yield Static("", id="notes-view")
        # The bottom row: a single message pane.
        yield MessageBar(id="message-bar")
        yield Footer()

    def on_mount(self):
        self.sub_title = str(self.start_dir)
        listing = self.query_one("#operations", ListView)
        for _identifier, label, _prompt, _default in self.OPERATIONS:
            listing.append(ListItem(Label(label)))
        listing.focus()
        self._set_action(0)
        self._update_target_bar()
        self._placeholder("board-view",
                          "Choose an .sgf file in the EXPLORER on the left.")
        self._placeholder("info-view", "No file open.")
        self._placeholder("moves-view", "No file open.")
        self._placeholder("notes-view",
                          "Messages from actions appear here.")

    # -- small helpers -----------------------------------------------------

    def _placeholder(self, view_id, message):
        self.query_one("#" + view_id, Static).update(
            Text(message, style="italic dim"))

    def _set_view(self, view_id, renderable):
        self.query_one("#" + view_id, Static).update(renderable)

    def _note(self, message, style=None):
        notes = self.query_one("#notes-view", Static)
        lines = getattr(notes, "_sgf_lines", None)
        if lines is None:
            lines = []
        lines.append(Text(message, style=style))
        del lines[:-300]
        notes._sgf_lines = lines
        notes.update(Text("\n").join(lines))

    def _show(self, tab_id):
        self.query_one(TabbedContent).active = tab_id

    def _require_file(self):
        if self.game is None:
            self.notify("Choose an .sgf file in the explorer first.",
                        title="No target selected", severity="warning")
            return False
        return True

    def _set_action(self, index):
        if not 0 <= index < len(self.OPERATIONS):
            return
        self.current = self.OPERATIONS[index]
        identifier, _label, prompt, default = self.current
        input_widget = self.query_one("#param-input", Input)
        if prompt is None:
            self._set_parameter_prompt(None)
            input_widget.value = ""
            input_widget.disabled = True
        else:
            self._set_parameter_prompt(prompt)
            input_widget.disabled = False
            input_widget.value = self._default_parameter(identifier, default)
        self.query_one(MessageBar).update_message(
            identifier, self.path.name if self.path else None)
        # Show what a board transformation would do, before it is saved.
        self._update_preview(identifier)

    def _set_parameter_prompt(self, prompt):
        """Show which target the parameter applies to, and what is wanted."""
        label = self.query_one("#param-label", Static)
        text = Text()
        if self.path is not None:
            text.append(self.path.name, style="bold")
            text.append("  ")
        text.append(prompt if prompt else "(no parameters)",
                    style="" if prompt else "dim")
        label.update(text)

    def _default_parameter(self, identifier, default):
        if self.path is None:
            return str(default)
        source = Path(self.path)
        if identifier == "split":
            return str(source.with_name(source.stem + "_files"))
        if identifier in ("board", "to_utf8"):
            return ""
        # Suggest a new name; _output_path() avoids collisions.
        return str(source.with_name(source.stem + default + source.suffix))

    def _update_preview(self, identifier):
        """Draw the board that the selected action is about.

        The point of a flip or a turn is what the board becomes, so the result
        is shown as soon as the action is selected, and 'Run' then only has to
        save it. Selecting anything else puts the plain final position back, so
        a stale preview can't be mistaken for the file's contents.
        """
        if self.game is None:
            return
        if identifier in self.BOARD_TRANSFORMS:
            transformation, _words = self.BOARD_TRANSFORMS[identifier]
            self._show_board(transform=transformation)
        else:
            self._show_board()

    def _update_target_bar(self):
        """Describe the target, on one line above the result tabs."""
        bar = self.query_one("#target-bar", Static)
        if self.path is None:
            bar.update(Text("(no target selected — choose a file on the left)",
                            style="dim italic"))
            return
        text = Text()
        text.append("%d bytes" % len(self.raw))
        if self.game is not None:
            side = self.game.get_size()
            text.append("    %dx%d" % (side, side))
        text.append("    %d game%s" % (self.game_count,
                                       "" if self.game_count == 1 else "s"))
        if self.game_count > 1:
            text.append(" (first used)", style="yellow")
        if self.encoding_result is not None:
            result = self.encoding_result
            text.append("    %s" % result.encoding,
                        style="yellow" if result.mismatch
                        and not result.ascii_only else "")
        bar.update(text)

    # -- file loading ------------------------------------------------------

    @on(SgfFileExplorer.FileSelected)
    def _file_selected(self, event):
        self.load_file(event.path)

    def load_file(self, path):
        """Read and parse an .sgf file, making it the target."""
        path = Path(path)
        try:
            raw = path.read_bytes()
        except OSError as e:
            self.notify(str(e), title="Can't read file", severity="error")
            return
        self.path = path
        self.raw = raw
        self.encoding_result = None
        self.game = None
        self.game_count = 0

        try:
            self.game_count = len(sgf_grammar.parse_sgf_collection(raw))
        except ValueError as e:
            self.game_count = 0
            self._update_target_bar()
            self.notify("Not a usable SGF file: %s" % e,
                        title="Parse error", severity="error")
            return

        # Work out the character encoding, so comments and player names are
        # not displayed as mojibake.
        encoding = None
        try:
            self.encoding_result = sgf_encoding.detect_bytes(raw)
            encoding = self.encoding_result.encoding
        except sgf_encoding.SgfEncodingError:
            pass

        try:
            if encoding is None:
                self.game = sgf.Sgf_game.from_bytes(raw)
            else:
                self.game = sgf.Sgf_game.from_bytes(
                    raw, override_encoding=encoding)
        except (ValueError, LookupError) as e:
            self._update_target_bar()
            self.notify("Can't parse the file: %s" % e,
                        title="Parse error", severity="error")
            return

        self._update_target_bar()
        self._show_game_info()
        self._show_board()
        self._show_moves()
        # Refresh the parameter box, which may suggest a file name.
        self._set_action(self.query_one("#operations", ListView).index or 0)
        self._show("tab-board")
        message = "Opened %s" % path.name
        if self.game_count > 1:
            message += "  (%d games; only the first is used)" % self.game_count
        self._note(message)
        self.notify(message, title="Target selected")

    # -- running actions ---------------------------------------------------

    @on(ListView.Highlighted, "#operations")
    def _action_highlighted(self, event):
        if event.item is None:
            return
        self._set_action(self.query_one("#operations", ListView).index)

    @on(ListView.Selected, "#operations")
    def _action_selected(self, event):
        self._set_action(self.query_one("#operations", ListView).index)
        if self.current[2] is None:
            self.run_current_operation()
        else:
            self.query_one("#param-input", Input).focus()

    @on(Button.Pressed, "#run")
    def _run_pressed(self):
        self.run_current_operation()

    @on(Input.Submitted, "#param-input")
    def _param_submitted(self):
        self.run_current_operation()

    def action_run(self):
        self.run_current_operation()

    def run_current_operation(self):
        identifier = self.current[0]
        handler = getattr(self, "op_" + identifier, None)
        if handler is None:
            self.notify("Not implemented: %s" % identifier, severity="warning")
            return
        try:
            handler()
        except Exception as e:                 # noqa: BLE001
            # An action failing shouldn't take the app down, and it must be
            # visible: show it in the result pane as well as notifying, so a
            # failure can't pass unnoticed.
            import traceback
            detail = "%s failed:\n\n%s" % (identifier, traceback.format_exc())
            self._set_view("info-view", Text(detail, style="bold red"))
            self._show("tab-info")
            self._note("%s failed: %s" % (identifier, e), style="bold red")
            try:
                self.notify(str(e), title="Action failed", severity="error")
            except Exception:                  # noqa: BLE001
                pass

    def _parameter(self):
        return self.query_one("#param-input", Input).value.strip()

    # 1 -- board position
    def op_board(self):
        if not self._require_file():
            return
        answer = self._parameter()
        move_number = None
        if answer:
            try:
                move_number = int(answer)
            except ValueError:
                self.notify("Not a move number: %s" % answer,
                            severity="error")
                return
        self._show_board(move_number)
        self._show("tab-board")

    def _show_board(self, move_number=None, transform=None):
        """Draw a position, optionally after a board transformation.

        'transform' is one of the sgf_transform constants; it is applied to a
        copy of the game, so the target itself is not changed.
        """
        game = self.game
        if transform is not None:
            game = self._reparse()
            sgf_transform.transform_game(game, transform)
        try:
            board, plays = sgf_moves.get_setup_and_moves(game)
        except ValueError as e:
            self._set_view("board-view", Text(str(e), style="bold red"))
            return
        limit = len(plays) if move_number is None else max(0, move_number - 1)
        for colour, move in plays[:limit]:
            if move is None:
                continue
            try:
                board.play(move[0], move[1], colour)
            except ValueError:
                self._note("Stopped early: illegal move in the file.",
                           style="yellow")
                break
        caption = Text()
        caption.append(self.path.name, style="bold")
        if transform is not None:
            caption.append("   PREVIEW: %s"
                           % self.BOARD_TRANSFORMS_BY_VALUE[transform],
                           style="bold yellow")
            caption.append("   (Run saves it)", style="dim")
        elif move_number is None:
            caption.append("   final position, %d moves" % len(plays))
        else:
            caption.append("   before move %d" % move_number)
        self._set_view("board-view",
                       Text.assemble(caption, "\n\n",
                                     Text(ascii_boards.render_board(board))))
        if transform is not None:
            self._show("tab-board")
            self._note("Previewing the board %s (not saved yet)"
                       % self.BOARD_TRANSFORMS_BY_VALUE[transform])

    # 2 -- game information
    def op_info(self):
        if not self._require_file():
            return
        self._show_game_info()
        self._show("tab-info")

    def _show_game_info(self):
        root = self.game.get_root()
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold", justify="right")
        table.add_column()
        rows = [("File", str(self.path)),
                ("Games in file", str(self.game_count)),
                ("Board size", str(self.game.get_size()))]
        if self.encoding_result is not None:
            rows.append(("Encoding", str(self.encoding_result)))
        try:
            rows.append(("Komi", "%g" % self.game.get_komi()))
        except (KeyError, ValueError):
            pass
        try:
            handicap = self.game.get_handicap()
            if handicap is not None:
                rows.append(("Handicap", str(handicap)))
        except (KeyError, ValueError):
            pass
        for colour, label in (("b", "Black"), ("w", "White")):
            try:
                name = self.game.get_player_name(colour)
            except (KeyError, ValueError):
                continue
            if name:
                rows.append(("%s player" % label, name))
        for identifier, label in (("BR", "Black rank"), ("WR", "White rank"),
                                  ("RE", "Result"), ("RU", "Rules"),
                                  ("DT", "Date"), ("EV", "Event"),
                                  ("PC", "Place"), ("GN", "Game name")):
            try:
                if root.has_property(identifier):
                    rows.append((label, str(root.get(identifier))))
            except ValueError:
                pass
        rows.append(("Winner", str(self.game.get_winner() or "unknown")))
        for key, value in rows:
            table.add_row(str(key), value)
        self._set_view("info-view", table)

    # 3 -- properties in the tree
    def op_properties(self):
        if not self._require_file():
            return
        table = Table(show_edge=False, pad_edge=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Properties")
        count = 0
        for node in self._walk(self.game.get_root()):
            count += 1
            names = " ".join(sorted(node.get_raw_property_map()))
            table.add_row(str(count), names or "(none)")
        self._set_view("info-view", Group(
            Text("%d nodes (depth first, including variations)" % count),
            "",
            table))
        self._show("tab-info")

    def _walk(self, node):
        yield node
        for child in node:
            yield from self._walk(child)

    # 4 -- moves
    def op_moves(self):
        if not self._require_file():
            return
        self._show_moves()
        self._show("tab-moves")

    def _show_moves(self):
        try:
            _, plays = sgf_moves.get_setup_and_moves(self.game)
        except ValueError as e:
            self._set_view("moves-view", Text(str(e), style="bold red"))
            return
        table = Table(title="Moves (leftmost variation)",
                      show_edge=False, pad_edge=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Colour")
        table.add_column("Move")
        for number, (colour, move) in enumerate(plays, start=1):
            table.add_row(str(number),
                          "Black" if colour == "b" else "White",
                          "pass" if move is None else format_vertex(move))
        self._set_view("moves-view", table)

    # 5 -- check for non-standard properties
    def op_check(self):
        if not self._require_file():
            return
        report = sgf_normalise.check_game(self.game)
        if not report:
            self._set_view("info-view", Text(
                "No non-standard properties: this file only uses standard "
                "FF[4] properties for Go.", style="green"))
            self._note("%s: clean" % self.path.name, style="green")
        else:
            table = Table(show_edge=False, pad_edge=False)
            table.add_column("Property", style="bold yellow")
            table.add_column("Nodes", justify="right")
            for name in report.properties():
                table.add_row(name, str(len(report.findings[name])))
            self._set_view("info-view", Group(
                Text("Non-standard properties", style="bold yellow"),
                "",
                table))
            self._note("%s: %s" % (self.path.name, report), style="yellow")
        self._show("tab-info")

    # 6 -- clean and write
    def op_clean(self):
        if not self._require_file():
            return
        report = sgf_normalise.check_game(self.game)
        if not report:
            self.notify("Nothing to remove: the file is already clean.")
            self._note("%s: already clean" % self.path.name, style="green")
            return
        target = self._output_path()
        if target is None:
            return
        game = self._reparse()
        report = sgf_normalise.clean_game(game)
        self._write(target, game.serialise())
        self._note("%s: removed %s" % (self.path.name, report), style="green")

    # 7 -- report encoding
    def op_encoding(self):
        if not self._require_file():
            return
        result = self.encoding_result
        if result is None:
            self._set_view("info-view", Text(
                "The encoding could not be determined.", style="bold red"))
            self._show("tab-info")
            return
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold", justify="right")
        table.add_column()
        table.add_row("Detected", result.encoding)
        table.add_row("CA property", result.declared or "(none)")
        table.add_row("Differs", "yes" if result.mismatch else "no")
        table.add_row("ASCII only", "yes" if result.ascii_only else "no")
        table.add_row("Needs conversion",
                      "yes" if result.needs_conversion() else "no")
        self._set_view("info-view", table)
        self._note("%s: %s" % (self.path.name, result))
        self._show("tab-info")

    # 8 -- convert to UTF-8
    def op_to_utf8(self):
        if not self._require_file():
            return
        if self.encoding_result is not None and \
                not self.encoding_result.needs_conversion():
            self.notify("This file is already UTF-8.", title="Nothing to do")
            self._note("%s: already UTF-8" % self.path.name, style="green")
            return
        target = self._output_path()
        if target is None:
            return
        parsing_encoding = None
        if self.encoding_result is not None:
            parsing_encoding = self.encoding_result.encoding
        if parsing_encoding is None:
            game = self.game
        else:
            game = sgf.Sgf_game.from_bytes(
                self.raw, override_encoding=parsing_encoding)
        data = sgf_encoding.convert_game_to_utf8(game)
        self._write(target, data)
        self._note("%s -> %s (UTF-8)" % (self.path.name, target.name),
                   style="green")

    # 9-12 -- transforms. Selecting one previews the result on the Board tab;
    # running it saves that result (Run does not re-preview, and refuses to
    # write over the target, so the file you opened is never turned in place).
    def op_rotate_cw(self):
        self._transform("rotate_cw")

    def op_rotate_acw(self):
        self._transform("rotate_acw")

    def op_flip_v(self):
        self._transform("flip_v")

    def op_flip_h(self):
        self._transform("flip_h")

    def _transform(self, identifier):
        if not self._require_file():
            return
        transformation, description = self.BOARD_TRANSFORMS[identifier]
        target = self._output_path()
        if target is None:
            return
        if target == Path(self.path):
            self.notify("That would overwrite the file you opened. Give a "
                        "different output name, or use Save.",
                        title="Not written", severity="error")
            self._note("Refused to %s over the target file" % description,
                       style="bold red")
            return
        # Transforms modify a game in place, so work on a fresh parse and leave
        # the loaded game alone until the user saves.
        game = self._reparse()
        sgf_transform.transform_game(game, transformation)
        self._write(target, game.serialise())
        self._note("%s: %s -> %s" % (self.path.name, description, target.name),
                   style="green")

    # 13 -- split a collection
    def op_split(self):
        if not self._require_file():
            return
        if self.game_count < 2:
            self.notify("This file holds a single game; nothing to split.")
            return
        answer = self._parameter()
        if not answer:
            self.notify("Give a directory to write into.", severity="warning")
            return
        target_dir = Path(answer).expanduser()
        if not target_dir.is_absolute():
            target_dir = Path(self.path).parent / target_dir
        try:
            target_dir.mkdir()
        except FileExistsError:
            self.notify("%s already exists." % target_dir,
                        title="Not overwritten", severity="warning")
            return
        except OSError as e:
            self.notify(str(e), title="Can't create directory",
                        severity="error")
            return
        coarse_games = sgf_grammar.parse_sgf_collection(self.raw)
        source = Path(self.path)
        written = []
        for index, coarse in enumerate(coarse_games, start=1):
            game = sgf.Sgf_game.from_coarse_game_tree(coarse)
            game.get_root().add_comment_text(
                "Split from %s (game %d)" % (source.name, index))
            path = target_dir / ("%s_%d%s" % (source.stem, index,
                                              source.suffix))
            self._write(path, game.serialise(), quiet=True)
            written.append(path.name)
        self._note("%s: split into %d files in %s"
                   % (source.name, len(written), target_dir), style="green")
        self.notify("Wrote %d files." % len(written), title="Split complete")

    # 14 -- save
    def op_save(self):
        self.action_save()

    def action_save(self):
        if not self._require_file():
            return
        self._write(self.path, self.game.serialise())

    # -- writing and reloading ---------------------------------------------

    def _write(self, path, data, quiet=False):
        path = Path(path)
        with open(path, "wb") as f:
            f.write(data)
        if not quiet:
            self.notify("Wrote %s" % path.name, title="Saved")
        return path

    def _output_path(self):
        """Resolve the output path from the parameter box.

        An existing file is never overwritten: a numbered name is used
        instead, so a mistyped name can't destroy a file. Passing '-' writes
        back to the open file, which is how the Save action already behaves.
        """
        answer = self._parameter()
        if not answer:
            self.notify("Give an output file name.", severity="warning")
            return None
        if answer == "-":
            return Path(self.path)
        path = Path(answer).expanduser()
        if not path.is_absolute():
            path = Path(self.path).parent / path
        if path.exists() and path != Path(self.path):
            path = self._unused_name(path)
            self.notify("That name exists; writing %s instead." % path.name,
                        title="Not overwritten", severity="warning")
        return path

    @staticmethod
    def _unused_name(path):
        stem = path.stem
        for number in range(1, 1000):
            candidate = path.with_name("%s-%d%s" % (stem, number,
                                                    path.suffix))
            if not candidate.exists():
                return candidate
        return path

    def _reparse(self):
        """Parse the target again, using the detected encoding."""
        if self.encoding_result is None:
            return sgf.Sgf_game.from_bytes(self.raw)
        return sgf.Sgf_game.from_bytes(
            self.raw, override_encoding=self.encoding_result.encoding)

    # -- bindings ----------------------------------------------------------

    def action_reload(self):
        if self.path is None:
            self.notify("No file open.", severity="warning")
            return
        self.load_file(self.path)

    def action_focus_explorer(self):
        self.query_one("#explorer-tree").focus()

    def action_focus_operations(self):
        self.query_one("#operations").focus()

    def action_toggle_help(self):
        help_pane = self.query_one(MessageBar)
        help_pane.display = not help_pane.display

    def action_refresh_explorer(self):
        self.query_one("#explorer-tree").reload()
        self.notify("File list refreshed.")

    def action_go_to_directory(self):
        answer = self.query_one("#param-input", Input).value.strip()
        if not answer:
            self.notify("Type a directory in the parameter box, then press "
                        "Ctrl+N.", title="Open directory")
            return
        path = Path(answer).expanduser()
        if not path.is_dir():
            self.notify("%s is not a directory." % path, severity="error")
            return
        self.start_dir = path.resolve()
        self.sub_title = str(self.start_dir)
        self.query_one("#explorer-dir", Static).update(str(self.start_dir))
        explorer = self.query_one("#explorer-tree", SgfFileExplorer)
        explorer.path = self.start_dir
        explorer.reload()


def main(argv=None):
    """Run the application.

    The board is taken from the first command-line argument, or the current
    directory.

    Two environment variables are honoured, which is useful when there is no
    terminal to drive the app from (a test harness, or a build server):

    ``SGF_TOOLKIT_HEADLESS``
        Run with Textual's headless driver instead of a real terminal.
    ``SGF_TOOLKIT_EXIT_AFTER_STARTUP``
        Quit as soon as the layout is ready, instead of waiting for input.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    start_dir = argv[0] if argv else os.getcwd()
    app = SgfToolkitApp(start_dir)

    if os.environ.get("SGF_TOOLKIT_EXIT_AFTER_STARTUP"):
        async def auto_pilot(pilot):
            await pilot.pause()
            await pilot.press("q")
        app.run(headless=True, auto_pilot=auto_pilot)
    elif os.environ.get("SGF_TOOLKIT_HEADLESS"):
        app.run(headless=True)
    else:
        app.run()


if __name__ == "__main__":
    main()
