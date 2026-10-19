#!/usr/bin/env python3
"""Serve the catalog (docs/) on the local network, always on port 5588.

The same site GitHub Pages publishes, private decks included, but straight from
this machine: it shows a build the moment `build_site.py` writes it, without
waiting for a push to go live. One page differs: the home page is the owner's
local index (docs/index.local.html), which shows local-only categories such as
Goblins and is never published. The name predates private decks being
published, when this was the only place to see them.

On macOS this installs and starts a launchd LaunchAgent (`com.cholo.mtg-catalog`)
with `RunAtLoad` and `KeepAlive`, matching the Discord bot services."""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.client
import http.server
import os
import plistlib
import shutil
import signal
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
LABEL = "com.cholo.mtg-catalog"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
STATE_DIR = Path(tempfile.gettempdir()) / "mtg-private-catalog"
LOCAL_INDEX = "index.local.html"          # build_site.LOCAL_INDEX


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


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _service_running() -> bool:
    res = subprocess.run(
        ["launchctl", "print", f"{_domain()}/{LABEL}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def _service_pid() -> int | None:
    res = subprocess.run(
        ["launchctl", "print", f"{_domain()}/{LABEL}"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    for line in res.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("pid = "):
            try:
                return int(stripped.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def _write_plist(site: Path, log_path: Path) -> bool:
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    python_bin = shutil.which("python3") or sys.executable
    payload = {
        "Label": LABEL,
        "ProgramArguments": [
            python_bin,
            "-u",
            str(Path(__file__).resolve()),
            "--serve",
            str(site),
        ],
        "WorkingDirectory": str(site.parent),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }
    raw = plistlib.dumps(payload)
    if PLIST.is_file() and PLIST.read_bytes() == raw:
        return False
    PLIST.write_bytes(raw)
    return True


def _stop_legacy_pid() -> None:
    pid_file = STATE_DIR / f"catalog-{PORT}.pid"
    if not pid_file.is_file():
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            os.kill(pid, 0)
    except (ValueError, ProcessLookupError, PermissionError):
        pass
    with contextlib.suppress(OSError):
        pid_file.unlink()


def _start_launchd(site: Path, index: bytes) -> int:
    log_path = workspace.log_dir().resolve() / f"catalog-{PORT}.log"
    changed = _write_plist(site, log_path)
    if serving_catalog(index) and _service_running() and not changed:
        pid = _service_pid()
        print(f"Catalog already running ({LABEL}): {URL}\n"
              f"PID: {pid or '?'} | Plist: {PLIST} | Log: {log_path}")
        return 0

    if serving_catalog(index) and not _service_running():
        _stop_legacy_pid()

    domain = _domain()
    target = f"{domain}/{LABEL}"
    if _service_running():
        subprocess.run(["launchctl", "bootout", target],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            if not _service_running():
                break
            time.sleep(0.25)

    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            if not serving_catalog(index):
                print(f"Port {PORT} is already in use by another service. "
                      "It has been left running.", file=sys.stderr)
                return 1
    except OSError:
        pass

    bootstrapped = False
    for _ in range(5):
        res = subprocess.run(["launchctl", "bootstrap", domain, str(PLIST)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            subprocess.run(["launchctl", "enable", target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            bootstrapped = True
            break
        time.sleep(0.5)

    if not bootstrapped:
        print(f"Could not bootstrap {LABEL} from {PLIST}.", file=sys.stderr)
        return 1

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if serving_catalog(index):
            pid = _service_pid()
            print(f"Catalog running ({LABEL}): {URL}\n"
                  f"PID: {pid or '?'} | Plist: {PLIST} | Log: {log_path}")
            return 0
        time.sleep(0.1)

    print(f"Could not start the catalog on port {PORT}. "
          f"See {log_path}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", type=Path, help=argparse.SUPPRESS)   # the detached child
    ap.add_argument("--stop", action="store_true", help="stop the background service")
    args = ap.parse_args()
    if args.serve:
        serve(args.serve)
        return 0
    if args.stop:
        if sys.platform == "darwin" and shutil.which("launchctl"):
            subprocess.run(["launchctl", "bootout", f"{_domain()}/{LABEL}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _stop_legacy_pid()
        print(f"Catalog service stopped ({LABEL}).")
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

    if sys.platform == "darwin" and shutil.which("launchctl"):
        return _start_launchd(site, index)

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

