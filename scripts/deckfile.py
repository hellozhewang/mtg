"""Decklist file format — parsing and discovery.

Concerned only with turning `.txt` files into structured entries and back. Knows
nothing about Scryfall, brackets or legality.

Format (see README.md):

    1 Zur the Enchanter        <- line 1 is ALWAYS the commander
    1 Academy Rector
    1 Sol Ring (SLD) 249       <- optional: pin one printing, for its art
    16 Swamp

A printing is the set code in parentheses and then the collector number, the
form Arena and Moxfield export and the one Tabletop Simulator's deck importer
reads. The number may be left off to mean "any printing from this set". Nothing
else in the pipeline cares which printing a card is: `Entry.name` is always the
bare card name, so legality, colour identity and the catalog work as before.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

LINE = re.compile(r"^(\d+)\s+(.+)$")
# "(SLD) 249" or "(SLD)" at the end of a line. Scryfall set codes are three to six
# letters and digits; collector numbers are not always numeric ("796★", "52s").
PRINTING = re.compile(r"^(.*\S)\s+\(([A-Za-z0-9]{3,6})\)(?:\s+(\S+))?$")

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
BASICS |= {f"Snow-Covered {b}" for b in list(BASICS)}


class Printing(NamedTuple):
    set: str                    # upper-case set code, e.g. "SLD"
    number: str | None          # collector number; None means any printing in the set

    def __str__(self) -> str:
        return f"({self.set})" + (f" {self.number}" if self.number else "")


class Entry(NamedTuple):
    count: int
    name: str
    printing: Printing | None = None


class Deck(NamedTuple):
    path: Path
    entries: list[Entry]
    bad_lines: list[str]

    @property
    def commander(self) -> str:
        return self.entries[0].name if self.entries else "?"

    @property
    def names(self) -> list[str]:
        return [e.name for e in self.entries]

    @property
    def total(self) -> int:
        return sum(e.count for e in self.entries)

    @property
    def printings(self) -> dict[str, Printing]:
        """Card name -> the printing pinned for it, for the lines that pin one."""
        return {e.name: e.printing for e in self.entries if e.printing}

    def duplicates(self) -> list[Entry]:
        """Entries with count > 1 that aren't basic lands (singleton violations)."""
        return [e for e in self.entries if e.count > 1 and e.name not in BASICS]

    def repeated_lines(self) -> list[str]:
        seen: dict[str, int] = {}
        for e in self.entries:
            seen[e.name] = seen.get(e.name, 0) + 1
        return [n for n, c in seen.items() if c > 1]


def parse(path: Path) -> Deck:
    entries: list[Entry] = []
    bad: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = LINE.match(line)
        if not m:
            bad.append(line)
            continue
        name, printing = split_printing(m.group(2).strip())
        entries.append(Entry(int(m.group(1)), name, printing))
    return Deck(path, entries, bad)


def split_printing(text: str) -> tuple[str, Printing | None]:
    """Split "Sol Ring (SLD) 249" into the card name and its pinned printing."""
    m = PRINTING.match(text)
    if not m:
        return text, None
    return m.group(1), Printing(m.group(2).upper(), m.group(3))


def render(commander: str, cards: dict[str, int]) -> str:
    """Format a decklist: commander on line 1, everything else alphabetised.

    `cards` must NOT contain the commander. Sorting is case-insensitive so
    output matches the existing decks, which were sorted that way.
    """
    lines = [f"1 {commander}"]
    lines += [f"{n} {c}" for c, n in
              sorted(cards.items(), key=lambda kv: kv[0].lower())]
    return "\n".join(lines) + "\n"


def write(path: Path, commander: str, cards: dict[str, int]) -> int:
    """Write a decklist and return its total card count."""
    path.write_text(render(commander, cards), encoding="utf-8")
    return 1 + sum(cards.values())


def discover(paths: list[Path]) -> list[Path]:
    """Expand a mix of files and folders into a sorted list of decklist files.

    No exclusions are needed: `private/` lives at the repo root, outside the deck
    workspace, so expanding the deck root never reaches it — while naming a
    private file explicitly still works, which is how you validate one in progress.
    """
    out: list[Path] = []
    for p in paths:
        p = Path(p).resolve()
        out.extend(sorted(p.rglob("*.txt")) if p.is_dir() else [p])
    return [f for f in out if f.is_file()]


def discover_private(root: Path) -> list[Path]:
    """The owner's decks in `root` (private/): its bracket folders ONLY.

    private/ also holds the owner's tools and scratch files, and `discover()` on
    the whole tree would turn every .txt among them into a "deck". It did once:
    four showcards input files rendered as decklists, one of them a 51-card
    "commander". The bracket folder is what marks a file as a deck, here and in
    validate_deck's gc_cap(). The site and the Discord commands both call this,
    so they always agree on which decks exist.
    """
    return discover(sorted(root.glob("Bracket*"))) if root.is_dir() else []
