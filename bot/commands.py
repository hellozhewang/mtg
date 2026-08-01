"""Deterministic prefix commands, handled without calling Codex.

`handle(text)` returns a list of Discord-ready messages, or None when the text
isn't a command — in which case bot.py forwards it to the model as usual.

**The `!` prefix here is an internal wire format, not what users type.** Discord
users invoke registered slash commands, which live in the sibling discord-bot
project (`src/features/commands/deck-print.ts`, `deck-list.ts`). Those translate:

    user types  /deck-print deck: zur      (`deck` is a required string option)
    deck-print.ts -> askDeckBuilder("!deck zur", channelId)
    -> python3 bot.py --channel <id> "!deck zur"
    -> handle("!deck zur")  [here]

`/deck-list` takes no options and maps to "!decks". So renaming a command here
means renaming it in that project too, and AGENTS.md tells the agent to reference
`/deck-print deck:` and `/deck-list`, never the `!` forms.

These exist because listing and printing decks is pure file reading. Routing it
through the model would cost tokens and latency for a fixed answer, and would risk
a paraphrased or partially-hallucinated decklist. A decklist is something you paste
into a client to import, so it has to be byte-exact.

Output is fenced in ``` so Discord renders it monospaced and stops "smart" quote
substitution from corrupting card names like `Urza's Saga`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent        # bot/ -> repo root
sys.path.insert(0, str(_REPO / "scripts"))

import deckfile
import workspace

PREFIX = "!"
# What Discord actually accepts in one message. Our reply is flattened to a
# single string by bot.py and then re-split by splitDiscordText() in the
# discord-bot project, which cuts at the nearest newline under this number and
# knows nothing about ``` fences. So a reply longer than this does not merely
# arrive in two parts — it arrives with the code fences CUT THROUGH, leaving
# half the list rendered as plain text and a stray ``` floating in the channel.
# Everything below exists to keep a decklist reply under it.
DISCORD_LIMIT = 2000
# Discord hard-caps a message at 2000 chars; this is our budget within that.
#
# It was 1900, which is where a real bug lived: a 100-card list runs 1500-1950
# characters, so decks landed in the 1892-2000 gap between our cap and Discord's
# and got split across two fenced blocks. A decklist exists to be pasted into an
# importer, and half a list is useless — the split broke the one thing the
# command is for, on the biggest decks, while Discord would have accepted them
# whole. 1990 leaves a 10-character margin and keeps every current deck in one
# block.
LIMIT = 1990


# ---------- formatting ----------

def _fence(body: str, lang: str = "") -> list[str]:
    """Wrap body in ``` fences, splitting across messages if it exceeds LIMIT."""
    overhead = len(f"```{lang}\n\n```")
    budget = LIMIT - overhead
    lines, chunks, cur = body.rstrip("\n").split("\n"), [], []
    size = 0
    for line in lines:
        # +1 for the newline that will rejoin it
        if cur and size + len(line) + 1 > budget:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return [f"```{lang}\n{c}\n```" for c in chunks] or [f"```{lang}\n(empty)\n```"]


# ---------- deck discovery ----------

def _decks() -> list[Path]:
    return sorted(deckfile.discover([workspace.deck_root()]))


def _bracket_of(path: Path) -> str:
    return path.parent.name


def _norm(s: str) -> str:
    """Fold a deck name for matching: case, spaces and punctuation all ignored.

    Normalising BOTH sides is the point — `Kozilek-Annihilator` has a hyphen the
    user will type as a space (or omit), and `!deck ZURVOLTRON` should work too.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _match(query: str) -> tuple[list[Path], str | None]:
    """Resolve a user-typed deck name, case- and punctuation-insensitively."""
    decks = _decks()
    q = _norm(query)
    if not q:
        return [], "give a deck name — try `!decks` to see them"

    exact = [p for p in decks if _norm(p.stem) == q]
    if exact:
        return exact, None
    partial = [p for p in decks if q in _norm(p.stem)]
    if not partial:
        return [], f"no deck matching `{query}`. Try `!decks`."
    if len(partial) > 1:
        names = ", ".join(f"`{p.stem}`" for p in partial)
        return [], f"`{query}` matches several decks: {names}"
    return partial, None


# ---------- commands ----------

def cmd_decks(_arg: str) -> list[str]:
    """List every commander, grouped by bracket."""
    rows, current = [], None
    for path in _decks():
        bracket = _bracket_of(path)
        if bracket != current:
            rows.append(f"{bracket}" if current is None else f"\n{bracket}")
            current = bracket
        try:
            rows.append(f"  {deckfile.parse(path).commander}")
        except Exception as exc:                        # unreadable/malformed file
            rows.append(f"  {path.stem} — unreadable ({exc.__class__.__name__})")
    if not rows:
        return [f"No decks found under `{workspace.deck_root()}`."]
    return _fence("\n".join(rows))


def cmd_deck(arg: str) -> list[str]:
    """Print one decklist verbatim, ready to paste in."""
    matches, err = _match(arg)
    if err:
        return [err]
    path = matches[0]
    deck = deckfile.parse(path)
    header = f"{path.stem} — {deck.commander} — {deck.total} cards ({_bracket_of(path)})"
    body = path.read_text(encoding="utf-8").rstrip()
    one = f"{header}\n```\n{body}\n```"

    # ONE message or none — never two. bot.py flattens whatever we return into a
    # single string, and the Discord side re-splits that blind at 2000 characters
    # (splitDiscordText, discord-bot/src/features/deckBuilder.ts). It cuts at the
    # nearest newline and knows nothing about ``` fences, so a two-block reply
    # comes back with a fence cut through: half the list renders as plain text
    # and a stray ``` is left in the channel.
    #
    # So when the list will not fit, do not try. Send the raw link instead: it is
    # a single paste at any length, and a correct link beats a mangled list.
    if len(one) <= DISCORD_LIMIT:
        return [one]
    return [f"{header}\n"
            f"Too long for one Discord message ({len(body)} characters), and "
            f"splitting it would break the code block. Full list, ready to copy "
            f"in one go:\n{workspace.raw_url(path)}"]


def cmd_help(_arg: str) -> list[str]:
    """Show these commands."""
    body = "\n".join(
        # Defensive: a command added without a docstring should not break help.
        f"{PREFIX}{name:<14} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else '-'}"
        for name, fn in COMMANDS.items()
    )
    return _fence(body + "\n\nAnything else is sent to the deckbuilding agent.")


COMMANDS = {
    "decks": cmd_decks,
    "deck": cmd_deck,
    "help": cmd_help,
}


# ---------- entry point ----------

def handle(text: str) -> list[str] | None:
    """Run a command, or return None so bot.py forwards the text to Codex."""
    text = (text or "").strip()
    if not text.startswith(PREFIX):
        return None
    head, _, arg = text[len(PREFIX):].partition(" ")
    fn = COMMANDS.get(head.lower())
    if fn is None:
        known = ", ".join(f"`{PREFIX}{k}`" for k in COMMANDS)
        return [f"Unknown command `{PREFIX}{head}`. Known: {known}"]
    return fn(arg)
