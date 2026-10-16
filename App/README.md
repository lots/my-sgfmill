# SGF Toolkit

A small [Textual](https://textual.textualize.io) application that puts the
`sgfmill` library's functions behind a keyboard-driven interface, so you can
inspect and edit `.sgf` files without writing Python.

It is a *companion* to the library rather than part of it: `sgfmill` itself
stays dependency-free, and only this app needs Textual.

## Running it

On Windows, `App\run_sgf_toolkit.cmd` is the shortest way in. It uses the
repository's `.venv` if there is one and otherwise falls back to `python` on
your `PATH`, so it does not care which directory you are in:

```bat
App\run_sgf_toolkit.cmd                 :: opens the current directory
App\run_sgf_toolkit.cmd examples        :: opens that directory
App\run_sgf_toolkit.cmd --help          :: lists the options and keys
```

A directory given to it is resolved against the directory you run it from, not
against `App\`. It also pauses before closing the console, so an error message
stays readable if you started it by double-clicking.

Otherwise, install Textual and start the app directly. The optional argument is
the directory the file explorer opens on (the current directory by default).

```powershell
pip install textual

# from the repository root
python App/run_sgf_toolkit.py
python App/run_sgf_toolkit.py examples

# or as a module
python -m App examples

# the script can also be run from inside App/, or by absolute path
cd App; python run_sgf_toolkit.py
```

`--help` works here too:

```powershell
python App/run_sgf_toolkit.py --help
```

It works from any directory: the entry script puts the repository root on
`sys.path` itself. (Running a script adds *its own* directory to `sys.path`,
not the directory you started it from, so without that step `import App` would
fail with `ModuleNotFoundError: No module named 'App'`.)

To try it against the sample files that ship in this repository:

```powershell
App\run_sgf_toolkit.cmd examples
```

### Without a terminal

Two environment variables let the app start where there is no terminal to drive
it from (a build server, or a smoke test):

| Variable | Effect |
| --- | --- |
| `SGF_TOOLKIT_HEADLESS` | Use Textual's headless driver |
| `SGF_TOOLKIT_EXIT_AFTER_STARTUP` | Quit once the layout is ready |

```powershell
$env:SGF_TOOLKIT_EXIT_AFTER_STARTUP = "1"   # start, then quit
python App/run_sgf_toolkit.py
```

## The layout

Two rows. The top row is four panels side by side; the bottom row is a single
message pane. The panels follow the order you work in: **select a target**,
**choose an action**, **see the game as a tree**, **see the result**.

```
┌─ header ──────────────────────────────────────────────────────────────────────────┐
│ 1 SELECT TARGET   │ 2 SELECT ACTION        │ 3 GAME TREE        │ 468 bytes  9x9  │
│  examples         │  Show board position   │ ▼ GN HA KM PB +3   │ Board Info ...  │
│ 📂 examples       │  Show tree (click...)  │ └ ▼ B F3           │ 9x9-wg-05.sgf   │
│  ├── 9x9-wg-01    │  Show game information │   └ ▼ W E6         │ at B E3         │
│  ├── 9x9-wg-05    │  List properties...    │     └ ▼ B C3       │                 │
│  └── ff4_ex       │  List moves            │       └ ▼ W E4     │ 9 . . . . . . . │
│                   │  Check for non-stand.  │         └ ▶ B E3   │ 8 . . . . . . . │
│                   │  ...                   │                    │ 7 . . . . . . . │
│                   │                        │                    │ 6 . . . . o . . │
│                   │ 9x9-wg-05.sgf          │                    │ ...             │
│                   │ [ ....-clean.sgf   ]   │                    │                 │
│                   │ [      Run         ]   │                    │                 │
├───────────────────┴────────────────────────┴────────────────────┴─────────────────┤
│ 9x9-wg-05.sgf  Click a move in the tree to see its position.  Board tab.          │
└─ footer ─────────────────────────────────────────────────────────────────────────┘
```

The four panels each take the full height of the top row; nothing is stacked.

* **1 — Explorer** (left) — a VS Code style tree rooted at the chosen
  directory: directories, plus `.sgf` files only, so hidden directories
  (`.git`, `__pycache__`) stay out of the way. Selecting a file opens it and
  makes it the target.

  There is a `..` entry at the top of the list for the parent directory, so you
  can walk up to anywhere on the disk; selecting any directory in the tree
  moves the root there, and `Backspace` goes up a level. (At the top of a
  filesystem there is no parent, so no `..` is offered.)
* **2 — Actions** (second) — the list of actions, with the parameter box and
  **Run** button below it. Select an action to run it, or press `Ctrl+J`.
* **3 — Game tree** (third) — the whole game as a tree, filled in by the
  **Show tree** action. One entry per node of the SGF file, so the main line
  runs down the pane with variations branching off it. Move entries read
  `B C3`; other nodes show the properties a reader cares about, or just how
  many properties they carry. **Clicking an entry draws that position** on the
  Board tab, and the caption says which entry it is. Setup stones anywhere in
  the tree, and passes, are honoured. Until **Show tree** has been run the pane
  is empty.
* **4 — Results** (right) — a line describing the target (size, board, games,
  encoding), then a tab per kind of output: the board diagram, information and
  tables, the move list, and a running log of what the app has done.
* **Message pane** (bottom, full width) — one line about the highlighted
  action: what it does, what its parameter means, and what you get. It names
  the target too, so there is no doubt what **Run** will act on. Press `h` to
  hide or show it.

## Keys

| Key | Action |
| --- | --- |
| `Ctrl+J` | Run the highlighted action |
| `Ctrl+A` | Apply the current flip/turn one more time |
| `Escape` | Reset the preview to the file's position |
| `Enter` | In the parameter box: run the action |
| `e` | Focus the explorer (step 1) |
| `a` | Focus the actions list (step 2) |
| `Backspace` | Go up one folder in the explorer |
| `h` | Hide or show the message pane |
| `r` | Reload the target from disk |
| `s` | Save (write the game back to its file) |
| `d` | Open a directory (type it in the parameter box first) |
| `Ctrl+N` | Refresh the explorer's file list |
| `q` | Quit |

Arrow keys and Enter drive the operations list and the file tree.

## What each operation uses

| Operation | Library call |
| --- | --- |
| Show board position | `sgf_moves.get_setup_and_moves()` + `ascii_boards.render_board()` |
| Show tree | `Tree_node` children, `get_raw_move()`, `sgf_properties.interpret_go_point()` |
| Show game information | `Sgf_game.get_komi()`, `get_handicap()`, `get_player_name()`, `get_winner()` |
| List properties in the tree | `Tree_node.get_raw_property_map()`, walking variations |
| List moves | `sgf_moves.get_setup_and_moves()` + `common.format_vertex()` |
| Check for non-standard props | `sgf_normalise.check_game()` |
| Clean non-standard → file | `sgf_normalise.clean_game()` |
| Report character encoding | `sgf_encoding.detect_bytes()` |
| Convert to UTF-8 → file | `sgf_encoding.convert_game_to_utf8()` |
| Turn / flip the board | `sgf_transform.transform_game()` |
| Split a collection | `sgf_grammar.parse_sgf_collection()` + `Sgf_game.from_coarse_game_tree()` |
| Save | `Sgf_game.serialise()` |

## Things worth knowing

* **Nothing is overwritten by accident.** The actions that write files suggest
  a new name (`game-clean.sgf`, `game-rotate_cw.sgf`, and so on); the file you
  opened is left alone. If a name is already taken, a numbered one is used
  (`game-clean-1.sgf`) and the app says so. The only action that writes back to
  the target is **Save** (`s`); entering `-` in the output box also means "the
  open file".
* **Relative output names** are resolved against the directory of the target
  file, not the app's working directory.
* **The four flip and turn actions preview themselves, and they compose.**
  Selecting *Turn board 90 clockwise*, *Turn board 90 anticlockwise*, *Flip
  board vertically* or *Flip board horizontally* applies it to the preview on
  the Board tab, captioned `PREVIEW: ... (n applied, Run saves it)`. Selecting
  the same action again, or pressing **Apply one more** (`Ctrl+A`), adds
  another application on top, so the cycle can be watched closing: **two flips
  return to the original board, and four quarter-turns do too**. `Escape`
  resets the preview. Nothing is written until you press **Run**, which saves
  the board that is on screen — including a full cycle, which is saved as an
  unchanged position and noted as such in the log.

  The target is never transformed in place: if the output name is the file you
  opened, the action refuses and says so (use **Save** for that). Pressing
  **Run** with nothing previewed also refuses, because there would be nothing to
  save. Selecting any other action puts the plain final position back, so a
  preview can't be mistaken for the file's contents.
* **Moves and stones are not the same count.** A pass places nothing, a
  capture removes something, and setup stones (`AB`/`AW`) are on the board
  before any move. So four moves need not mean four stones, and the board
  caption says which is which — for example `final position: 4 moves, 1 pass,
  3 stones by the moves`. The diagram itself is always the position the library
  computes for the file.
* **Collections.** An `.sgf` file may hold several games. Everything except
  *Split* works on the first game, and the target bar says so. *Split* writes
  one file per game.
* **Encoding.** On opening a file the app works out its character encoding, so
  comments and player names are shown correctly even when the `CA` property is
  wrong or missing. The detected encoding is shown in the target bar.
* **Variations.** The board and move list follow the leftmost variation (that
  is what `sgf_moves` provides). *List properties in the tree* walks the whole
  tree, including variations.
* **A failed action is reported** in the Info tab and in the log, rather than
  being swallowed.

## Layout of the code

```
App/
    __init__.py            package marker
    __main__.py            lets 'python -m App' work
    run_sgf_toolkit.py     the script to run
    run_sgf_toolkit.cmd    Windows launcher (finds Python, passes a directory)
    sgf_toolkit.py         the application (widgets, operations, CSS)
    README.md              this file
```

`sgf_toolkit.py` is in three parts: `SgfFileExplorer` (the filtered directory
tree), `MessageBar` (the message text for each action), and the
`SgfToolkitApp` class (layout, actions, bindings). Each action is a method named
`op_<identifier>` and is listed in `SgfToolkitApp.OPERATIONS`; adding one means
appending to that list, writing the method, and adding an entry to
`MessageBar.HELP` (a test checks that every action has a message).

## Tests

The app is covered by four test modules:

* `sgfmill_tests/app_tests.py` drives it headlessly with Textual's own test
  harness (`App.run_test`). The tests load files, run every read-only action,
  exercise the writing actions against scratch directories, and check that a
  failing action is reported rather than ignored.
* `sgfmill_tests/app_layout_tests.py` covers the shape of the window and the
  behaviour of the actions: that the three panels share the top row with the
  message pane across the bottom, that the message describes the highlighted
  action and names the target, that the board matches the position the library
  computes (including passes, captures and setup stones), that the flip and
  turn actions compose into a cycle, and that writing to a name that already
  exists picks a free name instead.
* `sgfmill_tests/app_entry_tests.py` runs the entry script for real, in a
  subprocess, from the repository root and from another directory. It guards
  the `sys.path` bootstrap described above, which is easy to break and was
  broken once.
* `sgfmill_tests/app_launcher_tests.py` runs `run_sgf_toolkit.cmd` for real:
  with no argument, with a relative directory (which must resolve against the
  caller's directory, not `App\`), with `--help` (which must print and exit
  rather than start the interface), and with a directory that does not exist.

```powershell
python -m sgfmill_tests.run_sgfmill_testsuite `
    app_tests app_layout_tests app_entry_tests app_launcher_tests
python -m pytest sgfmill_tests/app_tests.py sgfmill_tests/app_layout_tests.py `
                sgfmill_tests/app_entry_tests.py `
                sgfmill_tests/app_launcher_tests.py
```
