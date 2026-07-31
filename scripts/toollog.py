"""One log line per tool invocation, for debugging and verifying usage.

Every business-logic script calls `record()` on startup. Answers the question
"did the agent actually use the tools, or did it freestyle a decklist?" without
having to reconstruct it afterwards from a codex session rollout.

    2026-07-30T10:29:41-0700 TOOL    new_deck.py "Winota, Joiner of Forces" -o Bracket3/Winota-Attacks.txt
    2026-07-30T10:33:02-0700 TOOL    validate_deck.py Bracket3/Winota-Attacks.txt

**Three sinks, because of the sandbox.** `logs/` sits outside the deck workspace
on purpose and is NOT granted via `--add-dir`, so the sandboxed Codex session
cannot write there — that is what stops it rewriting its own history.

  * run directly (you, in a terminal)  -> appended to `logs/<utc-date>.log`
  * run by the bot inside the sandbox  -> that write fails with EPERM, so the
    record goes to the SPOOL, `.cache/toolcalls.log`. `.cache` is the one
    directory the sandbox is granted (bot.py passes `--add-dir` for it so the
    tools can write the Scryfall cache). After each turn `bot.py` drains the
    spool from outside the sandbox and folds it into `logs/`.
  * always -> a `[mtg-tool]` line on stderr.

The spool exists because stderr alone was lossy. `bot.py` used to recover these
records ONLY by grepping codex's captured output, and codex does not surface
every tool's stderr in its final result: one measured turn banked 354 cards
across eight separate searches and reported exactly two tool calls. A file the
tools can always append to does not depend on what the harness chooses to echo.

The tradeoff is honest: the spool lives somewhere the session can write, so a
determined session could edit it, whereas `logs/` it cannot touch. Completeness
was worth more than that, since the log's job is telling you what the agent did
— and a log that silently drops three quarters of its entries fails that badly.
Drained entries land in `logs/`, out of reach, within a second of the turn.

Set MTG_NO_TOOLLOG=1 to silence it (useful when scripting bulk runs).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workspace

# Marker bot.py greps for in codex's captured output. Keep it distinctive and in
# sync with bot.py's TOOL_LINE regex.
PREFIX = "[mtg-tool]"

# Spool file inside the granted cache directory. Tab-separated so bot.py can
# split it back apart without parsing quotes: stamp, channel, command line.
SPOOL = "toolcalls.log"
SEP = "\t"


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def record(argv: list[str] | None = None) -> None:
    """Log one invocation. Never raises — logging must not break a tool."""
    if os.environ.get("MTG_NO_TOOLLOG"):
        return
    try:
        argv = argv if argv is not None else sys.argv
        line = f"{Path(argv[0]).name} " + " ".join(_quote(a) for a in argv[1:])
        line = line.strip()

        # stderr always: visible in a terminal, and captured by codex so bot.py
        # can recover it when the file sink below is blocked by the sandbox.
        print(f"{PREFIX} {line}", file=sys.stderr)

        now = datetime.now().astimezone()
        stamp = now.strftime("%Y-%m-%dT%H:%M:%S%z")
        # UTC day, matching bot.py's logger. These disagreed: bot.py named its
        # file by UTC and this by local time, so every evening west of Greenwich
        # the bot's entries and the tools' entries landed in DIFFERENT files.
        # The timestamp above stays local, which is what you want when reading.
        day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        try:
            d = workspace.log_dir()
            d.mkdir(parents=True, exist_ok=True)
            with open(d / f"{day}.log", "a", encoding="utf-8") as fh:
                fh.write(f"{stamp} TOOL    {line}\n")
            return                       # direct run: logs/ is authoritative
        except OSError:
            pass                         # sandboxed; fall through to the spool

        # Append-only and O_APPEND, so concurrent tools interleave whole lines
        # rather than corrupting each other. The channel lets bot.py drain only
        # its own turn and leave another channel's records alone.
        chan = os.environ.get("MTG_TOOL_CHANNEL", "?")
        spool = workspace.cache_dir() / SPOOL
        spool.parent.mkdir(parents=True, exist_ok=True)
        with open(spool, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp}{SEP}{chan}{SEP}{line}\n")
    except Exception:
        pass          # logging is never worth crashing a tool over
