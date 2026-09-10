"""Deterministic prefix commands, handled without calling Codex.

`handle(text)` returns a list of Discord-ready messages, or None when the text
isn't a command — in which case bot.py forwards it to the model as usual.

**The `!` names here are an internal wire format, and they are NOT the `!` names
users type.** Both layers use a `!` prefix, which is worth untangling:

    what a user types      /deck-print deck: zur     (slash command)
                           !deck-print deck: zur     (same command, as chat text)
    what reaches us        !deck zur                 (this module's wire format)

The user-facing commands live in the sibling discord-bot project and are named
after the slash commands: `deck-print`, `deck-list`, `deck-repo`. Any of them a
manifest marks `supportsChat: true` can also be invoked as plain text with `!`,
running the identical `execute()` — that exists because Discord will not turn a
pasted `/command` into a real interaction, so `!` gives people something they can
copy, paste and share.

Ours are the shorter `!deck` and `!decks`, which no user types and no chat
command matches. So AGENTS.md should quote `/deck-print deck:` or
`!deck-print deck:` — never the bare `!deck`.

These exist because listing and printing decks is pure file reading. Routing it
through the model would cost tokens and latency for a fixed answer, and would risk
a paraphrased or partially-hallucinated decklist. A decklist is something you paste
into a client to import, so it has to be byte-exact.

**`!deck` returns the decklist RAW** — newline-separated `1 Card Name` lines and
nothing else. No fence, no header, no length handling. That is deliberate: the
reply is flattened to one string by bot.py and then re-split by the Discord side,
which cuts at the nearest newline under 2000 characters and knows nothing about
``` fences. Anything we fenced here came back with a fence cut through it, half
the list rendered as plain text. Fencing and splitting belong to whoever knows
Discord's rules; our job is to hand over an exact list.

`!decks` and `!help` ARE still fenced, and the difference is not an oversight:
that output is READ, so monospacing it here is helpful, whereas a decklist is
PASTED and anything wrapped around it is something the user has to strip out.

But fencing is only safe while a message fits. This docstring used to claim the
listing "never approaches the length limit"; at 45 decks it was 1567 of Discord's
2000 characters and still growing, and a fenced block the Discord side splits
gets cut through the fence -- the exact failure `!deck` was changed to avoid.
So `!decks` now returns one message PER BRACKET, and splits a bracket again if it
would exceed a conservative budget. The rule this encodes: whoever adds the fence
owns the split. `!deck` hands over raw text and lets Discord split it precisely
because it does NOT fence; anything we do fence, we have to keep small enough
that nobody else needs to cut it.
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


# ---------- formatting ----------

def _fence(body: str, lang: str = "") -> str:
    """Wrap body in ``` fences. No length limit — that is not ours to know.

    There used to be a LIMIT here that split long output across messages, and it
    was the source of the bug it was meant to prevent: the split happened at OUR
    budget, then bot.py flattened the pieces back into one string and the Discord
    side re-split THAT at its own boundary, cutting through a fence. Two layers
    guessing at the same limit produced output neither would have produced alone.
    Length now belongs entirely to whoever talks to Discord.
    """
    return f"```{lang}\n{body.rstrip(chr(10)) or '(empty)'}\n```"


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


def _keys(path: Path) -> set[str]:
    """Everything a user might reasonably type to mean this deck.

    The filename AND the commander's printed name. Matching the filename alone
    was the whole bug: someone who reads "Shorikai, Genesis Engine" in a reply --
    which is now exactly what the card tags put in front of them -- and pastes it
    back got "no deck matching", because it is not a substring of
    "Shorikai-Prison".
    """
    keys = {_norm(path.stem)}
    try:
        keys.add(_norm(deckfile.parse(path).commander))
    except Exception:                       # unreadable file: the stem still works
        pass
    return {k for k in keys if k}


def _label(path: Path) -> str:
    """`Stem — Commander`, for a disambiguation list."""
    try:
        return f"{path.stem} — {deckfile.parse(path).commander}"
    except Exception:
        return path.stem


def _match(query: str) -> tuple[list[Path], str | None]:
    """Resolve a user-typed deck name, case- and punctuation-insensitively.

    Error text names `!deck-list`, never `!decks`. The latter is this module's
    internal wire format and matches no user-facing command, so telling someone
    to type it sends them somewhere that does nothing.
    """
    decks = _decks()
    q = _norm(query)
    if not q:
        return [], "give a deck name — try `!deck-list` to see them"

    keyed = [(p, _keys(p)) for p in decks]
    exact = [p for p, keys in keyed if q in keys]
    if len(exact) == 1:
        return exact, None
    if not exact:
        exact = [p for p, keys in keyed if any(q in k for k in keys)]
    if not exact:
        return [], f"no deck matching `{query}`. Try `!deck-list`."
    if len(exact) > 1:
        # One per line, and none of them on the sentence's line. Run together
        # after a colon, the first match reads as part of the prose and the list
        # is hard to scan — which is the whole job of this message. The commander
        # is included because two decks can share a commander.
        names = "\n".join(_label(p) for p in exact)
        return [], f"`{query}` matches {len(exact)} decks — say which:\n{names}"
    return exact, None


# ---------- commands ----------

def cmd_decks(_arg: str) -> list[str]:
    """List every commander, one fenced message PER BRACKET.

    Per bracket rather than one block for the whole collection, because a fenced
    message that exceeds Discord's 2000 characters gets split downstream and the
    split cuts through the fence. Bracket is the natural bound: it is how people
    already read the list, and it keeps each message small as the collection
    grows.
    """
    # Budget, not Discord's real cap. We own the fence, so we own the split --
    # and the two ``` lines plus the bracket header cost characters the cap does
    # not know about. Well under 2000 leaves room for both and for a long
    # commander name landing on the boundary.
    BUDGET = 1500
    groups: dict[str, list[str]] = {}
    for path in _decks():
        try:
            row = f"  {deckfile.parse(path).commander}"
        except Exception as exc:                        # unreadable/malformed file
            row = f"  {path.stem} — unreadable ({exc.__class__.__name__})"
        groups.setdefault(_bracket_of(path), []).append(row)
    if not groups:
        return [f"No decks found under `{workspace.deck_root()}`."]
    out: list[str] = []
    for bracket, rows in groups.items():
        chunk: list[str] = []
        for row in rows:
            # +1 for the newline this row will add.
            if chunk and sum(len(r) + 1 for r in chunk) + len(row) + 1 > BUDGET:
                out.append(_fence(f"{bracket}\n" + "\n".join(chunk)))
                chunk = []
            chunk.append(row)
        if chunk:
            out.append(_fence(f"{bracket}\n" + "\n".join(chunk)))
    return out


def cmd_deck(arg: str) -> list[str]:
    """The decklist, raw — `1 Card Name` lines separated by newlines, nothing else.

    No fence, no header, no splitting. Whatever this returns is what someone
    pastes into a deck importer, so anything wrapped around it is something they
    have to strip back out. Presentation is the Discord layer's job: it knows the
    2000-character limit and where a fence may legally be cut, and this does not.
    """
    matches, err = _match(arg)
    if err:
        return [err]
    return [matches[0].read_text(encoding="utf-8").rstrip() + "\n"]


def cmd_help(_arg: str) -> list[str]:
    """Show these commands."""
    body = "\n".join(
        # Defensive: a command added without a docstring should not break help.
        f"{PREFIX}{name:<14} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else '-'}"
        for name, fn in COMMANDS.items()
    )
    return [_fence(body + "\n\nAnything else is sent to the deckbuilding agent.")]


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
