"""One log line per tool invocation, for debugging and verifying usage.

Every business-logic script calls `record()` on startup. Answers the question
"did the agent actually use the tools, or did it freestyle a decklist?" without
having to reconstruct it afterwards from a codex session rollout.

    2026-07-30T10:29:41-0700 TOOL    new_deck.py "Winota, Joiner of Forces" -o Bracket3/Winota-Attacks.txt
    2026-07-30T10:33:02-0700 TOOL    validate_deck.py Bracket3/Winota-Attacks.txt

**Two sinks, because of the sandbox.** `logs/` sits outside the deck workspace on
purpose and is NOT granted via `--add-dir`, so the sandboxed Codex session cannot
write there — that is what stops it rewriting its own history. So:

  * run directly (you, in a terminal)  -> appended to `logs/<utc-date>.log`
  * run by the bot inside the sandbox  -> the file write fails with EPERM, and the
    line goes to stderr instead. codex captures that in its transcript, and
    `bot.py` scrapes it back out and re-logs it from OUTSIDE the sandbox.

Net effect: every invocation is recorded either way, and the sandboxed session
still cannot forge or delete entries. The stderr line is always emitted, so it
shows up in a terminal too — cheap, and makes the tool self-announcing.

Set MTG_NO_TOOLLOG=1 to silence it (useful when scripting bulk runs).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workspace

# Marker bot.py greps for in codex's captured output. Keep it distinctive and in
# sync with bot.py's TOOL_LINE regex.
PREFIX = "[mtg-tool]"


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

        stamp = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        day = datetime.now().astimezone().strftime("%Y-%m-%d")
        d = workspace.log_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{day}.log", "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} TOOL    {line}\n")
    except (OSError, PermissionError):
        pass          # sandboxed: stderr already carried it, bot.py will re-log
    except Exception:
        pass          # logging is never worth crashing a tool over
