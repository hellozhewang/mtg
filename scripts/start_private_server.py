#!/usr/bin/env python3
"""Serve the catalog (docs/) on the local network, always on port 5588.

The same site GitHub Pages publishes, private decks included, but straight from
this machine: it shows a build the moment `build_site.py` writes it, without
waiting for a push to go live. One page differs: the home page is the owner's
local index (docs/index.local.html), which shows local-only categories such as
Goblins and is never published. The name predates private decks being
published, when this was the only place to see them."""
from __future__ import annotations

import argparse
import functools
import http.client
import http.server
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import workspace

HOST = "127.0.0.1"
BIND_HOST = "0.0.0.0"
PORT = 5588
URL = f"http://localhost:{PORT}/"
# Log and PID go to the temp dir, not private/: that folder is for decks, and a
# server that doesn't survive a reboot doesn't need state that does.
STATE_DIR = Path(tempfile.gettempdir()) / "mtg-private-catalog"


def serving_catalog(index: bytes) -> bool:
    """Recognize this catalog, including a server started with http.server."""
    connection = http.client.HTTPConnection(HOST, PORT, timeout=1)
    try:
        connection.request("GET", "/index.html")
        response = connection.getresponse()
        return response.status == 200 and response.read(len(index) + 1) == index
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


LOCAL_INDEX = "index.local.html"          # build_site.LOCAL_INDEX


class CatalogHandler(http.server.SimpleHTTPRequestHandler):
    """Serves docs/, except that the index is the owner's local one. Every deck
    page links home as `index.html`, so this keeps the whole visit local."""

    def translate_path(self, path):
        bare = path.split("?", 1)[0].split("#", 1)[0]
        if bare in ("/", "/index.html") and (Path(self.directory) / LOCAL_INDEX).is_file():
            path = "/" + LOCAL_INDEX + path[len(bare):]
        return super().translate_path(path)


def serve(site: Path) -> None:
    handler = functools.partial(CatalogHandler, directory=str(site))
    http.server.ThreadingHTTPServer((BIND_HOST, PORT), handler).serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", type=Path, help=argparse.SUPPRESS)   # the detached child
    args = ap.parse_args()
    if args.serve:
        serve(args.serve)
        return 0
    site = workspace.site_dir().resolve()
    try:
        # What the home page should be: the local index once a build wrote one.
        index = ((site / LOCAL_INDEX) if (site / LOCAL_INDEX).is_file()
                 else (site / "index.html")).read_bytes()
    except OSError as error:
        print(f"Cannot read the catalog: {error}\n"
              "Build it first with: python3 scripts/build_site.py", file=sys.stderr)
        return 1

    if serving_catalog(index):
        print(f"Catalog already running: {URL}")
        return 0

    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            print(f"Port {PORT} is already in use by another service. "
                  "It has been left running.", file=sys.stderr)
            return 1
    except OSError:
        pass

    state = STATE_DIR
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / f"catalog-{PORT}.log"
    with log_path.open("ab", buffering=0) as log:
        server = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--serve", str(site)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if server.poll() is not None:
            break
        if serving_catalog(index) and server.poll() is None:
            (state / f"catalog-{PORT}.pid").write_text(f"{server.pid}\n")
            print(f"Catalog running: {URL}\n"
                  f"PID: {server.pid} | Log: {log_path}")
            return 0
        time.sleep(0.1)

    if server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=2)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    print(f"Could not start the catalog on port {PORT}. "
          f"See {log_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
