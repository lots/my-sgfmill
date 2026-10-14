# Using the sgfmill example scripts

This directory contains small command-line programs that show how to drive the
sgfmill library:

| Script | What it does | Modules it demonstrates |
| --- | --- | --- |
| `show_sgf.py` | Prints the board position from an SGF file as ASCII art | `sgf`, `sgf_moves`, `ascii_boards` |
| `split_sgf_collection.py` | Splits a multi-game SGF file into one file per game | `sgf_grammar`, `sgf` |
| `report_sgf_properties.py` | Reports (or removes) properties that aren't standard | `sgf_normalise` |
| `transform_sgf.py` | Flips or turns the board, saving a new file | `sgf_transform` |
| `convert_sgf_encoding.py` | Reports a file's encoding and converts it to UTF-8 | `sgf_encoding` |

These are examples rather than polished tools: they are short, they print
errors in their own way, and they cover only the common cases. Read them
alongside this tutorial.

## Setup

The scripts import the `sgfmill` package, so it must be importable. Choose one:

**1. Install the package**, then run the scripts from anywhere:

```
pip install sgfmill
```

**2. Run from a checkout without installing.** Point `PYTHONPATH` at the
directory that *contains* the `sgfmill` package — that is, the parent of
`examples/`, not `examples/` itself:

```powershell
# Windows (PowerShell), from the checkout's top level
$env:PYTHONPATH = (Get-Location).Path
python examples\show_sgf.py examples\ff4_ex.sgf
```

```
# Unix
PYTHONPATH=/path/to/sgfmill-checkout python examples/show_sgf.py game.sgf
```

Setting `PYTHONPATH` is required. Running `python examples/show_sgf.py` with no
`PYTHONPATH` does **not** work from a checkout, because Python puts the
*script's* directory (`examples/`) on `sys.path`, not the directory you are
standing in, so `sgfmill` is not found:

```
ModuleNotFoundError: No module named 'sgfmill'
```

**3. Use a virtualenv that has the project installed** (as in this repository's
`.venv`), where no `PYTHONPATH` is needed:

```powershell
.venv\Scripts\python.exe examples\show_sgf.py examples\ff4_ex.sgf
```

In the rest of this tutorial, commands are written as if `sgfmill` is already
importable. No sample files are needed: the `examples/` directory already
contains `ff4_ex.sgf` (a two-game collection), `ff4_myex1.sgf`,
`9x9-wg-05.sgf`, and `9x9-wg-01.sgf`.

---

## `show_sgf.py`

Displays the board position from an SGF file.

### Usage

```
show_sgf.py <filename> [move number]
```

* **`filename`** — the SGF file to read. It may contain a collection; the
  **first** game is used.
* **`move number`** — optional. If given, the position **before** that move is
  shown. This matches the behaviour of GTP's `loadsgf` command.

### Example

Given this file, `game.sgf`:

```
(;FF[4]CA[UTF-8]GM[1]KM[6.5]PB[Black]PW[White]RE[B+R]SZ[9]
;B[cg];W[gc];B[gg];W[cc];B[df];W[fd];B[ff];W[dd];B[ee])
```

show the final position:

```
$ python show_sgf.py game.sgf
9  .  .  .  .  .  .  .  .  .
8  .  .  .  .  .  .  .  .  .
7  .  .  o  .  .  .  o  .  .
6  .  .  .  o  .  o  .  .  .
5  .  .  .  .  #  .  .  .  .
4  .  .  .  #  .  #  .  .  .
3  .  .  #  .  .  .  #  .  .
2  .  .  .  .  .  .  .  .  .
1  .  .  .  .  .  .  .  .  .
   A  B  C  D  E  F  G  H  J
```

`#` is black, `o` is white, and `.` is an empty point. The column labels follow
Go convention and **omit the letter I**.

Now show the position before move 5 (that is, after 4 moves have been played):

```
$ python show_sgf.py game.sgf 5
9  .  .  .  .  .  .  .  .  .
8  .  .  .  .  .  .  .  .  .
7  .  .  o  .  .  .  o  .  .
6  .  .  .  .  .  .  .  .  .
5  .  .  .  .  .  .  .  .  .
4  .  .  .  .  .  .  .  .  .
3  .  .  #  .  .  .  #  .  .
2  .  .  .  .  .  .  .  .  .
1  .  .  .  .  .  .  .  .  .
   A  B  C  D  E  F  G  H  J
```

So `show_sgf.py game.sgf 1` shows an empty board, `2` shows the position after
move 1, and so on. This off-by-one is deliberate, for compatibility with
`loadsgf`.

### What it handles

* **Setup stones and handicaps.** `AB`, `AW`, and `HA` in the root node are
  applied before the moves.
* **Passes.** Both `[]` and the older `[tt]` are skipped, so play continues
  after a pass.
* **Captures.** Moves are played through `Board.play()`, so stones are removed
  when they are captured, and the final diagram reflects that.
* **Rectangular and non-19x19 boards**, as declared by `SZ`.

### What it does not handle

* **Variations.** Only the game's *leftmost* variation (the main sequence) is
  followed; moves in other branches are ignored.
* **Annotations.** Comments, marks, and labels are not shown — only stones.
* **Move legality beyond the basics.** Illegal moves are detected and reported,
  but the SGF's ruleset (`RU`), ko, and superko are not enforced specially.

One parser behaviour is worth knowing because it can look surprising. If a node
contains both setup stones and a move — which FF[4] does not allow — sgfmill
does not reject the file. It moves the move into a new child node:

```
(;FF[4]SZ[9]AB[cc];B[dd])   ->   (;FF[4]AB[cc]SZ[9];B[dd])
```

So the illegal combination is quietly normalised rather than reported. This
also means the `mixed setup and moves in root node` error in
`sgf_moves.get_setup_and_moves()` is not reachable from a parsed file; you would
have to build that state yourself in memory.

### Errors

Argument mistakes are reported by `optparse` and exit with status **2**:

```
$ python show_sgf.py
Usage: show_sgf.py <filename> [move number]
show_sgf.py: error: not enough arguments

$ python show_sgf.py game.sgf abc
show_sgf.py: error: invalid integer value: abc

$ python show_sgf.py game.sgf 3 4
show_sgf.py: error: too many arguments
```

Anything wrong with the file itself is reported with a `show_sgf:` prefix and
exit status **1**:

| Problem | Message |
| --- | --- |
| File cannot be opened | `show_sgf: [Errno 2] No such file or directory: 'nope.sgf'` |
| Coordinates out of range for the board size, e.g. `B[zz]` on a 9x9 board | `show_sgf:` (the underlying `ValueError` has no message) |
| Setup properties after the root node | `show_sgf: setup properties after the root node` |
| A move onto an occupied point, or a suicide move | `show_sgf: illegal move in sgf file` |

Note that a **negative** move number is not accepted: `optparse` treats `-3` as
an option, giving `show_sgf.py: error: no such option: -3`. Use `0` to mean "no
moves played", and note that any move number larger than the number of moves
simply shows the final position.

---

## `split_sgf_collection.py`

An SGF file can hold more than one game: a *collection* is a sequence of game
trees. Many programs expect exactly one game per file, so this script splits a
collection into separate files.

### Usage

```
split_sgf_collection.py <filename>
```

There are no options; exactly one filename is accepted.

### What it writes

For an input file `NAME.EXT`, the script creates a directory `NAME_files/` next
to it (in the same directory as the input file) and writes one file per game:

```
NAME_files/NAME_1.EXT    <- first game
NAME_files/NAME_2.EXT    <- second game
...
```

Each extracted game also gets a comment in its root node recording where it came
from.

### Example

Given `collection.sgf`, containing two games:

```
(;FF[4]CA[UTF-8]GM[1]PB[First]SZ[9];B[ai];W[bh])
(;FF[4]CA[UTF-8]GM[1]PB[Second]SZ[9];B[bh];W[cg])
```

split it:

```
$ python split_sgf_collection.py collection.sgf
$ ls collection_files
collection_1.sgf  collection_2.sgf
```

The results are:

```
(;FF[4]C[Split from collection.sgf (game 1)]CA[UTF-8]GM[1]PB[First]SZ[9];B[ai];
W[bh])

(;FF[4]C[Split from collection.sgf (game 2)]CA[UTF-8]GM[1]PB[Second]SZ[9];B[bh]
;W[cg])
```

Note the added `C[...]` provenance comment in each root node.

A file containing a single game is also accepted — it just produces one output
file, `game_files/game_1.sgf`.

### Errors

Argument mistakes exit with status **2**:

```
$ python split_sgf_collection.py
Usage: split_sgf_collection.py <filename>
split_sgf_collection.py: error: not enough arguments

$ python split_sgf_collection.py a.sgf b.sgf
split_sgf_collection.py: error: too many arguments
```

File problems exit with status **1**, and are prefixed with `sgf_splitter:` —
note that this does not match the script's filename:

| Problem | Message |
| --- | --- |
| File cannot be opened | `sgf_splitter: [Errno 2] No such file or directory: 'nope.sgf'` |
| Malformed SGF data | `sgf_splitter: error parsing file: error parsing game 0: unexpected end of SGF data` |
| Output directory already exists | `sgf_splitter: [WinError 183] Cannot create a file when that file already exists:` |

Two consequences of the order of operations are worth knowing:

* The output directory is created **before** the input is parsed. If parsing
  fails, an **empty directory is left behind**.
* Because the directory is created with `os.mkdir`, running the script twice on
  the same file fails the second time rather than overwriting. Delete the
  `NAME_files/` directory first.

---

## `report_sgf_properties.py`

An SGF file may contain properties that aren't defined by FF[4]. Applications
add them for their own use, but other software must ignore them, and a file
containing them isn't portable. This script reports them, and can remove them.

### Usage

```
report_sgf_properties.py [options] <filename>

  -c, --clean          remove the non-standard properties
  -o FILE, --output=FILE
                       where to write the cleaned file (implies --clean)
```

The properties treated as standard are the "general" FF[4] properties plus the
Go-specific ones. `ID`, `L` and `LT` count as standard (FF[4] defines them)
even though sgfmill has no interpretation for them.

### Example

`9x9-wg-05.sgf` opens with two properties that aren't standard — `LV`, and
`UR`:

```
$ python report_sgf_properties.py 9x9-wg-05.sgf
9x9-wg-05.sgf:
  LV           in 1 node
  UR           in 1 node
```

A file with no such properties says so, and exits successfully:

```
$ python report_sgf_properties.py ff4_ex.sgf
ff4_ex.sgf: no non-standard properties
```

To write a cleaned copy (a new file, so the original is untouched):

```
$ python report_sgf_properties.py -o clean.sgf 9x9-wg-05.sgf
9x9-wg-05.sgf:
  LV           in 1 node
  UR           in 1 node
wrote clean.sgf
$ python report_sgf_properties.py clean.sgf
clean.sgf: no non-standard properties
```

Used without `--clean`, the script only reads, so it is safe to run on files
you care about.

### What it reports

Every node of the tree is examined, including variations, and each property is
listed once with the number of nodes containing it. Note that a private
property is reported whatever its value: `MULTIGOGM[1]` in `ff4_myex1.sgf`
holds a single number, and is still reported.

The exit status is **0** whether or not anything was found; a non-zero status
means the file couldn't be read.

### Errors

```
$ python report_sgf_properties.py
Usage: report_sgf_properties.py [options] <filename>
report_sgf_properties.py: error: not enough arguments

$ python report_sgf_properties.py -o clean.sgf
report_sgf_properties.py: error: not enough arguments

$ python report_sgf_properties.py nope.sgf
report_sgf_properties: [Errno 2] No such file or directory: 'nope.sgf'
```

The last one exits with status **1**.

---

## `transform_sgf.py`

Flips or turns the board, writing the result to a new file. Every move, stone
and markup is transformed; comments, player names and other properties are
copied unchanged.

### Usage

```
transform_sgf.py <transform> <filename> <outfile>
```

`<transform>` is one of:

| Name | Effect |
| --- | --- |
| `vflip` | swap the left and right halves of the board |
| `hflip` | swap the top and bottom halves of the board |
| `cw` | turn the board 90° clockwise |
| `acw` | turn the board 90° anticlockwise |

### Example

```
$ python transform_sgf.py cw 9x9-wg-05.sgf turned.sgf
```

To see that it did something, compare an early position. Before:

```
$ python show_sgf.py 9x9-wg-05.sgf 2
9  .  .  .  .  .  .  .  .  .
8  .  .  .  .  .  .  .  .  .
7  .  .  .  .  .  .  .  .  .
6  .  .  .  .  .  .  .  .  .
5  .  .  .  .  .  .  .  .  .
4  .  .  .  .  .  .  .  .  .
3  .  .  .  .  .  #  .  .  .
2  .  .  .  .  .  .  .  .  .
1  .  .  .  .  .  .  .  .  .
   A  B  C  D  E  F  G  H  J
```

After a clockwise turn, the same move (F3) is at G6:

```
$ python show_sgf.py turned.sgf 2
9  .  .  .  .  .  .  .  .  .
8  .  .  .  .  .  .  .  .  .
7  .  .  .  .  .  .  .  .  .
6  .  .  .  .  .  .  #  .  .
...
```

The script always writes to `<outfile>`, so the input file is never modified.

### Notes

* Each transformation is its own inverse or repeats: two `vflip`s, two `hflip`s
  or four `cw`s return the file to its original position.
* "Vertical flip" means a flip about a vertical axis, so `vflip` swaps left and
  right. If you want top and bottom exchanged, use `hflip`.
* An arrow (`AR`) keeps its direction: the order of its two points is
  preserved.

### Errors

```
$ python transform_sgf.py
transform_sgf.py: error: not enough arguments

$ python transform_sgf.py sideways ff4_ex.sgf out.sgf
transform_sgf.py: error: unknown transform: sideways (expected one of acw, cw, hflip, vflip)

$ python transform_sgf.py cw nope.sgf out.sgf
transform_sgf: [Errno 2] No such file or directory: 'nope.sgf'
```

The first two exit with status **2**, the last with status **1**.

---

## `convert_sgf_encoding.py`

SGF text values use the encoding named by the root `CA` property, defaulting to
ISO-8859-1. Files often declare the wrong encoding, or none, which makes
comments and player names appear as mojibake. This script works out what the
file actually is, and can rewrite it as UTF-8.

### Usage

```
convert_sgf_encoding.py [options] <filename>

  -o FILE, --output=FILE  write a UTF-8 copy to FILE
  -e NAME, --encoding=NAME
                          treat the file as being in this encoding
```

Without `-o` the script only reports, and changes nothing.

### Example

```
$ python convert_sgf_encoding.py 9x9-wg-05.sgf
9x9-wg-05.sgf: UTF-8
```

It reports both what it detected and what the file claims, when those differ:

```
$ python convert_sgf_encoding.py latin1-declared.sgf
latin1-declared.sgf: UTF-8 (file declares ISO-8859-1)
  (the file's CA property disagrees with its contents)
```

To convert:

```
$ python convert_sgf_encoding.py -o utf8.sgf 9x9-wg-05.sgf
9x9-wg-05.sgf: UTF-8
wrote utf8.sgf (UTF-8)
```

### How the encoding is decided

1. A UTF-8 byte order mark settles it, whatever `CA` says.
2. Otherwise the `CA` property is tried. If it names a codec Python knows, and
   the text values decode with it, that's the answer: a file that says what it
   is, is believed.
3. Otherwise UTF-8 is tried.
4. Otherwise ISO-8859-1, which can decode anything, so it never fails.

Step 2 is skipped for files with no non-ASCII bytes, since every
ASCII-compatible encoding decodes those identically.

A file that declares an encoding which is *wrong* but which still decodes its
bytes can't be detected: UTF-8 bytes labelled `CA[ISO-8859-1]` form a valid
Latin-1 string too, just not the intended one. The script follows the
declaration and reports the disagreement. Use `-e` to override it:

```
$ python convert_sgf_encoding.py -e UTF-8 -o fixed.sgf suspect.sgf
suspect.sgf: using UTF-8 (as requested)
wrote fixed.sgf (UTF-8)
```

A `CA` property naming a codec Python doesn't know (a broken file, but common
enough) is not fatal: the bytes are examined instead, and the name is reported.

### Errors

```
$ python convert_sgf_encoding.py
convert_sgf_encoding.py: error: not enough arguments
$ python convert_sgf_encoding.py nope.sgf
convert_sgf_encoding: [Errno 2] No such file or directory: 'nope.sgf'
```

Status **2** for a bad command line, **1** for a file problem.

### Notes

* The input file is never modified unless you point `-o` at it.
* These functions handle a single game. For a collection, split it first with
  `split_sgf_collection.py`.
* Only properties the library knows to be Text or SimpleText are converted. Any
  private property holding text is left alone.

---

## Things to watch out for

* **Coordinates are `(row, col)` in the library, not `(col, row)`.** SGF's
  `cc` means column C, row 7 on a 9x9 board, but sgfmill represents that as
  `(2, 6)`. `show_sgf.py` never exposes this, but you will meet it as soon as
  you write your own code. Row and column are both zero-based, with `(0, 0)`
  at the **bottom left** (GTP convention).
* **Passes.** sgfmill represents a pass as `None` and now *writes* it as `[]`.
  The older `[tt]` form is still read as a pass on boards of 19x19 or smaller,
  and a file read from disk is re-written with its original raw values, so a
  loaded `[tt]` is preserved.
* **Only the main sequence.** The viewing and splitting scripts follow the
  leftmost variation. Walking variations yourself means using
  `Sgf_game.get_main_sequence_below()` and `get_sequence_above()`, or the tree
  structure directly. (`report_sgf_properties.py`, `transform_sgf.py` and
  `convert_sgf_encoding.py` do walk the whole tree.)
* **Exit codes.** `0` success, `1` file/parse problem, `2` bad command line.
  All the scripts print their errors to stderr.
* **Encodings.** `split_sgf_collection.py` re-serialises each game, which adds
  `CA[UTF-8]` when the source had no `CA`. `show_sgf.py` and
  `report_sgf_properties.py` only read (unless asked to clean).
* **Transforms and coordinates.** `transform_sgf.py` works in sgfmill's own
  `(row, col)` coordinates, where `(0, 0)` is the bottom left, rather than in
  SGF's letters. SGF `aa` is the *top* left, i.e. `(size-1, 0)` — so a
  `vflip` is a flip about a vertical axis, swapping left and right.

## Where to look next

The example scripts are deliberately small. The library calls worth reading up
on are:

* `sgf.Sgf_game.from_bytes()` / `from_string()` — parse one game.
* `sgf_grammar.parse_sgf_collection()` — parse every game in a collection
  (this is what makes splitting possible).
* `sgf.Sgf_game.from_coarse_game_tree()` — turn a parsed tree into a full game.
* `sgf_moves.get_setup_and_moves()` — get the starting position and the move
  list, with passes as `None`.
* `boards.Board` — the Go board, including `play()`, `apply_setup()` and
  `area_score()`.
* `ascii_boards.render_board()` / `interpret_diagram()` — ASCII rendering and
  parsing.
* `sgf_normalise.check_game()` / `clean_game()` — find and remove properties
  that aren't standard.
* `sgf_transform.transform_game()` / `transform_point()` — flip or turn a
  game's board.
* `sgf_encoding.detect_bytes()` / `convert_game_to_utf8()` — work out a file's
  encoding, and convert it.

The full documentation is in `doc/`, and the test suite in `sgfmill_tests/`
shows every module being used in detail.
