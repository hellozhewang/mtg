"""Commander catalog themes, independent of brackets and card legality.

Curated assignments list the primary group first, then secondary filter tags.
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


# Display order is stable across brackets, filters, and builds.
THEMES = {
    "stax": Theme("Stax / Prison", "Tax actions, restrict resources, and shut down opposing engines.", "hatebears lockdown denial"),
    "pillowfort": Theme("Pillowfort", "Make attacking you difficult while you develop a winning position.", "defensive defence defense"),
    "voltron": Theme("Voltron", "Build one creature into a lethal attacker with Auras, Equipment, or other buffs.", "commander damage"),
    "tribal": Theme("Tribal / Kindred", "Build around a shared creature type and its synergies.", "typal creature type"),
    "tokens": Theme("Tokens / Go-wide", "Create an army of tokens or small creatures and turn numbers into power.", "swarm go wide"),
    "aristocrats": Theme("Aristocrats", "Sacrifice creatures and other permanents for cards, mana, and death triggers.", "sacrifice death drain"),
    "reanimator": Theme("Reanimator", "Use the graveyard to bring back threats or make powerful copies.", "graveyard recursion resurrection"),
    "spellslinger": Theme("Spellslinger / Storm", "Build engines around casting spells and chaining them into a decisive turn.", "instants sorceries cantrips"),
    "punisher": Theme("Group Slug / Punisher", "Damage the table or punish opponents for drawing, casting, and other actions.", "burn pain pings drain"),
    "goad": Theme("Goad / Forced Combat", "Make opponents attack and steer their creatures toward each other.", "forced attacks politics"),
    "combo": Theme("Combo", "Assemble interacting pieces for a decisive loop or alternate win.", "infinite loops"),
    "lands": Theme("Lands / Landfall", "Make land drops, land recursion, and land-based engines drive the deck.", "landfall lands matter"),
    "artifacts": Theme("Artifacts / Vehicles", "Build around artifacts, Equipment, Treasures, or Vehicle crews.", "artifact equipment treasure crew"),
    "enchantress": Theme("Enchantress", "Turn enchantments into a sustained engine of cards, protection, and threats.", "enchantments auras"),
    "counters": Theme("Counters / Proliferate", "Build and multiply counters on creatures and other permanents.", "proliferation +1/+1 -1/-1"),
    "lifegain": Theme("Lifegain / Drain", "Use life as a resource and turn life gain into damage or life loss.", "lifelink life gain"),
    "discard": Theme("Discard / Wheels", "Empty or replace hands and turn discarded cards into an advantage.", "hand disruption wheel"),
    "superfriends": Theme("Superfriends", "Protect planeswalkers and build toward their strongest loyalty abilities.", "planeswalkers loyalty"),
    "theft": Theme("Theft / Gifts", "Use opponents' cards or give away permanents with dangerous drawbacks.", "steal stolen donate donation"),
    "blink": Theme("Blink / ETB", "Repeat enter-the-battlefield abilities with flicker and copy effects.", "flicker enters etb"),
    "combat": Theme("Combat / Attack Triggers", "Win through combat abilities, attack triggers, and extra attacks.", "aggro attacks keywords toughness defenders"),
    "ramp": Theme("Ramp / Big Mana", "Accelerate mana into enormous creatures and spells.", "big mana stompy cascade discover"),
    "toolbox": Theme("Toolbox / Value", "Use flexible tutors, draw engines, and repeatable abilities to outlast opponents.", "midrange control activations topdeck"),
    "other": Theme("Other Strategies", "Explore decks with a different or newly added plan."),
}


# A conservative fallback for newly added decks. Curated assignments override
# these hints: Cloud-Equipment and Cloud-Attacks, for example, play differently.
HINTS = {
    "prison": ("stax",), "lockdown": ("stax",), "hatebears": ("stax",),
    "antisacrifice": ("stax",), "graveyardhate": ("stax",),
    "pillowfort": ("pillowfort",), "voltron": ("voltron",),
    "goblins": ("tribal",), "elves": ("tribal",), "rats": ("tribal",),
    "vampires": ("tribal",), "ninjas": ("tribal",), "dragons": ("tribal",),
    "dinosaurs": ("tribal",), "warriors": ("tribal",), "humans": ("tribal",),
    "wizards": ("tribal",), "sphinxes": ("tribal",), "angels": ("tribal",),
    "tokens": ("tokens",), "swarm": ("tokens",),
    "aristocrats": ("aristocrats",), "sacrifice": ("aristocrats",),
    "reanimator": ("reanimator",), "spells": ("spellslinger",),
    "spellslinger": ("spellslinger",), "storm": ("spellslinger",),
    "miracles": ("spellslinger",), "punisher": ("punisher",),
    "burn": ("punisher",), "drain": ("punisher",), "goad": ("goad",),
    "combo": ("combo",), "infinite": ("combo",), "lands": ("lands",),
    "landfall": ("lands",), "artifacts": ("artifacts",),
    "vehicles": ("artifacts",), "equipment": ("artifacts",),
    "treasure": ("artifacts",), "enchantress": ("enchantress",),
    "counters": ("counters",), "proliferate": ("counters",),
    "superfriends": ("superfriends",), "theft": ("theft",),
    "gifts": ("theft",), "blink": ("blink",), "attacks": ("combat",),
    "keywords": ("combat",), "ramp": ("ramp",),
    "toolbox": ("toolbox",), "activations": ("toolbox",),
}


def load(path: Path) -> dict[str, tuple[str, ...]]:
    """Read optional assignments, failing clearly on misspelled theme IDs."""
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
            raise ValueError(f"{path}: invalid themes for {stem!r}: {themes!r}")
        result[stem] = tuple(themes)
    return result


def classify(stem: str, assignments: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return assignments.get(stem) or HINTS.get(stem.rsplit("-", 1)[-1].lower(), ("other",))


def search_text(themes: tuple[str, ...]) -> str:
    return " ".join(f"{THEMES[t].label} {THEMES[t].aliases}".strip() for t in themes)
