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
# Discord hard-caps a message at 2000 chars. The largest deck is ~1826 with
# fences, so one deck fits today — but the margin is thin, so split defensively.
LIMIT = 1900


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
    blocks = _fence(path.read_text(encoding="utf-8"))
    # Keep the header in the same message as the list when it fits, rather than
    # burning a second Discord message on one line of text.
    if len(blocks) == 1 and len(header) + 1 + len(blocks[0]) <= LIMIT:
        return [f"{header}\n{blocks[0]}"]
    return [header] + blocks


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
