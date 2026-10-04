"""Commander catalog categories: a FIXED vocabulary of seven, a catch-all, and Goblins.

Every deck's assignment lists its primary category first, then any secondary
categories. The seven canonical categories, plus the `other` catch-all for a
plan that genuinely fits none of them, are the only IDs a builder may use;
adding or renaming one is an owner decision, not a builder's. Goblins is an
eighth, private-only category: a Goblin deck keeps a canonical primary and
carries `goblins` as a secondary tag, and the LOCAL catalog mirrors it into a
Goblins section. The published catalog ignores the tag entirely.

Public assignments live in frontend/deck-themes.json; private assignments live
only in private/deck-themes.json. Never merge the private mapping into the public
one, even when a private deck has the same filename as a public deck.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    label: str
    description: str
    aliases: str = ""
    # Shown only in the local (private) catalog, as a mirror of decks that
    # already sit in a canonical category. Never a primary.
    private_only: bool = False


# Display order is stable across brackets, filters, and builds. Each category is
# defined by HOW THE DECK WINS, so every deck has one obvious primary.
THEMES = {
    "aggro": Theme("Aggro & Voltron", "Win by attacking: one huge threat, attack triggers, extra combats, evasive beatdown.",
                   "combat voltron attacks equipment keywords tribal beatdown"),
    "gowide": Theme("Tokens & Aristocrats", "Win with an army of tokens or small creatures, or by sacrificing it for value and drain.",
                    "tokens go wide swarm aristocrats sacrifice death triggers"),
    "combo": Theme("Combo", "Win by assembling a loop or an alternate win condition.",
                   "infinite loops alt win"),
    "control": Theme("Stax & Control", "Win by denying the table: taxes, locks, hatebears, pillowfort, counterspells, theft and goad.",
                     "stax prison lockdown hatebears pillowfort theft goad counterspells"),
    "graveyard": Theme("Graveyard", "Use the graveyard as a resource: reanimation, recursion, self-mill, discard and wheels.",
                       "reanimator recursion discard wheels self-mill"),
    "spells": Theme("Spells & Burn", "Win without combat: spellslinger and storm engines, burn, drain and punisher effects.",
                    "spellslinger storm instants sorceries burn punisher drain group slug lifegain"),
    "value": Theme("Value & Ramp", "Out-resource the table with engines: big mana, lands, artifacts, enchantments, counters, blink and planeswalkers.",
                   "ramp big mana lands landfall artifacts enchantress counters proliferate blink superfriends toolbox"),
    # The public catch-all. Only for a plan that genuinely fits none of the seven,
    # and for decks nobody has placed yet (see FALLBACK).
    "other": Theme("Other Strategies", "Plans that genuinely fit none of the seven categories above.",
                   "misc unique"),
    "goblins": Theme("Goblins", "Every Goblin deck, mirrored here from its own category. Local catalog only.",
                     "goblin kindred typal", private_only=True),
}

# The categories a deck can have as its primary: the seven plus `other`.
# Goblins is not one of them.
CANONICAL = tuple(k for k, t in THEMES.items() if not t.private_only)


# A conservative fallback for decks without an explicit assignment, keyed on the
# word after the hyphen. Curated assignments override these hints: Cloud-Equipment
# and Cloud-Attacks, for example, are placed by their maps, not their names.
_HINT_WORDS = {
    "control": "prison lockdown hatebears antisacrifice graveyardhate stax pillowfort antistax "
               "anticounters theft gifts goad tempo removal",
    "aggro": "voltron attacks keywords equipment beats ninjas dinosaurs dragons angels warriors humans vehicles",
    "gowide": "tokens swarm aristocrats sacrifice elves rats vampires myriad",
    "graveyard": "reanimator discard refill graveyard wheels",
    "spells": "spells spellslinger storm miracles punisher burn drain antispells",
    "combo": "combo infinite",
    "value": "lands landfall artifacts treasure enchantress counters proliferate superfriends blink "
             "ramp toolbox activations topdeck cascade discover legends",
}
HINTS = {w: (cat,) for cat, words in _HINT_WORDS.items() for w in words.split()}
HINTS["goblins"] = ("gowide", "goblins")
FALLBACK = ("other",)


def load(path: Path) -> dict[str, tuple[str, ...]]:
    """Read optional assignments, failing clearly on anything outside the fixed set."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a deck-name to theme-list mapping")
    result = {}
    for stem, themes in raw.items():
        if (not isinstance(themes, list) or not themes
                or any(not isinstance(t, str) or t not in THEMES for t in themes)
                or len(set(themes)) != len(themes)):
            raise ValueError(f"{path}: invalid themes for {stem!r}: {themes!r} "
                             f"(allowed: {', '.join(THEMES)})")
        if themes[0] not in CANONICAL:
            raise ValueError(f"{path}: {stem!r} must start with one of the canonical "
                             f"categories ({', '.join(CANONICAL)}), not {themes[0]!r}")
        result[stem] = tuple(themes)
    return result


def classify(stem: str, assignments: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return assignments.get(stem) or HINTS.get(stem.rsplit("-", 1)[-1].lower(), FALLBACK)


def visible(themes: tuple[str, ...], private_catalog: bool) -> tuple[str, ...]:
    """The tags a catalog shows: the published one drops private-only categories."""
    return themes if private_catalog else tuple(t for t in themes if not THEMES[t].private_only)


def search_text(themes: tuple[str, ...]) -> str:
    return " ".join(f"{THEMES[t].label} {THEMES[t].aliases}".strip() for t in themes)
