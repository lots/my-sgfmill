# SGF Toolkit — web app

A browser front end for the sgfmill library: the same fourteen operations as
the desktop app in [`../App/`](../App/README.md), in HTML5, CSS and JavaScript,
with no build step and **no runtime dependencies**. Copy this directory to a
static web server and it works.

```
WebApp/
├── index.html          the page
├── styles.css          the layout and colours
├── js/
│   ├── properties.js   SGF property values, points, vertices
│   ├── sgf.js          the FF[4] parser and serialiser
│   ├── board.js        a go board with captures, and the diagram
│   ├── moves.js        setup stones, moves, positions
│   ├── tools.js        normalise, transform, encoding, split
│   └── app.js          the interface: panels, tree, actions, log
└── tests/              Node tests, and the generator for their fixtures
```

## Running it

**On Windows, double-click `standalone.html`.** That is the whole app in one
file — no server, no Python, nothing to install — and it is the simplest way to
use it locally.

```
standalone.html              the app in one file; double-click it
run_web_app.cmd              serve the modular version and open a browser
```

Use the served version when developing (it reloads the separate modules rather
than a built file). Anywhere, or with your own server:

```bash
cd WebApp
python serve.py                   # what the .cmd runs: picks a free port and
                                  # opens a browser
python -m http.server 8000        # or any static server
node tests/serve.mjs 8000         # or the dependency-free one in the tests
```

The launcher looks for Python in this order: the repository's `.venv`, then
`python` on the PATH, then the `py` launcher. Nothing is installed.

### Why there are two versions

Browsers refuse to load ES modules from a `file://` URL, so `index.html` — which
loads `js/*.js` as modules — has to be served. `standalone.html` is generated
from the same sources with the modules inlined into one classic script, which a
browser will happily load from disk.

The modular sources are the truth. Regenerate the single file after changing
anything in `js/`:

```bash
node build_standalone.mjs        # or: npm run build:standalone
```

`tests/standalone_test.mjs` fails if the file is out of date, and also runs it
from a `file://` URL to prove it still works.

## Deploying it

Copy `WebApp/` to the server. That is the whole procedure: there is nothing to
build, no package to install, and no server-side code. It works on GitHub
Pages, Netlify, S3, a plain Apache directory, or anywhere else that serves
files. The only requirement is that `.js` files are served as JavaScript
(`text/javascript`) — which every normal server does.

Development dependencies (`package.json`, `node_modules/`) are only used to run
the tests, and need not be deployed.

## What it does

The window follows the desktop app: **select a target**, **choose an action**,
**see the game as a tree**, **see the result**, with a message bar across the
bottom describing the highlighted action. Panel widths are draggable.

| Action | What it does |
| --- | --- |
| Show board position | The position after a given number of moves |
| Show tree | Every node of the file; click a move to see its position |
| Show game information | Players, result, komi, handicap, size, encoding |
| List properties in the tree | Every node with its properties |
| List moves | The main line, with vertices in GTP style |
| Check for non-standard props | Properties FF[4] does not define for Go |
| Clean non-standard → file | Removes them and downloads the result |
| Convert to UTF-8 → file | Writes the file as UTF-8, declaring `CA[UTF-8]` |
| Turn 90 clockwise / anticlockwise | Composing quarter-turns, previewed |
| Flip vertically / horizontally | Composing flips, previewed for a mirror image |
| Split collection → files | One download per game in a collection |
| Save back to a file | Writes the game out again |

The flip and turn actions preview immediately and **compose**: choosing a flip
twice brings the board back to where it started, and four quarter-turns do the
same. *Apply one more* (`Ctrl+A`) adds another application without moving the
selection; `Escape` resets the preview; `Run` (`Ctrl+J`) writes what is on
screen.

### Keys

| Key | Action |
| --- | --- |
| `Ctrl+J` | Run the highlighted action |
| `Ctrl+A` | Apply the current flip or turn one more time |
| `Escape` | Reset the preview |
| `↑` / `↓`, `Enter` | Move through the actions and choose one |
| `e` / `a` / `t` | Focus the explorer, actions, or tree |

## Why this is a port, not the Python library

The library is Python, and a static web server cannot run Python. The two
honest options were a JavaScript port, or shipping a Python interpreter to the
browser (Pyodide, ~10 MB of WebAssembly from a CDN). This is the port: it keeps
deployment to plain files, works offline, and needs no CDN at run time.

The cost is real — a second implementation of the same rules can drift from the
first — so the port is **checked against the library rather than trusted**:

* [`tests/generate_expected.py`](tests/generate_expected.py) asks the Python
  library what each fixture contains: the serialised bytes, node counts, move
  lists, setup stones, the position after every move and at every node, the
  non-standard property report, the cleaned file, all four transformations, and
  the board diagram character for character.
* [`tests/engine_test.mjs`](tests/engine_test.mjs) computes the same things in
  JavaScript and compares. **221 checks**, and the answers must be identical,
  not merely similar — including the exact bytes written back out.
* [`tests/ui_test.mjs`](tests/ui_test.mjs) loads the real page in jsdom and
  drives it: loading files, clicking actions, walking the tree, composing
  flips, writing files, splitting collections.

If the library changes, regenerate the expectations and the comparison will say
whether the port still agrees:

```bash
python WebApp/tests/generate_expected.py     # uses sgfmill itself
cd WebApp && npm install && npm test
```

Both test scripts also run from the library's own testsuite, as
`sgfmill_tests/webapp_tests.py`, which skips them when Node is not installed.

## Deliberate differences from the desktop app

* **Files come in through a picker or drag and drop**, not a directory tree.
  A web page cannot read a directory, so the explorer lists the files you have
  opened instead. Writing produces downloads, or a save dialog where the
  browser supports the File System Access API.
* **Output is a download, not a file on disk.** The app never overwrites the
  file you loaded; it hands you a new one. That is the same rule as the desktop
  app, enforced by the platform.
* The paths, the shell launcher and the `SGF_TOOLKIT_*` environment variables of
  the desktop app have no meaning here.

## Troubleshooting

**"Nothing happens when I choose a file."** The app's JavaScript did not load.
This is almost always `index.html` opened as a file rather than served: a
`file://` URL cannot load ES modules, so the page appears but nothing is wired
up. The page says so — a red banner explains it.

**Open `standalone.html` instead.** It is the same app in one file and needs
no server. Or serve the modular version:

```bash
cd WebApp
python serve.py                # picks a free port and opens a browser
```

Other causes, in order of likelihood:

* **The server sends `.js` as the wrong content type.** Browsers refuse to run
  a module served as `text/plain`. It must be `text/javascript` (or
  `application/javascript`). The banner reports a load failure; the browser
  console names the file.
* **The directory was only partly copied.** `index.html` needs the `js/` and
  `styles.css` beside it, with the paths unchanged.
* **A file is listed but marked unreadable.** The reason appears under the file
  list and in the Notes tab; the file itself is not valid SGF.

The banner and the line under the file list exist because a silent failure
looks exactly like a broken interface: the page renders, and nothing responds.

## Limitations worth knowing

* Board sizes up to 26×26, as the library supports. Compressed point lists
  (`AB[aa:cc]`) are expanded exactly as the library expands them.
* Files are decoded with the browser's `TextDecoder`, so the encodings
  available are the browser's (which covers UTF-8, Latin-1, Shift_JIS, EUC-JP,
  GBK, Big5, EUC-KR and more).
* Very large collections are parsed synchronously, so a huge file will block
  the page briefly while it loads.
