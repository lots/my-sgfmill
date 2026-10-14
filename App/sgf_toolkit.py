"""A small Textual front end for the sgfmill library.

Run it with::

    python run_sgf_toolkit.py [directory]

The layout is deliberately like a small editor: the operations and their
parameters on the left, a tabbed area of results in the middle, and a file
explorer on the right for choosing the |SGF| file to work on.

Each operation is a thin wrapper around one of the library's public functions;
see OPERATIONS for the mapping.
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


class SgfToolkitApp(App):
    """Browse .sgf files and invoke sgfmill's functions on them."""

    CSS = """
    #body { height: 1fr; }

    #operations-pane {
        width: 38;
        min-width: 30;
        border-right: solid $panel-lighten-2;
    }
    #operations-heading, #explorer-heading, #params-heading {
        background: $panel;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    #operations { height: 1fr; }
    #params { height: auto; padding: 0 1; }
    #param-label { color: $text-muted; padding-bottom: 0; }
    #param-input { margin-bottom: 1; }
    #file-details { height: auto; padding: 1; }

    #main { width: 1fr; }
    TabbedContent { height: 1fr; }
    #board-view, #info-view, #moves-view, #notes-view { padding: 0 1; }

    /* The explorer is docked to the right, like a side bar. */
    #explorer {
        width: 44;
        min-width: 30;
        border-left: solid $panel-lighten-2;
    }
    #explorer-root-label { padding: 0 1; }
    #explorer-tree { height: 1fr; }
    """

    BINDINGS = [
        Binding("ctrl+j", "run", "Run operation"),
        Binding("q", "quit", "Quit"),
        Binding("r", "reload", "Reload file"),
        Binding("s", "save", "Save"),
        Binding("f", "focus_explorer", "Explorer"),
        Binding("p", "focus_operations", "Operations"),
        Binding("d", "go_to_directory", "Open dir"),
        Binding("ctrl+n", "refresh_explorer", "Refresh files"),
    ]

    TITLE = APP_TITLE

    # (identifier, label, prompt for the parameter input, default value)
    # A prompt of None means the operation needs no parameter.
    OPERATIONS = [
        ("board",      "Show board position",          "Move number (blank = final)", ""),
        ("info",       "Show game information",         None, ""),
        ("properties", "List properties in the tree",   None, ""),
        ("moves",      "List moves",                    None, ""),
        ("check",      "Check for non-standard props",  None, ""),
        ("encoding",   "Report character encoding",     None, ""),
        ("clean",      "Clean non-standard -> file",    "Output file", "-clean"),
        ("to_utf8",    "Convert to UTF-8 -> file",      "Output file", "-utf8"),
        ("rotate_cw",  "Turn board 90 clockwise",       "Output file", "-rotate_cw"),
        ("rotate_acw", "Turn board 90 anticlockwise",   "Output file", "-rotate_acw"),
        ("flip_v",     "Flip board vertically",         "Output file", "-flip_vertical"),
        ("flip_h",     "Flip board horizontally",       "Output file", "-flip_horizontal"),
        ("split",      "Split collection -> directory", "Output directory", "_files"),
        ("save",       "Save back to the file",         None, ""),
    ]

    def __init__(self, start_dir):
        super().__init__()
        self.start_dir = Path(start_dir).resolve()
        self.path = None
        self.raw = None
        self.encoding_result = None
        self.game = None
        self.game_count = 0
        self.current = None

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="operations-pane"):
                yield Static("OPERATIONS", id="operations-heading")
                yield ListView(id="operations")
                with Vertical(id="params"):
                    yield Static("PARAMETERS", id="params-heading")
                    yield Static("", id="param-label")
                    yield Input(placeholder="", id="param-input")
                    yield Button("Run", variant="primary", id="run")
                yield Static("No file open.", id="file-details")
            with Vertical(id="main"):
                with TabbedContent(initial="tab-board"):
                    with TabPane("Board", id="tab-board"):
                        yield Static("", id="board-view")
                    with TabPane("Info", id="tab-info"):
                        yield Static("", id="info-view")
                    with TabPane("Moves", id="tab-moves"):
                        yield Static("", id="moves-view")
                    with TabPane("Notes", id="tab-notes"):
                        yield Static("", id="notes-view")
            with Vertical(id="explorer"):
                yield Static("EXPLORER", id="explorer-heading")
                yield Static(str(self.start_dir), id="explorer-root-label")
                yield SgfFileExplorer(str(self.start_dir), id="explorer-tree")
        yield Footer()

    def on_mount(self):
        self.sub_title = str(self.start_dir)
        listing = self.query_one("#operations", ListView)
        for _identifier, label, _prompt, _default in self.OPERATIONS:
            listing.append(ListItem(Label(label)))
        listing.focus()
        self._set_operation(0)
        self._placeholder("board-view",
                          "Choose an .sgf file in the EXPLORER on the right.")
        self._placeholder("info-view", "No file open.")
        self._placeholder("moves-view", "No file open.")
        self._placeholder("notes-view",
                          "Messages from operations appear here.")

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
                        title="No file open", severity="warning")
            return False
        return True

    def _set_operation(self, index):
        self.current = self.OPERATIONS[index]
        identifier, label, prompt, default = self.current
        label_widget = self.query_one("#param-label", Static)
        input_widget = self.query_one("#param-input", Input)
        if prompt is None:
            label_widget.update(Text("(no parameters)", style="dim"))
            input_widget.value = ""
            input_widget.disabled = True
        else:
            label_widget.update(prompt)
            input_widget.disabled = False
            input_widget.value = self._default_parameter(identifier, default)
        self.query_one("#run", Button).disabled = prompt is None and \
            identifier not in ("info", "properties", "moves", "check",
                               "encoding", "save")

    def _default_parameter(self, identifier, default):
        """Work out the parameter box's initial value for an operation."""
        if self.path is None:
            return str(default)
        source = Path(self.path)
        if identifier == "split":
            return str(source.with_name(source.stem + "_files"))
        if identifier == "board":
            return ""
        return str(source.with_name(source.stem + default + source.suffix))

    # -- file loading ------------------------------------------------------

    @on(SgfFileExplorer.FileSelected)
    def _file_selected(self, event):
        self.load_file(event.path)

    def load_file(self, path):
        """Read and parse an .sgf file, making it the current file."""
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
            self._update_file_details("unparseable")
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
            self._update_file_details("unparseable")
            self.notify("Can't parse the file: %s" % e,
                        title="Parse error", severity="error")
            return

        self._update_file_details()
        self._show_game_info()
        self._show_board()
        self._show_moves()
        self._set_operation(self.query_one("#operations", ListView).index or 0)
        self._show("tab-board")
        message = "Opened %s" % path.name
        if self.game_count > 1:
            message += "  (%d games; only the first is used)" % self.game_count
        self._note(message)
        self.notify(message, title="Opened")

    def _update_file_details(self, problem=None):
        widget = self.query_one("#file-details", Static)
        if self.path is None:
            widget.update(Text("No file open.", style="italic dim"))
            return
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold", justify="right")
        table.add_column()
        table.add_row("File", self.path.name)
        if problem:
            table.add_row("Status", Text(problem, style="bold red"))
        else:
            table.add_row("Size", "%d bytes" % len(self.raw))
            if self.game is not None:
                side = self.game.get_size()
                table.add_row("Board", "%dx%d" % (side, side))
            table.add_row("Games", str(self.game_count))
            if self.encoding_result is not None:
                result = self.encoding_result
                shown = Text(result.encoding)
                if result.mismatch and not result.ascii_only:
                    shown.append(" (CA differs)", style="yellow")
                table.add_row("Encoding", shown)
        widget.update(table)

    # -- running operations ------------------------------------------------

    @on(ListView.Highlighted, "#operations")
    def _operation_highlighted(self, event):
        if event.item is None:
            return
        self._set_operation(self.query_one("#operations", ListView).index)

    @on(ListView.Selected, "#operations")
    def _operation_selected(self, event):
        self._set_operation(self.query_one("#operations", ListView).index)
        prompt = self.current[2]
        if prompt is None:
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
        if self.current is None:
            return
        identifier = self.current[0]
        handler = getattr(self, "op_" + identifier, None)
        if handler is None:
            self.notify("Not implemented: %s" % identifier, severity="warning")
            return
        try:
            handler()
        except Exception as e:                 # noqa: BLE001
            # An operation failing shouldn't take the app down, and it must be
            # visible: show it in the result pane as well as notifying, so a
            # failure can't pass unnoticed.
            import traceback
            detail = "%s failed:\n\n%s" % (identifier, traceback.format_exc())
            self._set_view("info-view",
                           Text(detail, style="bold red"))
            self._show("tab-info")
            self._note("%s failed: %s" % (identifier, e), style="bold red")
            try:
                self.notify(str(e), title="Operation failed",
                            severity="error")
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

    def _show_board(self, move_number=None):
        try:
            board, plays = sgf_moves.get_setup_and_moves(self.game)
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
        if move_number is None:
            caption.append("   final position, %d moves" % len(plays))
        else:
            caption.append("   before move %d" % move_number)
        self._set_view("board-view",
                       Text.assemble(caption, "\n\n",
                                     Text(ascii_boards.render_board(board))))

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
        target = self._output_path("-clean")
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
        target = self._output_path("-utf8")
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

    # 9-12 -- transforms
    def op_rotate_cw(self):
        self._transform(sgf_transform.ROTATE_CW, "-rotate_cw", "turned clockwise")

    def op_rotate_acw(self):
        self._transform(sgf_transform.ROTATE_ACW, "-rotate_acw",
                        "turned anticlockwise")

    def op_flip_v(self):
        self._transform(sgf_transform.FLIP_VERTICAL, "-flip_vertical",
                        "flipped vertically")

    def op_flip_h(self):
        self._transform(sgf_transform.FLIP_HORIZONTAL, "-flip_horizontal",
                        "flipped horizontally")

    def _transform(self, transformation, suffix, description):
        if not self._require_file():
            return
        target = self._output_path(suffix)
        if target is None:
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

    def _output_path(self, suffix):
        """Resolve the output path from the parameter box.

        Passing '-' as the parameter writes back to the open file.
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
        return path

    def _reparse(self):
        """Parse the current file again, using the detected encoding."""
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
        self.query_one("#explorer-root-label", Static).update(str(self.start_dir))
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
