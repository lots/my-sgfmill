# SGF Toolkit

A small [Textual](https://textual.textualize.io) application that puts the
`sgfmill` library's functions behind a keyboard-driven interface, so you can
inspect and edit `.sgf` files without writing Python.

It is a *companion* to the library rather than part of it: `sgfmill` itself
stays dependency-free, and only this app needs Textual.

## Running it

Install Textual, then start the app. The optional argument is the directory the
file explorer opens on (the current directory by default).

```powershell
pip install textual

# from the repository root
python run_sgf_toolkit.py
python run_sgf_toolkit.py examples

# or as a module
python -m App examples
```

To try it against the sample files that ship in this repository:

```powershell
python run_sgf_toolkit.py examples
```

## The layout

```
┌─ header ───────────────────────────────────────────────┐
│ OPERATIONS          │  Board | Info | Moves | Notes │ EXPLORER │
│  Show board position│                                │  examples│
│  Show game info     │   (results appear here)        │   ff4_ex │
│  ...                │                                │   ...    │
│ PARAMETERS          │                                │          │
│  Move number: [   ] │                                │          │
│  [ Run ]            │                                │          │
│ (file details)      │                                │          │
└─ footer ───────────────────────────────────────────────┘
```

* **Operations** (left) — pick one, fill in its parameters, press **Run**.
* **Results** (middle) — a tab per kind of output: the board diagram, general
  information and tables, the move list, and a running log of what the app has
  done.
* **Explorer** (right) — a VS Code style tree rooted at the chosen directory.
  It shows directories and `.sgf` files only, so other files and hidden
  directories (`.git`, `__pycache__`) stay out of the way. Selecting a file
  opens it.

## Keys

| Key | Action |
| --- | --- |
| `Ctrl+J` | Run the highlighted operation |
| `Enter` | In the parameter box: run the operation |
| `f` | Focus the explorer |
| `p` | Focus the operations list |
| `r` | Reload the open file from disk |
| `s` | Save (write the game back to its file) |
| `d` | Open a directory (type it in the parameter box first) |
| `Ctrl+N` | Refresh the explorer's file list |
| `q` | Quit |

Arrow keys and Enter drive the operations list and the file tree.

## What each operation uses

| Operation | Library call |
| --- | --- |
| Show board position | `sgf_moves.get_setup_and_moves()` + `ascii_boards.render_board()` |
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

* **Nothing is overwritten by accident.** The operations that write files
  suggest a new name (`game-clean.sgf`, `game-rotate_cw.sgf`, and so on) and
  write there; the file you opened is left alone. The only operation that
  writes back to the open file is **Save** (`s`). Entering `-` in the output
  box also means "write back to the open file".
* **Relative output names** are resolved against the directory of the open
  file, not the app's working directory.
* **Collections.** An `.sgf` file may hold several games. Everything except
  *Split* works on the first game, and the app says so when it opens such a
  file. *Split* writes one file per game.
* **Encoding.** On opening a file the app works out its character encoding, so
  comments and player names are shown correctly even when the `CA` property is
  wrong or missing. The detected encoding is shown in the file details panel.
* **Variations.** The board and move list follow the leftmost variation (that
  is what `sgf_moves` provides). *List properties in the tree* walks the whole
  tree, including variations.
* **A failed operation is reported** in the Info tab and in the log, rather
  than being swallowed.

## Layout of the code

```
App/
    __init__.py            package marker
    __main__.py            lets 'python -m App' work
    run_sgf_toolkit.py     the script to run
    sgf_toolkit.py         the application (widgets, operations, CSS)
    README.md              this file
```

`sgf_toolkit.py` is in three parts: `SgfFileExplorer` (the filtered directory
tree), the `SgfToolkitApp` class (layout, operations, bindings), and `main()`.
Each operation is a method named `op_<identifier>` and is listed in
`SgfToolkitApp.OPERATIONS`; adding one is a matter of appending to that list
and writing the method.

## Tests

The app is covered by `sgfmill_tests/app_tests.py`, which drives it headlessly
with Textual's own test harness (`App.run_test`). The tests load files, run
every read-only operation, exercise the writing operations against temporary
directories, and check that a failing operation is reported rather than
ignored.

```powershell
python -m sgfmill_tests.run_sgfmill_testsuite app_tests
python -m pytest sgfmill_tests/app_tests.py
```
