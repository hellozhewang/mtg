#!/usr/bin/env python3
"""The tool-invocation log: a small API, with SQLite behind it.

Every business-logic script calls `record()` on startup. Answers "did the agent
use the tools, or freestyle a decklist?" without reconstructing it afterwards
from a codex session rollout.

    import toollog
    toollog.record()                      # every tool, first line of main()
    toollog.since(t, channel="1234")      # what ran in that turn   -> bot.py
    toollog.recent(20)                    # the last 20 calls       -> humans
    toollog.flush()                       # append new rows to a file

Callers only ever use those four. **Storage is an implementation detail** — rows
in the `toolcalls` table of the `.cache/cards.db` the tools already open. Nothing
outside this module knows that, so the sink can change without touching a caller.

Why a database and not a log file. `.cache` is the ONE directory the sandboxed
Codex session can write, granted by bot.py with `--add-dir`, so a record always
lands. Writing to `logs/` does not work — the sandbox blocks it — and the scheme
that worked around it (announce on stderr, have bot.py grep the line back out of
codex's captured output) was lossy: codex does not surface every tool's stderr,
and one measured turn logged 2 of about 10 calls. Beyond that, SQLite already
gives concurrent appends from several processes, ordering, and reading a slice
back; the file version needed a spool, a drain, a truncate and a lock to
approximate the same thing, and still dropped records.

Reading it from a shell:

    ./toollog.py                        # the last 50 calls
    ./toollog.py --channel 12345 -n 20  # one Discord channel
    ./toollog.py --flush                # append new rows to logs/tools.log
    ./toollog.py --sql "SELECT tool, COUNT(*) FROM toolcalls GROUP BY tool"

`--flush` is checkpointed on the monotonic row id, so running it repeatedly
appends only what is new. The checkpoint lives in `logs/`, not the database, and
that is deliberate: `logs/` is outside the sandbox, so a session cannot rewind it
to make a call it already made look unflushed.

A `[mtg-tool]` line also goes to stderr, always. It costs nothing, makes a tool
self-announcing in a terminal, and is the last resort if the database is
unavailable.

Set MTG_NO_TOOLLOG=1 to silence recording (useful for bulk scripted runs).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workspace

# Marker for the stderr line. bot.py greps for it only as a fallback now.
PREFIX = "[mtg-tool]"
CHECKPOINT = ".toollog-checkpoint"


def _store():
    """Open the backing store. Imported late so `import toollog` stays cheap for
    the tools, which call record() before doing anything else."""
    from cardlib import ToolLogStore
    return ToolLogStore(workspace.cache_db())


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


# ---------- writing ----------

def record(argv: list[str] | None = None) -> None:
    """Log one invocation. Never raises — logging must not break a tool."""
    if os.environ.get("MTG_NO_TOOLLOG"):
        return
    try:
        argv = argv if argv is not None else sys.argv
        tool = Path(argv[0]).name
        args = " ".join(_quote(a) for a in argv[1:])

        # Always, and first: survives a database that is locked or read-only.
        print(f"{PREFIX} {tool} {args}".rstrip(), file=sys.stderr)

        _store().add(os.environ.get("MTG_TOOL_CHANNEL", "cli"), tool, args)
    except Exception as exc:
        # Never crash a tool over logging — but never fail SILENTLY either. A
        # bare `pass` here hid a plain ImportError, and the log simply recorded
        # nothing while every tool kept working and looked fine.
        print(f"{PREFIX} warning: not recorded ({type(exc).__name__}: {exc})",
              file=sys.stderr)


# ---------- reading ----------

class Call:
    """One recorded invocation. A plain object so callers never see a DB row."""

    __slots__ = ("id", "at", "channel", "tool", "args")

    def __init__(self, row):
        self.id, self.at = row["id"], row["at"]
        self.channel, self.tool, self.args = row["channel"], row["tool"], row["args"]

    @property
    def command(self) -> str:
        return f"{self.tool} {self.args}".rstrip()

    def __str__(self) -> str:
        stamp = datetime.fromtimestamp(self.at).astimezone().strftime(
            "%Y-%m-%dT%H:%M:%S%z")
        return f"{stamp} [{self.channel}] {self.command}"


def since(when: float, channel: str | None = None) -> list[Call]:
    """Calls recorded at or after `when` (a time.time() value). Never raises."""
    try:
        return [Call(r) for r in _store().query(since_time=when, channel=channel)]
    except Exception:
        return []


def recent(limit: int = 50, channel: str | None = None) -> list[Call]:
    try:
        return [Call(r) for r in _store().recent(limit, channel)]
    except Exception:
        return []


def flush(out: Path | None = None) -> int:
    """Append calls recorded since the last flush. Returns how many were written."""
    out = out or workspace.log_dir() / "tools.log"
    mark = out.parent / CHECKPOINT
    try:
        last = int(mark.read_text().strip())
    except (OSError, ValueError):
        last = 0
    rows = _store().query(since_id=last)
    if rows:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(str(Call(r)) + "\n")
        mark.write_text(str(rows[-1]["id"]))
    return len(rows)


# ---------- cli ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Show or flush the tool-invocation log.",
        epilog="Backed by the `toolcalls` table in .cache/cards.db.")
    ap.add_argument("-n", "--limit", type=int, default=50,
                    help="how many recent calls to show (default 50)")
    ap.add_argument("--channel", help="only this Discord channel (or 'cli')")
    ap.add_argument("--flush", nargs="?", const="", metavar="FILE",
                    help="append new calls to FILE (default logs/tools.log) "
                         "and advance the checkpoint")
    ap.add_argument("--sql", metavar="QUERY",
                    help="run a query against the log and print the rows")
    args = ap.parse_args()

    if args.sql:
        for row in _store().conn.execute(args.sql):
            print("  ".join(str(v) for v in row))
        return 0

    if args.flush is not None:
        out = Path(args.flush) if args.flush else None
        n = flush(out)
        print(f"{n} new call{'' if n == 1 else 's'} flushed")
        return 0

    calls = recent(args.limit, args.channel)
    for c in calls:
        print(c)
    if not calls:
        print("no tool calls recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
