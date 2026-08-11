"""Decklist file format — parsing and discovery.

Concerned only with turning `.txt` files into structured entries and back. Knows
nothing about Scryfall, brackets or legality.

Format (see README.md):

    1 Zur the Enchanter        <- line 1 is ALWAYS the commander
    1 Academy Rector
    16 Swamp
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

LINE = re.compile(r"^(\d+)\s+(.+)$")

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
BASICS |= {f"Snow-Covered {b}" for b in list(BASICS)}


class Entry(NamedTuple):
    count: int
    name: str


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
        entries.append(Entry(int(m.group(1)), m.group(2).strip())) if m else bad.append(line)
    return Deck(path, entries, bad)


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
