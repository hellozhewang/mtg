"""Strategy guides for decks, rendered as a tab on the deck page.

A guide is a plain text file living beside its decklist, same name, `.guide`
instead of `.txt`:

    public/Bracket3.5/Shorikai-Prison.txt
    public/Bracket3.5/Shorikai-Prison.guide

**The format is the showcards format**, deliberately: `# Section` headers and
`Name :: comment` lines. That syntax already exists in this repo, it is already
what a guide wants to say, and reusing it means one thing to learn instead of two.
A line with no `::` is prose, and belongs where a paragraph reads better than a
card row.

    # How it wins
    Prose lines need no card and render as a paragraph.
    Shorikai, Genesis Engine :: taps for two Pilots and two cards, every turn

WHY BESIDE THE DECK, IN `public/`
---------------------------------
Two reasons. The catalog builder already walks that tree, so a guide is found
without a second discovery path or a second convention to remember. And `public/`
is the ONLY directory the Codex session can write, so the builder can author a
guide for a deck it just made — which is the point of putting it there rather
than in a `guides/` folder at the repo root that the sandbox cannot reach.

`deckfile.discover()` globs `*.txt`, so a `.guide` file is never mistaken for a
decklist.

COMBO AND CHAIN ROWS
--------------------
One row can name several cards, so a combo or a tutor line reads as one thing
with every card pictured:

    Kiki-Jiki, Mirror Breaker + Zealous Conscripts :: Kiki copies Conscripts ...
    Goblin Matron -> Krenko, Mob Boss :: when you need a board, not a combo piece
    Goblin Recruiter -> Kiki-Jiki, Mirror Breaker + Conspicuous Snoop :: ...

` + ` joins cards that work together; ` -> ` reads "finds" or "leads to". The
spaces around each joiner are required, which is what keeps a card name like
"+2 Mace" from splitting.
"""
from __future__ import annotations

import re
from pathlib import Path

SPLIT = "::"
# Captures the joiner so pieces() can tell a combo (+) from a chain (->).
JOINER = re.compile(r"\s+(\+|->|→)\s+")


def guide_path(deck: Path) -> Path:
    """The guide that belongs to a decklist, whether or not it exists."""
    return deck.with_suffix(".guide")


def parse(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """`[(section title, [(card name or "", comment)])]`, in file order.

    An empty card name means the row is prose. Content before any `#` header
    lands in a section with an empty title, which renders as an intro with no
    heading — the natural place for a one-line summary of the deck.
    """
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    current: list[tuple[str, str]] = []
    title = ""

    def flush() -> None:
        if current or title:
            sections.append((title, list(current)))

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            flush()
            title, current = line.lstrip("#").strip(), []
            continue
        name, sep, comment = line.partition(SPLIT)
        if sep:
            current.append((name.strip(), comment.strip()))
        else:
            current.append(("", line))          # prose
    flush()
    return sections


def load(deck: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    """Parsed guide for a deck, or [] when it has none."""
    path = guide_path(deck)
    try:
        return parse(path.read_text(encoding="utf-8"))
    except OSError:
        return []


def pieces(name: str) -> list[tuple[str, str]]:
    """Split a row's card field into `[(joiner, card)]`, in order.

    The first card's joiner is "". A plain single-card row returns one piece, so
    callers can treat every row the same way. "→" is accepted as a spelling of
    "->" and normalised to it.
    """
    parts = JOINER.split(name.strip())
    out = [("", parts[0].strip())]
    for i in range(1, len(parts) - 1, 2):
        out.append(("->" if parts[i] in ("->", "→") else "+", parts[i + 1].strip()))
    return [(j, c) for j, c in out if c]


def card_names(sections) -> list[str]:
    """Every distinct card a guide references, in first-seen order.

    build_site needs this before rendering, to fetch the images the guide will
    show — the same reason the deck page collects its own card images up front.
    Combo and chain rows contribute every card they name.
    """
    seen: list[str] = []
    for _, rows in sections:
        for name, _comment in rows:
            for _joiner, card in pieces(name) if name else []:
                if card not in seen:
                    seen.append(card)
    return seen
