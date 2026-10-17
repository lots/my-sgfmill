# my-sgfmill — an experimental fork

> **This is a personal fork of sgfmill, kept for experimental work.**
>
> It is **not** the official sgfmill, and it is not maintained for anyone
> else's use. The code here has not been reviewed by the original author, may
> change without notice, and may be less reliable than what it is forked from.
>
> **If you want to use sgfmill, or to contribute to it, use the original:**
>
> * Upstream repository — <https://github.com/mattheww/sgfmill>
> * Original author's page — <https://mjw.woodcraft.me.uk/sgfmill/>
>
> Everything below describes this fork. For anything resembling production use,
> read the upstream documentation instead.

## What sgfmill is

Sgfmill is a Python library for reading and writing Go (weiqi) game records in
Smart Game Format (SGF), specifically FF[4]. It has no third-party
dependencies: it is pure Python, and it works with the standard library alone.

Its design is deliberately small and layered:

* `sgf` — the object model: parse, build, edit and serialise game trees
* `sgf_moves` — the starting position and move list of a game
* `boards` — a Go board, including captures and scoring
* `ascii_boards` — board diagrams as text
* `sgf_grammar`, `sgf_properties` — the parser and the property type system

Sgfmill is a Python 3 port of the SGF code from the older Python 2 Gomill
project. It is intended for Go only: it does not implement the other game
modules of FF[4].

## What this fork adds

Beyond the upstream library, this fork carries three extra modules and two
front ends, all written to the same style as the rest of the library. They are
the reason this fork exists, and they have not been proposed upstream.

| Addition | What it does |
| --- | --- |
| `sgf_normalise` | Reports the properties in an SGF game that aren't defined by FF[4] for Go, and can remove them to produce a file that only uses standard properties. |
| `sgf_transform` | Flips or turns a game's board: vertical and horizontal flips, and quarter-turns clockwise and anti-clockwise. |
| `sgf_encoding` | Works out the character encoding an SGF file's bytes are really in, and converts them to UTF-8. |
| `App/` | **SGF Toolkit**, a [Textual](https://textual.textualize.io) application that puts the library's functions behind a keyboard-driven interface, with a VS Code style file explorer. |
| `WebApp/` | **SGF Toolkit (web)**, the same operations in HTML5, CSS and JavaScript, deployable to any static web server by copying the directory. |

Other differences from upstream:

* A pass is now written as the FF[4] empty value (`B[]`) rather than `tt`. The
  older `tt` form is still read as a pass on boards of 19x19 or smaller.
* `App/run_sgf_toolkit.cmd` starts the desktop app on Windows.
* The testsuite has grown well past 200 tests, and pytest is wired up
  alongside the library's own runner.

The desktop app needs Textual, and the web app is a JavaScript port of the
library; **the library itself still needs nothing**. Keeping that property is
deliberate, and it is why the web app has no runtime dependencies either — no
build step and no CDN.

See `doc/changes.rst` for the details, `App/README.md` for the desktop app and
`WebApp/README.md` for the web app.

## Requirements

The library requires Python 3.5 or newer, and has no other dependencies.

The companion app in `App/` additionally requires Textual, and the
documentation build requires Sphinx. Neither is needed to use the library.

## Running the test suite

The library has its own runner, which is the authoritative one:

```
python run_sgfmill_testsuite                 # everything
python run_sgfmill_testsuite sgf_tests       # one module
```

It can also be run as a module, which is what works on Windows, where the
`run_sgfmill_testsuite` file is a shell script:

```
python -m sgfmill_tests.run_sgfmill_testsuite
python -m sgfmill_tests.run_sgfmill_testsuite common_tests.test_opponent_of
```

A single test is named `<module>.<function>`; a parameterised test adds its
code, as in `<module>.<test_name>:<code>`.

pytest runs the same tests, and is configured in `pytest.ini`:

```
python -m pytest
```

## Running the example scripts

`examples/` holds small command-line programs that show how to drive the
library: `show_sgf.py`, `split_sgf_collection.py`, and one for each of this
fork's modules. `examples/README.md` is a tutorial for all of them.

The scripts import the `sgfmill` package, so either install it or point
`PYTHONPATH` at this directory:

```
export PYTHONPATH=<path to this directory>       # Unix
$env:PYTHONPATH = (Get-Location).Path            # PowerShell
```

## Running the companion app

```
App\run_sgf_toolkit.cmd [directory]              # Windows
pip install textual
python App/run_sgf_toolkit.py [directory]
python App/run_sgf_toolkit.py --help
```

## Running the web app

On Windows, **double-click `WebApp\run_web_app.cmd`**: it serves the directory
and opens your browser. Close the window to stop it.

The app is plain files, but a browser will not load ES modules from `file://`,
so it has to be served over HTTP:

```
WebApp\run_web_app.cmd              # Windows: serve and open a browser
cd WebApp
python serve.py                     # the same thing, anywhere
python -m http.server 8000          # or any static server
node tests/serve.mjs 8000           # or the dependency-free one in the tests
```

Deploying it is copying `WebApp/` to a static web server: there is no build step
and nothing to install. See `WebApp/README.md`.

## Building the documentation

```
./build_docs
```

The result is written to `doc/_build/html`. Sphinx 1.0 or later is required
(tested with Sphinx 9).

## Installing

Installing puts the `sgfmill` package on the Python module search path. This
replaces any installed sgfmill, so it is worth being sure you want the fork:

```
python setup.py bdist_wheel
pip install --user dist/sgfmill-*.whl
```

To uninstall:

```
pip uninstall sgfmill
```

Note that `release_sgfmill.py`, which builds a source distribution, removes
this file: the distribution carries `README.sdist.txt` as its `README.txt`
instead, as upstream does.

## Layout

```
sgfmill/            the library
sgfmill_tests/      the testsuite
examples/           example scripts, with a tutorial in README.md
App/                SGF Toolkit, the Textual desktop app, with its own README
WebApp/             SGF Toolkit (web): HTML5, CSS and JavaScript, with its own README
doc/                Sphinx documentation sources
run_sgfmill_testsuite   testsuite entry point (shell script)
setup.py            packaging
```

## Licence

Sgfmill is copyright 2009-2018 Matthew Woodcraft and the sgfmill contributors,
and is released under the MIT licence; see the 'Licence' page of the
documentation (`doc/licence.rst`), which carries the full text.

This fork carries the same licence, and the additions here are offered under
it. The copyright in the original work remains with its authors.

## Contact

For sgfmill itself — bug reports, suggestions, patches, questions — please
contact the original author, Matthew Woodcraft
(<matthew@woodcraft.me.uk>), or use the upstream repository. Please do not
send them anything about the experimental additions in this fork.

Issues with this fork are its owner's problem, and can be raised in this
fork's repository.
