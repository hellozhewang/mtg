"""Power tiers: how hard each deck actually hits, independent of its bracket.

A bracket is a rules ceiling (what the deck may run). A tier is a judgment of
what the finished list does at a four-player table: how fast it wins, how
reliably, and through how much interaction. Two Bracket 3.5 decks can sit tiers
apart, and a Bracket 3 deck can outrank a 3.5 one.

The rubric, anchor decks and placement checklist live in deck-tiers.md. Public
assignments live in frontend/deck-tiers.json; private assignments live only in
private/deck-tiers.json. As with themes, never merge the private mapping into
the public one. There is no filename fallback: a deck without an assignment is
shown as Unrated until someone places it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Tier:
    label: str
    title: str
    description: str


# Strongest first. Display order everywhere follows this dict.
TIERS = {
    "GOD": Tier("GOD", "GOD tier",
                "cEDH. Wins or locks on turns 1-4 through interaction: full fast mana, "
                "free counterspells, deep tutors and compact wins."),
    "SS": Tier("SS", "SS tier",
               "Fringe cEDH with uncapped Game Changers. Wins or locks on turns 3-6, "
               "with fast mana and many tutors aimed at redundant game-ending lines."),
    "S": Tier("S", "S tier",
              "The ceiling of a three-Game-Changer deck. Several compact wins, enough "
              "tutors to find them, and a kill on turns 5-7."),
    "A": Tier("A", "A tier",
              "Strong. A combo deck with less redundancy, or a top engine deck that "
              "reliably kills on turns 6-8. The table's archenemy."),
    "B": Tier("B", "B tier",
              "Solid Bracket 3. A coherent plan with enough ramp, draw and answers; "
              "wins on turns 7-9 without combos."),
    "C": Tier("C", "C tier",
              "Fair. Works, but slow, commander-dependent or light on interaction; "
              "wins on turn 9 or later."),
    "D": Tier("D", "D tier",
              "Weak. Theme first or narrowly aimed; easily disrupted and struggles "
              "against a table of B decks."),
    "TRASH": Tier("TRASH", "TRASH tier",
                  "Does not work as built, or another deck here does the same job "
                  "better. Rebuild or delete."),
}

# Shown for a deck with no assignment yet. Not a tier: never write it to a map.
UNRATED = Tier("?", "Unrated", "Not placed yet. Add it to the tier map (see deck-tiers.md).")
UNRATED_ID = "unrated"


def load(path: Path) -> dict[str, str]:
    """Read optional assignments, failing clearly on a misspelled tier."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a deck-name to tier mapping")
    for stem, tier in raw.items():
        if not isinstance(tier, str) or tier not in TIERS:
            raise ValueError(f"{path}: invalid tier for {stem!r}: {tier!r} "
                             f"(expected one of {', '.join(TIERS)})")
    return dict(raw)


def classify(stem: str, assignments: dict[str, str]) -> str | None:
    """The deck's tier ID, or None when nobody has placed it yet."""
    return assignments.get(stem)


def info(tier: str | None) -> Tier:
    return TIERS[tier] if tier else UNRATED


def search_text(tier: str | None) -> str:
    """One token, e.g. `S-tier`. The catalog search strips punctuation and spaces,
    so this lets "s tier" or "god tier" find a tier without a separate filter."""
    return f"{tier}-tier" if tier else "unrated"
