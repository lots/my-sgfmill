Web app
=======

:file:`WebApp/` holds a browser front end for the library: the same operations
as the companion application in :file:`App/`, written in HTML5, CSS and
JavaScript, and deployable by copying the directory to a static web server.

It needs nothing at run time. There is no build step, no package to install and
no server-side code, because the library's own property -- no dependencies --
is worth keeping in its front ends too.

Why it is a port
----------------

A static web server cannot run Python, so the JavaScript in :file:`WebApp/js/`
is a port of the library rather than a binding to it. That risks the two
implementations drifting apart, so the port is checked against the library
rather than trusted: :file:`WebApp/tests/generate_expected.py` asks the Python
library what each fixture means -- the serialised bytes, the position after
every move and at every node, the non-standard property report, the cleaned
file, all four transformations, and the board diagram character for
character -- and the Node tests compare the JavaScript answers with those.

The comparison is part of this documentation's testsuite: see
:mod:`sgfmill_tests.webapp_tests`, which runs it when Node is installed and
skips it otherwise.

Running and deploying
---------------------

Serve the directory over HTTP (browsers will not load ES modules from
``file://``)::

   cd WebApp
   python -m http.server 8000

Deploying is copying :file:`WebApp/` to the server. See
:file:`WebApp/README.md` for the actions, the keys, and the differences from the
desktop application.
