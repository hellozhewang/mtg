#!/usr/bin/env python3
"""Start the private catalog for local-network access, always on port 5588."""
from __future__ import annotations

import argparse
import http.client
import socket
import subprocess
import sys
import time

import workspace

HOST = "127.0.0.1"
BIND_HOST = "0.0.0.0"
PORT = 5588
URL = f"http://localhost:{PORT}/"


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


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    site = workspace.private_site_dir().resolve()
    try:
        index = (site / "index.html").read_bytes()
    except OSError as error:
        print(f"Cannot read the private catalog: {error}\n"
              "Build it first with: python3 scripts/build_site.py", file=sys.stderr)
        return 1

    if serving_catalog(index):
        print(f"Private catalog already running: {URL}")
        return 0

    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            print(f"Port {PORT} is already in use by another service. "
                  "It has been left running.", file=sys.stderr)
            return 1
    except OSError:
        pass

    state = workspace.private_dir() / "server"
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / f"catalog-{PORT}.log"
    with log_path.open("ab", buffering=0) as log:
        server = subprocess.Popen(
            [sys.executable, "-u", "-m", "http.server", str(PORT),
             "--bind", BIND_HOST, "--directory", str(site)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if server.poll() is not None:
            break
        if serving_catalog(index) and server.poll() is None:
            (state / f"catalog-{PORT}.pid").write_text(f"{server.pid}\n")
            print(f"Private catalog running: {URL}\n"
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
    print(f"Could not start the private catalog on port {PORT}. "
          f"See {log_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
