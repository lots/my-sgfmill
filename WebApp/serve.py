"""Serve the web app over HTTP and open it in a browser.

The web app is plain files, but a browser will not load ES modules from a
``file://`` URL, so it has to be served. This script does that and opens the
page, which is what :file:`run_web_app.cmd` runs.

    python WebApp/serve.py                # pick a free port and open a browser
    python WebApp/serve.py --port 8080    # ask for a particular port
    python WebApp/serve.py --no-browser   # just serve (useful in tests)

Nothing is installed and nothing is compiled: this only uses the standard
library, as the rest of the project does.
"""

import argparse
import http.server
import socket
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Browsers are strict about the content type of a module, and .sgf is not in
# the mimetypes database, so both are spelled out.
EXTRA_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".sgf": "application/x-go-sgf",
    ".json": "application/json",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serve files from this directory, with the right content types."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        **EXTRA_TYPES,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def end_headers(self):
        # Edits should show up on a reload, not hours later.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Keep the console readable: the point is the URL, not a request log.
        if self.command not in ("GET", "HEAD"):
            super().log_message(fmt, *args)


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def free_port(host, preferred):
    """Find a port to listen on, preferring the one asked for."""
    candidates = []
    if preferred:
        candidates.extend(range(preferred, preferred + 10))
    candidates.append(0)                      # let the system choose
    for port in candidates:
        try:
            with socket.socket() as probe:
                probe.bind((host, port))
                return probe.getsockname()[1]
        except OSError:
            continue
    raise SystemExit("no free port to listen on")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Serve the SGF Toolkit web app over HTTP.")
    parser.add_argument("--port", type=int, default=8000,
                        help="port to try first (default 8000; the next free "
                             "one is used if it is taken)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to listen on (default 127.0.0.1, so only "
                             "this machine can reach it)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser")
    args = parser.parse_args(argv)

    if not (HERE / "index.html").is_file():
        raise SystemExit("index.html is missing from %s" % HERE)

    port = free_port(args.host, args.port)
    server = Server((args.host, port), Handler)
    url = "http://%s:%d/" % (args.host, port)

    # Flushed, so the URL appears at once even when the output is redirected to
    # a file rather than going to a console.
    print("SGF Toolkit (web)", flush=True)
    print("  serving %s" % HERE, flush=True)
    print("  %s" % url, flush=True)
    if port != args.port:
        print("  (port %d was busy)" % args.port, flush=True)
    print("  press Ctrl+C to stop", flush=True)

    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
